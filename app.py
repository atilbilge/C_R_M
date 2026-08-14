#!/usr/bin/env python3
"""
Stanomer Acente CRM - Web Dashboard Backend (Flask API)
------------------------------------------------------
`acenteler.db` SQLite veritabanına doğrudan bağlı REST API ve Web Arayüzü sunucusu.
"""

import os
import sys
import json
import smtplib
import threading
import time
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, session, redirect, url_for
import db

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "stanomer_crm_secret_key_2026_super_secure")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "stanomer2026")

# Veritabanını başlat
db.init_db()


@app.before_request
def check_auth():
    """Giriş kontrolü middleware"""
    allowed_routes = ["login", "login_api", "static"]
    if request.endpoint in allowed_routes:
        return
    if request.path.startswith("/static/") or request.path == "/unsubscribe" or request.path.startswith("/api/unsubscribe"):
        return
    if not session.get("authenticated"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Yetkisiz erişim. Lütfen giriş yapın."}), 401
        return redirect(url_for("login"))


@app.route("/login", methods=["GET"])
def login():
    """Giriş Sayfası"""
    if session.get("authenticated"):
        return redirect(url_for("index"))
    return send_from_directory("static", "login.html")


@app.route("/api/login", methods=["POST"])
def login_api():
    """Şifre ile Giriş Yapma Endpoint'i"""
    data = request.json or {}
    password = data.get("password", "")
    if password == APP_PASSWORD:
        session["authenticated"] = True
        return jsonify({"success": True, "redirect": "/"})
    return jsonify({"error": "Hatalı şifre. Lütfen tekrar deneyin."}), 401


@app.route("/api/logout", methods=["POST"])
def logout_api():
    """Çıkış Yapma Endpoint'i"""
    session.clear()
    return jsonify({"success": True, "redirect": "/login"})


@app.route("/")
def index():
    """Ana Sayfa (Web Dashboard)"""
    return send_from_directory("static", "index.html")


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Özet İstatistikler"""
    try:
        stats = db.get_db_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agencies", methods=["GET"])
def get_agencies():
    """
    Acente Listesi ve Filtreleme
    Query Params: q (arama), city, status, source (companywall/nekretnine)
    """
    city = request.args.get("city", "").strip()
    status = request.args.get("status", "").strip()
    segment = request.args.get("segment", "").strip()
    source = request.args.get("source", "").strip()
    has_phone = request.args.get("has_phone", "").strip()  # 'yes' | 'no'
    has_email = request.args.get("has_email", "").strip()  # 'yes' | 'no'
    q = request.args.get("q", "").strip()

    conn = db.get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT DISTINCT a.id, a.name, a.segment, a.long_name, a.establishment_date, a.enterprise_size, a.employees_json, a.income_json, a.city, a.address, a.pib, a.mb, a.status, a.ref_code
        FROM agencies a
        LEFT JOIN agency_phones p ON a.id = p.agency_id
        LEFT JOIN agency_emails e ON a.id = e.agency_id
        LEFT JOIN agency_websites w ON a.id = w.agency_id
        LEFT JOIN communications c ON a.id = c.agency_id
        WHERE 1=1
    """
    params = []

    if city:
        sql += " AND LOWER(a.city) = LOWER(?)"
        params.append(city)

    if status:
        sql += " AND a.status = ?"
        params.append(status)

    if segment:
        sql += " AND a.segment = ?"
        params.append(segment)

    if source == "companywall":
        sql += " AND (w.url LIKE '%companywall.rs%' OR a.pib IS NOT NULL AND a.pib != '')"
    elif source == "nekretnine":
        sql += " AND w.url LIKE '%nekretnine.rs%'"
    elif source == "indomio":
        sql += " AND w.url LIKE '%indomio.rs%'"

    if has_phone == "yes":
        sql += " AND (SELECT COUNT(*) FROM agency_phones WHERE agency_id = a.id) > 0"
    elif has_phone == "no":
        sql += " AND (SELECT COUNT(*) FROM agency_phones WHERE agency_id = a.id) = 0"

    if has_email == "yes":
        sql += " AND (SELECT COUNT(*) FROM agency_emails WHERE agency_id = a.id) > 0"
    elif has_email == "no":
        sql += " AND (SELECT COUNT(*) FROM agency_emails WHERE agency_id = a.id) = 0"

    if q:
        sql += """ AND (
            LOWER(a.name) LIKE LOWER(?) OR
            LOWER(a.city) LIKE LOWER(?) OR
            LOWER(a.address) LIKE LOWER(?) OR
            a.pib LIKE ? OR
            a.mb LIKE ? OR
            LOWER(p.phone) LIKE LOWER(?) OR
            LOWER(e.email) LIKE LOWER(?) OR
            LOWER(c.message) LIKE LOWER(?)
        )"""
        search_pattern = f"%{q}%"
        params.extend([search_pattern] * 8)

    sql += " GROUP BY a.id ORDER BY a.id ASC;"

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    agencies = []
    for r in rows:
        agency = dict(r)
        
        # Telefonlar
        cursor.execute("SELECT phone FROM agency_phones WHERE agency_id = ?", (agency['id'],))
        agency['phones'] = [p['phone'] for p in cursor.fetchall()]
        
        # E-postalar
        cursor.execute("SELECT email FROM agency_emails WHERE agency_id = ?", (agency['id'],))
        agency['emails'] = [e['email'] for e in cursor.fetchall()]

        # Web siteleri & kaynaklar
        cursor.execute("SELECT url FROM agency_websites WHERE agency_id = ?", (agency['id'],))
        urls = [w['url'] for w in cursor.fetchall()]
        agency['websites'] = urls

        sources = []
        if any('companywall.rs' in u for u in urls) or agency.get('pib'):
            sources.append('companywall')
        if any('indomio.rs' in u for u in urls):
            sources.append('indomio')
        if any('nekretnine.rs' in u for u in urls) or not sources:
            sources.append('nekretnine')
        agency['sources'] = sources

        agencies.append(agency)

    conn.close()
    return jsonify(agencies)


@app.route("/api/agencies/<int:agency_id>", methods=["GET"])
def get_agency_detail(agency_id: int):
    """Acente Detayları & İletişim Geçmişi"""
    details = db.get_agency_details(agency_id)
    if not details:
        return jsonify({"error": "Acente bulunamadı"}), 404
    return jsonify(details)


@app.route("/api/agencies/<int:agency_id>/communications", methods=["POST"])
def add_communication(agency_id: int):
    """Yeni İletişim Kaydı Ekleme"""
    data = request.json or {}
    sender = data.get("sender", "Atil Bilge ORUM")
    recipient = data.get("recipient", "")
    message = data.get("message", "").strip()
    channel = data.get("channel", "EMAIL")
    status = data.get("status", "SENT")

    if not message:
        return jsonify({"error": "Mesaj metni zorunludur"}), 400

    details = db.get_agency_details(agency_id)
    if not details:
        return jsonify({"error": "Acente bulunamadı"}), 404

    comm_id = db.add_communication(
        agency_id=agency_id,
        sender=sender,
        recipient=recipient or details['name'],
        message=message,
        channel=channel,
        status=status
    )
    return jsonify({"success": True, "communication_id": comm_id}), 201


@app.route("/api/agencies/<int:agency_id>/status", methods=["PATCH"])
def update_agency_status(agency_id: int):
    """Acente Statüsü Güncelleme"""
    data = request.json or {}
    new_status = data.get("status", "").strip()
    if not new_status:
        return jsonify({"error": "Statü zorunludur"}), 400

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE agencies SET status = ? WHERE id = ?", (new_status, agency_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/communications", methods=["GET"])
def get_all_communications():
    """Tüm İletişim Akışı (Feed)"""
    channel = request.args.get("channel", "").strip()
    status = request.args.get("status", "").strip()
    period = request.args.get("period", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    sql = """
        SELECT c.*, a.name as agency_name, a.city as agency_city, a.ref_code
        FROM communications c
        JOIN agencies a ON c.agency_id = a.id
        WHERE 1=1
    """
    params = []
    if channel:
        sql += " AND c.channel = ?"
        params.append(channel)
    if status:
        sql += " AND c.status = ?"
        params.append(status)

    now = datetime.now()

    if period == "today":
        today_str = now.strftime("%Y-%m-%d")
        sql += " AND c.date >= ?"
        params.append(today_str)
    elif period == "yesterday":
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")
        sql += " AND c.date >= ? AND c.date < ?"
        params.append(yesterday_str)
        params.append(today_str)
    elif period == "3days":
        dt_str = (now - timedelta(days=3)).strftime("%Y-%m-%d")
        sql += " AND c.date >= ?"
        params.append(dt_str)
    elif period == "7days":
        dt_str = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        sql += " AND c.date >= ?"
        params.append(dt_str)
    elif period == "30days":
        dt_str = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        sql += " AND c.date >= ?"
        params.append(dt_str)
    elif period == "custom" or (start_date or end_date):
        if start_date:
            sql += " AND c.date >= ?"
            params.append(f"{start_date}T00:00:00")
        if end_date:
            sql += " AND c.date <= ?"
            params.append(f"{end_date}T23:59:59")
        
    sql += " ORDER BY c.date DESC;"
    cursor.execute(sql, params)
    comms = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(comms)


@app.route("/api/referrals", methods=["GET"])
def get_referrals_overview():
    """Referans Sistemi ve Kod Yönetimi"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.name, a.city, a.ref_code, a.status,
               (SELECT COUNT(*) FROM referrals r WHERE r.referrer_agency_id = a.id) as referral_count
        FROM agencies a
        ORDER BY referral_count DESC, a.id ASC;
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/sync-emails", methods=["POST"])
def sync_emails_route():
    """Gmail e-postalarını senkronize eder."""
    try:
        new_count, last_sync = db.sync_emails_from_gmail()
        return jsonify({"success": True, "new_messages": new_count, "last_sync": last_sync})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "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")
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"
TRANSLATION_CACHE = {}


def clean_text_for_llm(raw_text: str) -> str:
    """Mesaj metninden HTML etiketi ve stilleri temizleyerek sade metin döner."""
    if "<" in raw_text and ">" in raw_text:
        import re
        clean = re.sub(r"<style[^>]*>.*?</style>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<script[^>]*>.*?</script>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
    return raw_text.strip()


@app.route("/api/translate", methods=["POST"])
def translate_text_route():
    """NVIDIA NIM API kullanarak mesaj metnini Türkçe'ye çevirir (Önbellekli & Otomatik Tekrar Denemeli)."""
    import urllib.request
    import time

    data = request.json or {}
    raw_text = data.get("text", "").strip()
    if not raw_text:
        return jsonify({"error": "Çevrilecek metin bulunamadı."}), 400

    plain_text = clean_text_for_llm(raw_text)[:2000]

    # Check cache
    if plain_text in TRANSLATION_CACHE:
        return jsonify({
            "translated_text": TRANSLATION_CACHE[plain_text],
            "model": NVIDIA_MODEL,
            "cached": True
        })

    payload = {
        "model": NVIDIA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a professional translator. Translate the given Serbian or English text into natural, fluent Turkish. Output ONLY the Turkish translation, no intro or notes."
            },
            {"role": "user", "content": plain_text}
        ],
        "temperature": 0.2,
        "max_tokens": 1024
    }

    last_error = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                translated = res_data["choices"][0]["message"]["content"].strip()
                TRANSLATION_CACHE[plain_text] = translated
                return jsonify({"translated_text": translated, "model": NVIDIA_MODEL, "attempt": attempt})
        except Exception as e:
            last_error = str(e)
            print(f"NVIDIA NIM Translation Attempt {attempt} failed: {e}")
            time.sleep(1)

    return jsonify({"error": f"Çeviri zaman aşımına uğradı veya servis yanıt vermedi. ({last_error})"}), 500


# ─── E-POSTA KAMPANYA SİSTEMİ & WORKER ───────────────────────────────────────

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "atilbilge@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "ijxz xjsk elcx xtmt").replace(" ", "")

CAMPAIGN_PROGRESS = {}


def process_email_template(template_str, agency, recipient_email=None, base_url=None, lang=None):
    result = template_str or ""
    agency_name = agency.get("name", "") if agency else ""
    city = agency.get("city", "") if agency else ""
    ref_code = agency.get("ref_code", "") if agency else ""
    address = agency.get("address", "") if agency else ""

    email_for_unsub = recipient_email or (agency.get("emails", [""])[0] if agency and agency.get("emails") else "info@example.com")
    
    if base_url:
        host = base_url.rstrip("/")
    else:
        host = os.environ.get("APP_HOST", "http://stanomer.online").rstrip("/")

    valid_langs = ["TR", "EN", "RU", "SR_LAT", "SR_CYR"]
    clean_lang = lang.strip().upper() if (lang and lang.strip().upper() in valid_langs) else "SR_LAT"

    unsub_url = f"{host}/unsubscribe?email={urllib.parse.quote(email_for_unsub)}&lang={clean_lang}"

    import re
    result = re.sub(r'(?i)AGENCY_NAME_PLACEHOLDER', agency_name, result)
    result = re.sub(r'(?i)\{\{\s*name\s*\}\}', agency_name, result)
    result = re.sub(r'(?i)\{\{\s*agency_name\s*\}\}', agency_name, result)
    result = re.sub(r'(?i)\{\{\s*city\s*\}\}', city, result)
    result = re.sub(r'(?i)\{\{\s*ref_code\s*\}\}', ref_code, result)
    result = re.sub(r'(?i)\{\{\s*address\s*\}\}', address, result)
    result = re.sub(r'(?i)\{\{\s*unsubscribe_url\s*\}\}', unsub_url, result)
    return result


def send_campaign_worker(campaign_id, test_email=None):
    camp = db.get_campaign(campaign_id)
    if not camp:
        return

    sender_name = camp.get("sender_name") or "Stanomer Ekibi"
    subject_raw = camp.get("subject") or "Stanomer"
    body_raw = camp.get("body_html") or ""
    target_filter_str = camp.get("target_filter_json") or "{}"

    if test_email:
        target_agencies = [{
            "id": 0,
            "name": "Test Acente (Önizleme)",
            "city": "Beograd",
            "ref_code": "REF-TEST",
            "address": "Test Adresi",
            "emails": [test_email]
        }]
    else:
        target_agencies = db.get_campaign_target_agencies(target_filter_str)

    total = len(target_agencies)
    progress_key = f"test_{campaign_id}" if test_email else str(campaign_id)
    CAMPAIGN_PROGRESS[progress_key] = {
        "total": total,
        "sent": 0,
        "failed": 0,
        "status": "RUNNING",
        "current_agency": "",
        "logs": []
    }

    if not test_email:
        db.update_campaign(campaign_id, status="RUNNING")

    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    except Exception as e:
        CAMPAIGN_PROGRESS[progress_key]["status"] = "FAILED"
        CAMPAIGN_PROGRESS[progress_key]["error"] = f"SMTP Bağlantı hatası: {str(e)}"
        if not test_email:
            db.update_campaign(campaign_id, status="FAILED")
        return

    sent_count = 0
    failed_count = 0

    camp_lang = camp.get("lang") or "SR_LAT"

    for ag in target_agencies:
        if CAMPAIGN_PROGRESS[progress_key].get("stop_requested") or CAMPAIGN_PROGRESS[progress_key].get("status") == "STOPPED":
            CAMPAIGN_PROGRESS[progress_key]["logs"].append("🛑 Gönderim işlemi kullanıcı tarafından durduruldu.")
            CAMPAIGN_PROGRESS[progress_key]["status"] = "STOPPED"
            if not test_email:
                db.update_campaign(campaign_id, status="COMPLETED")
            break

        emails = ag.get("emails", [])
        if not emails:
            continue

        active_emails = [e for e in emails if not db.is_unsubscribed(e)]
        agency_name = ag.get("name", "")

        if not active_emails:
            CAMPAIGN_PROGRESS[progress_key]["logs"].append(f"⚠️ Atlandı (Abonelikten çıkmış): {agency_name} ({', '.join(emails)})")
            continue

        CAMPAIGN_PROGRESS[progress_key]["current_agency"] = agency_name
        first_email = active_emails[0]
        recipient_str = ", ".join(active_emails)

        processed_subject = process_email_template(subject_raw, ag, recipient_email=first_email, lang=camp_lang)
        processed_body = process_email_template(body_raw, ag, recipient_email=first_email, lang=camp_lang)

        # Şablonda unsubscribe bağlantısı kullanılmamışsa otomatik altbilgi ekle
        if "{{unsubscribe_url}}" not in body_raw and "unsubscribe" not in processed_body.lower() and "odjav" not in processed_body.lower():
            host = os.environ.get("APP_HOST", "http://stanomer.online").rstrip("/")
            unsub_url = f"{host}/unsubscribe?email={urllib.parse.quote(first_email)}&lang={camp_lang}"
            footer_html = f"""
            <div style="margin-top: 35px; text-align: center; font-size: 12px; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 15px; font-family: sans-serif;">
                Ovo obaveštenje vam šalje Stanomer.<br>
                Ako ne želite da primate više obaveštenja, <a href="{unsub_url}" style="color: #6b7280; text-decoration: underline;">odjavite se ovde (Abonelikten Çık)</a>.
            </div>
            """
            processed_body += footer_html

        msg = MIMEMultipart("alternative")
        msg["Subject"] = processed_subject
        msg["From"] = f"{sender_name} <{GMAIL_ADDRESS}>"
        msg["To"] = recipient_str
        msg.attach(MIMEText(processed_body, "html", "utf-8"))

        try:
            smtp.sendmail(GMAIL_ADDRESS, active_emails, msg.as_string())
            sent_count += 1
            CAMPAIGN_PROGRESS[progress_key]["sent"] = sent_count
            CAMPAIGN_PROGRESS[progress_key]["logs"].append(f"✅ Gönderildi: {agency_name} ({recipient_str})")

            if not test_email and ag.get("id"):
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO communications (agency_id, date, sender, recipient, message, channel, status, campaign_id)
                    VALUES (?, ?, ?, ?, ?, 'EMAIL', 'SENT', ?)
                """, (ag["id"], datetime.now().isoformat(), GMAIL_ADDRESS, recipient_str, processed_body, campaign_id))
                cursor.execute("UPDATE agencies SET status = 'SENT', updated_at = ? WHERE id = ?", (datetime.now().isoformat(), ag["id"]))
                conn.commit()
                conn.close()

        except Exception as e:
            failed_count += 1
            CAMPAIGN_PROGRESS[progress_key]["failed"] = failed_count
            CAMPAIGN_PROGRESS[progress_key]["logs"].append(f"❌ Hata: {agency_name}: {str(e)}")

        time.sleep(2)

    smtp.quit()
    CAMPAIGN_PROGRESS[progress_key]["status"] = "COMPLETED"
    if not test_email:
        db.update_campaign(campaign_id, status="COMPLETED")


@app.route("/api/campaigns", methods=["GET"])
def list_campaigns():
    """Tüm kampanyaları getirir."""
    try:
        camps = db.get_campaigns()
        return jsonify(camps)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns", methods=["POST"])
def create_campaign_route():
    """Yeni kampanya oluşturur."""
    data = request.json or {}
    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    body_html = data.get("body_html", "").strip()
    sender_name = data.get("sender_name", "Stanomer Ekibi").strip()
    sender_email = data.get("sender_email", GMAIL_ADDRESS).strip()
    target_filter = data.get("target_filter", {})

    if not name or not subject or not body_html:
        return jsonify({"error": "Kampanya adı, konu ve HTML gövdesi zorunludur."}), 400

    target_filter_json = json.dumps(target_filter) if isinstance(target_filter, dict) else str(target_filter)
    lang = data.get("lang", "SR_LAT")
    try:
        camp_id = db.create_campaign(name, subject, body_html, sender_name, sender_email, target_filter_json, lang=lang)
        return jsonify({"success": True, "id": camp_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/<int:campaign_id>", methods=["GET"])
def get_campaign_route(campaign_id):
    """Kampanya detayını getirir."""
    camp = db.get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "Kampanya bulunamadı."}), 404
    return jsonify(camp)


@app.route("/api/campaigns/<int:campaign_id>", methods=["PUT"])
def update_campaign_route(campaign_id):
    """Kampanyayı günceller."""
    data = request.json or {}
    target_filter = data.get("target_filter")
    target_filter_json = json.dumps(target_filter) if isinstance(target_filter, dict) else target_filter
    lang = data.get("lang")

    try:
        success = db.update_campaign(
            campaign_id,
            name=data.get("name"),
            subject=data.get("subject"),
            body_html=data.get("body_html"),
            sender_name=data.get("sender_name"),
            sender_email=data.get("sender_email"),
            target_filter_json=target_filter_json,
            lang=lang,
            status=data.get("status")
        )
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/<int:campaign_id>", methods=["DELETE"])
def delete_campaign_route(campaign_id):
    """Kampanyayı siler."""
    try:
        db.delete_campaign(campaign_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/preview-audience", methods=["POST"])
def preview_audience():
    """Filtreye uyan acente listesini ve toplam sayıyı döndürür."""
    data = request.json or {}
    target_filter = data.get("target_filter", {})
    try:
        target_agencies = db.get_campaign_target_agencies(target_filter)
        return jsonify({
            "total": len(target_agencies),
            "agencies": target_agencies[:100]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/preview-html", methods=["POST"])
def preview_email_html():
    """E-posta HTML şablonunun ve konusunun değişkenlerle işlenmiş halini döndürür."""
    data = request.json or {}
    subject_raw = data.get("subject", "")
    body_raw = data.get("body_html", "")
    agency_id = data.get("agency_id")
    lang = data.get("lang", "SR_LAT")

    agency = None
    if agency_id:
        try:
            agency = db.get_agency(agency_id)
        except Exception:
            agency = None

    if not agency:
        agency = {
            "id": 0,
            "name": "Beoexpert Nekretnine d.o.o.",
            "city": "Beograd",
            "ref_code": "REF-849201",
            "address": "Knez Mihailova 12, Beograd",
            "emails": ["info@beoexpert.rs"]
        }

    processed_subject = process_email_template(subject_raw, agency, lang=lang)
    processed_body = process_email_template(body_raw, agency, lang=lang)

    return jsonify({
        "subject": processed_subject,
        "body_html": processed_body,
        "agency": agency
    })



@app.route("/api/campaigns/<int:campaign_id>/send", methods=["POST"])
def send_campaign_route(campaign_id):
    """Kampanya gönderimini başlatır (veya test mailleri gönderir)."""
    data = request.json or {}
    test_email = data.get("test_email", "").strip()

    camp = db.get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "Kampanya bulunamadı."}), 404

    t = threading.Thread(target=send_campaign_worker, args=(campaign_id, test_email if test_email else None), daemon=True)
    t.start()

    return jsonify({"success": True, "message": "Gönderim işlemi başlatıldı."})


@app.route("/api/campaigns/<int:campaign_id>/progress", methods=["GET"])
def campaign_progress(campaign_id):
    """Kampanya gönderim durumunu döndürür."""
    test_mode = request.args.get("test", "0") == "1"
    key = f"test_{campaign_id}" if test_mode else str(campaign_id)

    progress = CAMPAIGN_PROGRESS.get(key, {"status": "NOT_STARTED", "total": 0, "sent": 0, "failed": 0, "logs": []})
    return jsonify(progress)


@app.route("/api/campaigns/<int:campaign_id>/stop", methods=["POST"])
def stop_campaign(campaign_id: int):
    """Aktif kampanya gönderimini durdurur."""
    key = str(campaign_id)
    test_key = f"test_{campaign_id}"
    for k in [key, test_key]:
        if k in CAMPAIGN_PROGRESS:
            CAMPAIGN_PROGRESS[k]["stop_requested"] = True
            CAMPAIGN_PROGRESS[k]["status"] = "STOPPED"
            CAMPAIGN_PROGRESS[k]["logs"].append("🛑 Durdurma isteği alındı...")

    db.update_campaign(campaign_id, status="COMPLETED")
    return jsonify({"success": True, "message": "Gönderim işlemi durduruldu."})


@app.route("/api/campaigns/<int:campaign_id>/communications", methods=["GET"])
def get_campaign_communications(campaign_id: int):
    """Kampanyaya ait tüm e-posta iletişim zincirini döndürür."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, a.name as agency_name, a.city as agency_city, a.ref_code
        FROM communications c
        LEFT JOIN agencies a ON c.agency_id = a.id
        WHERE c.campaign_id = ?
        ORDER BY c.id DESC
    """, (campaign_id,))
    rows = cursor.fetchall()
    conn.close()
    
    logs = [dict(r) for r in rows]
    return jsonify({
        "campaign_id": campaign_id,
        "total": len(logs),
        "logs": logs
    })


@app.route("/unsubscribe", methods=["GET"])
def unsubscribe_page():
    """Kamuya açık e-posta abonelikten çıkma sayfası"""
    email = request.args.get("email", "").strip()
    confirm = request.args.get("confirm", "0") == "1"

    already_unsubbed = False
    if email:
        already_unsubbed = db.is_unsubscribed(email)

    success = False
    if confirm and email and not already_unsubbed:
        success = db.add_unsubscribe(email, reason="Web sayfasından odjava")

    is_done = success or already_unsubbed

    status_html = ""
    if is_done:
        status_html = f"""
        <div class="success-box">
            <div style="font-size: 32px; margin-bottom: 8px;">✅</div>
            <strong>Vaša e-mail adresa je uspešno odjavljena.</strong><br>
            <span style="font-size: 13px; color: #065f46; font-family: monospace; display: block; margin-top: 6px;">{email}</span>
            <p style="font-size: 12px; color: #047857; margin-top: 10px; margin-bottom: 0;">Ubuduće nećete primati naša obaveštenja.<br>(Bu e-posta adresi bülten listemizden çıkarılmıştır.)</p>
        </div>
        """
    elif email:
        status_html = f"""
        <h2>Odjava sa e-mail liste / Abonelikten Çıkış</h2>
        <p>Da li ste sigurni da želite da se odjavite sa e-mail obaveštenja za adresu:<br><br><span class="email-badge">{email}</span></p>
        <form action="/unsubscribe" method="GET" style="margin-top: 20px;">
            <input type="hidden" name="email" value="{email}">
            <input type="hidden" name="confirm" value="1">
            <button type="submit" class="btn">Potvrdi odjavu / Odjavi se</button>
        </form>
        """
    else:
        status_html = """
        <h2>Odjava sa e-mail liste</h2>
        <p style="color: #ef4444;">Nevažeći zahtev. E-mail adresa nije navedena.</p>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="sr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Odjava sa e-mail obaveštenja - Stanomer</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #f3f4f6;
            color: #1f2937;
            margin: 0;
            padding: 40px 15px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 80vh;
        }}
        .card {{
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08);
            max-width: 480px;
            width: 100%;
            padding: 36px 28px;
            text-align: center;
        }}
        .logo {{
            font-size: 26px;
            font-weight: 800;
            color: #3b82f6;
            margin-bottom: 24px;
            letter-spacing: -0.5px;
        }}
        h2 {{
            font-size: 20px;
            margin-bottom: 12px;
            color: #111827;
        }}
        p {{
            font-size: 14px;
            color: #4b5563;
            line-height: 1.6;
            margin-bottom: 20px;
        }}
        .email-badge {{
            background: #eff6ff;
            color: #1d4ed8;
            padding: 6px 14px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 14px;
            font-weight: 600;
            display: inline-block;
            word-break: break-all;
        }}
        .btn {{
            background: #ef4444;
            color: #ffffff;
            border: none;
            padding: 12px 28px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: background 0.2s;
        }}
        .btn:hover {{
            background: #dc2626;
        }}
        .success-box {{
            background: #ecfdf5;
            color: #047857;
            border: 1px solid #a7f3d0;
            padding: 24px;
            border-radius: 12px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">Stanomer</div>
        {status_html}
    </div>
</body>
</html>"""
    return html_content


@app.route("/api/unsubscribe", methods=["POST"])
def api_unsubscribe():
    """Kamuya açık e-posta abonelikten çıkma API endpoint'i"""
    data = request.json or {}
    email = data.get("email", "").strip()
    reason = data.get("reason", "API üzerinden odjava")

    if not email:
        return jsonify({"error": "E-posta adresi zorunludur."}), 400

    success = db.add_unsubscribe(email, reason=reason)
    return jsonify({"success": success, "email": email, "message": "Abonelikten çıkarıldı."})


@app.route("/api/unsubscribes", methods=["GET"])
def list_unsubscribes():
    """Abonelikten çıkan e-posta adreslerini döner (Admin)."""
    try:
        unsubs = db.get_unsubscribed_emails()
        return jsonify(unsubs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/unsubscribes/<path:email>", methods=["DELETE"])
def remove_unsubscribe_route(email):
    """E-posta adresini abonelikten çıkanlar listesinden siler (Yeniden Abone Yapar)."""
    try:
        success = db.remove_unsubscribe(email)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/unsubscribes/sync-supabase", methods=["POST"])
def sync_unsubscribes_from_supabase():
    """Supabase email_unsubscribes tablosundan local unsubscribes tablosuna upsert sync yapar."""
    try:
        import urllib.request
        data = request.get_json(silent=True) or {}
        SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ustcsvvkzsmsgzbptvpm.supabase.co")
        SUPABASE_KEY = data.get("service_role_key") or data.get("apiKey") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not SUPABASE_KEY:
            return jsonify({"error": "Supabase Service Role Key gereklidir."}), 400

        api_url = f"{SUPABASE_URL}/rest/v1/email_unsubscribes?select=email,unsubscribed_at"
        req = urllib.request.Request(api_url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            records = json.loads(resp.read().decode())

        result = db.upsert_unsubscribes_bulk(records, source="Supabase Sync")
        return jsonify({
            "success": True,
            "fetched": len(records),
            "inserted": result["inserted"],
            "skipped": result["skipped"],
            "errors": result["errors"],
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return jsonify({"error": f"Supabase HTTP {e.code}: {body}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"🚀 Stanomer Web Dashboard Başlatılıyor: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
