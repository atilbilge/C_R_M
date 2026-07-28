#!/usr/bin/env python3
"""
Stanomer Acente CRM - Web Dashboard Backend (Flask API)
------------------------------------------------------
`acenteler.db` SQLite veritabanına doğrudan bağlı REST API ve Web Arayüzü sunucusu.
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
import db

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Veritabanını başlat
db.init_db()


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
    source = request.args.get("source", "").strip()
    has_phone = request.args.get("has_phone", "").strip()  # 'yes' | 'no'
    has_email = request.args.get("has_email", "").strip()  # 'yes' | 'no'
    q = request.args.get("q", "").strip()

    conn = db.get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT DISTINCT a.id, a.name, a.city, a.address, a.pib, a.mb, a.status, a.ref_code
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"🚀 Stanomer Web Dashboard Başlatılıyor: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
