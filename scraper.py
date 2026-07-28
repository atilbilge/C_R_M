#!/usr/bin/env python3
"""
Nekretnine.rs Emlak Acenteleri Kazıma ve Mesaj Otomasyonu (Production-Ready)
-----------------------------------------------------------------------------------
Bu betik 4 farklı çalışma moduna sahiptir:

1. Kazıma Modu (`--mode scrape`):
   Belirtilen bölge URL'sindeki acenteleri tarar ve CSV dosyasına kaydeder.
   Örn: `python3 scraper.py https://www.nekretnine.rs/en/agencije-za-nekretnine/novi-sad/ -o novi-sad.csv`

2. Otomatik Mesaj Modu (`--mode message`):
   CSV'deki veya verilen URL'deki acenteler için form alanlarını otomatik doldurur.
   `--send` eklenirse doğrudan gönderir; eklenmezse dry-run (test) modunda çalışır.

3. Manuel / Yarı Otomatik Mesaj Modu (`--mode manual`):
   Ekranlı tarayıcı (headful) açılır. Her acente için profil açılır, 'MESSAGE' modalı tıkla-
   nır ve mesaj/iletişim alanları dolu şekilde kullanıcının önüne getirilir.
   - Kullanıcı 'Send' butonuna tıkladığında veya gönderim yapıldığında anında algılanır.
   - Gönderilen acente `sent_messages_log.json` kütüğüne yazılır (tekrar gönderim engellenir).
   - Gönderim sonrası otomatik olarak sıradaki acenteye geçer ve onun popup'ını açar.

4. Yavaş Otomatik Mesaj Modu (`--mode slow-auto`):
   Ekranlı tarayıcı açılır. Her acente için profil açılır, 'MESSAGE' modalı tıklanır,
   form alanları ve tüm onay kutuları (gizlilik, yetişkinlik/adult checkbox) işaretlenir.
   2 ila 10 saniye arasında rastgele bir süre bekledikten sonra mesajı otomatik gönderir.
"""

import os
import sys

# ----------------------------------------------------------------------
# OTO-SANAL ORTAM AKTİVASYONU (Auto-reexec with .venv)
# ----------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(SCRIPT_DIR, ".venv", "bin", "python")

if os.path.exists(VENV_PYTHON) and os.path.abspath(sys.executable) != os.path.abspath(VENV_PYTHON):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

# ----------------------------------------------------------------------
# İTHALATLAR
# ----------------------------------------------------------------------
import time
import random
import logging
import csv
import json
import re
import argparse
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd

try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False

try:
    from playwright.sync_api import sync_playwright, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# ----------------------------------------------------------------------
# YAPILANDIRMA & PARAMETRELER
# ----------------------------------------------------------------------
CONFIG = {
    "START_URL": "https://www.nekretnine.rs/en/agencije-za-nekretnine/severna-backa-okrug/",
    "OUTPUT_CSV": "nekretnine_acenteler.csv",
    "SENT_LOG_FILE": "sent_messages_log.json",
    "BUILD_IDS": ["5K-Y4Pf0Q9WcanokJVVbd"],
    "MAX_PAGES": 20,
    "DELAY_MIN": 1.5,
    "DELAY_MAX": 3.0,
    "USER_DATA_DIR": "./.browser_profile",
}

# Mesaj Gönderen İletişim Bilgileri
SENDER_INFO = {
    "NAME": "Atil Bilge ORUM",
    "EMAIL": "atilbilge@gmail.com",
    "PHONE": "+381 61 6036 556"
}

# Parametrik Mesaj Şablonu ({agency_name} otomatik doldurulur)
MESSAGE_TEMPLATE = """Poštovani tim {agency_name},

Nakon što se ugovor o zakupu potpiše, praćenje mesečne kirije i arhiviranje računa između stanodavca i zakupca često ostaje neformalizovano, što ponekad dovodi do nesporazuma ili kašnjenja.

Naš digitalni asistent, Stanomer, rešava upravo taj problem: automatizuje naplatu kirije i arhiviranje računa između stanodavaca i zakupaca, uz potpuno besplatan pristup za vlasnike nekretnina iz vašeg portfolija i njihove zakupce.

Preporukom Stanomera vašim klijentima nakon završenog procesa iznajmljivanja, obezbeđujete im:

Praćenje bez napora: upravljanje kirijom i računima kroz asistenta sa minimalističkim, modernim i preglednim interfejsom.

Maksimalnu privatnost: zahvaljujući "privacy-first" arhitekturi (lokalno skladištenje), finansijski podaci ostaju isključivo na uređajima korisnika, bez skladištenja na spoljnim serverima.

Dugoročan odnos s klijentima: vaša usluga ne prestaje predajom ključeva, već nastavlja da donosi vrednost i nakon završetka zakupa, što jača poverenje i verovatnoću ponovne saradnje.

Platforma je potpuno besplatna za vaše klijente i dostupna odmah na stanomer.online.

Ako želite da ovu dodatnu vrednost ponudite svom portfoliju, rado ću vam poslati gotov šablon poruke koji možete proslediti klijentima za par sekundi prilikom predaje ključeva, ili, ako vam više odgovara, možemo zakazati kratak poziv od 10-15 minuta da vam pokažem kako platforma funkcioniše u praksi.

Srdačan pozdrav,
Atıl Bilge
Osnivač, Stanomer"""

# ----------------------------------------------------------------------
# LOGGING YAPILANDIRMASI
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("NekretnineScraper")


def random_sleep(min_sec: float = CONFIG["DELAY_MIN"], max_sec: float = CONFIG["DELAY_MAX"]):
    """Hedef sunucuyu yormamak için rastgele gecikme ekler."""
    time.sleep(random.uniform(min_sec, max_sec))


def prepare_agency_message(agency_name: str) -> str:
    """Acente adına özel parametrik mesaj metnini hazırlar."""
    return MESSAGE_TEMPLATE.format(agency_name=agency_name.strip())


# ----------------------------------------------------------------------
# GÖNDERİLEN MESAJ LOG YÖNETİMİ (sent_messages_log.json)
# ----------------------------------------------------------------------
def load_sent_log(log_path: str = CONFIG["SENT_LOG_FILE"]) -> Dict[str, dict]:
    """Daha önce mesaj gönderilmiş acentelerin kütüğünü yükler."""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.warning(f"Log kütüğü okuma uyarısı: {e}")
    return {}


def record_sent_agency(url: str, agency_name: str, log_path: str = CONFIG["SENT_LOG_FILE"]):
    """Mesaj gönderilen acenteyi sent_messages_log.json dosyasına ve acenteler.db veritabanına ekler."""
    sent_dict = load_sent_log(log_path)
    now_iso = datetime.now().isoformat()
    sent_dict[url] = {
        "agency_name": agency_name,
        "sent_at": now_iso,
        "status": "SENT"
    }
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(sent_dict, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ [{agency_name}] 'sent_messages_log.json' dosyasına BAŞARIYLA KAYDEDİLDİ!")
    except Exception as e:
        logger.error(f"Log kaydedilirken hata: {e}")

    # SQLite Veritabanına (acenteler.db) Ekleme
    try:
        import db
        agency_id = db.add_or_get_agency(
            name=agency_name,
            profile_url=url,
            status="SENT"
        )
        msg_text = format_message(agency_name)
        sender_info = f"{SENDER_INFO['NAME']} ({SENDER_INFO['EMAIL']})"
        db.add_communication(
            agency_id=agency_id,
            sender=sender_info,
            recipient=agency_name or url,
            message=msg_text,
            date=now_iso,
            channel="NEKRETNINE_FORM",
            status="SENT"
        )
        logger.info(f"✅ [{agency_name}] acenteler.db veritabanına iletişim geçmişi eklendi!")
    except Exception as e:
        logger.error(f"SQLite veritabanına kaydedilirken hata: {e}")


def is_already_sent(url: str, log_path: str = CONFIG["SENT_LOG_FILE"]) -> bool:
    """Acenteye daha önce mesaj gönderilip gönderilmediğini JSON ve SQLite DB üzerinden kontrol eder."""
    # 1. sent_messages_log.json kontrolü
    sent_dict = load_sent_log(log_path)
    if url in sent_dict:
        return True

    # 2. acenteler.db veritabanı kontrolü
    try:
        import db
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.status FROM agencies a
            JOIN agency_websites w ON a.id = w.agency_id
            WHERE w.url = ? AND a.status IN ('SENT', 'RESPONDED', 'CONTACTED')
        """, (url.strip(),))
        row = cursor.fetchone()
        conn.close()
        if row:
            return True
    except Exception:
        pass

    return False


# ======================================================================
# BÖLÜM 1: CANLI VERİ KAZIMA (SCRAPING)
# ======================================================================
def fetch_live_next_json(region_slug: str, page_num: int = 1) -> Optional[dict]:
    """Next.js veri API'si üzerinden canlı JSON verisini çeker."""
    if not HAS_CFFI:
        return None

    for build_id in CONFIG["BUILD_IDS"]:
        if page_num == 1:
            json_url = f"https://www.nekretnine.rs/_next/data/{build_id}/en/agencije-za-nekretnine/{region_slug}.json"
        else:
            json_url = f"https://www.nekretnine.rs/_next/data/{build_id}/en/agencije-za-nekretnine/{region_slug}.json?pag={page_num}"

        try:
            r = cffi_requests.get(
                json_url,
                impersonate="chrome124",
                headers={
                    "accept": "*/*",
                    "accept-language": "en-US,en;q=0.9",
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                },
                timeout=15
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"JSON endpoint denemesi ({json_url}): {e}")

    return None


def fetch_agency_detail_live(agency_id: str) -> Optional[dict]:
    """Acente detay verisini canlı Next.js API'si üzerinden çeker."""
    if not HAS_CFFI:
        return None

    for build_id in CONFIG["BUILD_IDS"]:
        json_url = f"https://www.nekretnine.rs/_next/data/{build_id}/en/agencije-za-nekretnine/{agency_id}.json"
        try:
            r = cffi_requests.get(
                json_url,
                impersonate="chrome124",
                headers={
                    "accept": "*/*",
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                },
                timeout=15
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Acente detay JSON denemesi ({json_url}): {e}")

    return None


def crawl_live_agencies(start_url: str) -> List[Dict[str, str]]:
    """Bölge sayfasındaki tüm acenteleri sorgular ve detaylarını çekerek dönüştürür."""
    parsed = urlparse(start_url)
    slug = parsed.path.strip("/").split("/")[-1]

    extracted_agencies = []
    page_num = 1

    logger.info(f"Canlı veri kazıma başlatıldı (Bölge: '{slug}')...")

    while page_num <= CONFIG["MAX_PAGES"]:
        logger.info(f"Sayfa {page_num} sorgulanıyor...")
        data = fetch_live_next_json(slug, page_num)

        if not data:
            logger.warning("Canlı JSON yanıtı alınamadı veya son sayfaya ulaşıldı.")
            break

        queries = data.get("pageProps", {}).get("dehydratedState", {}).get("queries", [])
        results = []

        for q in queries:
            if "agency-list-search" in str(q.get("queryHash", "")):
                results = q.get("state", {}).get("data", {}).get("results", [])
                break

        if not results:
            logger.info("Bu sayfada daha fazla acente bulunamadı.")
            break

        logger.info(f"Sayfa {page_num}: {len(results)} acente canlı olarak çekildi.")

        for item in results:
            aid = str(item.get("id"))
            display_name = item.get("displayName", "N/A")
            address = item.get("address", "N/A")
            agency_url = item.get("agencyUrl", f"https://www.nekretnine.rs/en/agencije-za-nekretnine/{aid}/")

            phones = [p.get("value") for p in item.get("phones", []) if p.get("value")]
            phone_str = ", ".join(phones) if phones else "N/A"

            email_str = "N/A"
            detail_data = fetch_agency_detail_live(aid)
            if detail_data:
                d_queries = detail_data.get("pageProps", {}).get("dehydratedState", {}).get("queries", [])
                for dq in d_queries:
                    sdata = dq.get("state", {}).get("data", {})
                    if isinstance(sdata, dict) and "listing" in sdata:
                        listings = sdata.get("listing", [])
                        if listings:
                            adv = listings[0].get("realEstate", {}).get("advertiser", {}).get("agency", {})
                            if adv.get("email"):
                                email_str = adv.get("email")

            extracted_agencies.append({
                "Acente Adı": display_name,
                "Adres": address,
                "Telefon Numarası": phone_str,
                "E-posta Adresi": email_str,
                "Profil Linki": agency_url
            })

            random_sleep(0.5, 1.0)

        page_num += 1

    return extracted_agencies


def export_to_csv(data_list: List[Dict[str, str]], output_file: str):
    """Çekilen canlı verileri CSV dosyasına ve acenteler.db veritabanına kaydeder."""
    fieldnames = ["Acente Adı", "Adres", "Telefon Numarası", "E-posta Adresi", "Profil Linki"]

    df = pd.DataFrame(data_list)
    for col in fieldnames:
        if col not in df.columns:
            df[col] = "N/A"
    df = df[fieldnames]
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    logger.info(f"İşlem Başarılı! Toplam {len(data_list)} acente canlı verisi '{output_file}' dosyasına yazıldı.")

    # SQLite Veritabanı Otomatik Güncelleme
    try:
        import db
        saved_db_count = 0
        for item in data_list:
            name = item.get("Acente Adı", "").strip()
            if not name or name == "N/A":
                continue
            address = item.get("Adres", "").strip()
            phone_raw = item.get("Telefon Numarası", "").strip()
            email_raw = item.get("E-posta Adresi", "").strip()
            profile_url = item.get("Profil Linki", "").strip()

            agency_id = db.add_or_get_agency(
                name=name,
                address=address if address != "N/A" else "",
                profile_url=profile_url if profile_url != "N/A" else ""
            )

            if phone_raw and phone_raw != "N/A":
                for p in [x.strip() for x in phone_raw.split(",") if x.strip()]:
                    db.add_agency_phone(agency_id, p)

            if email_raw and email_raw != "N/A":
                for e in [x.strip() for x in email_raw.split(",") if x.strip()]:
                    db.add_agency_email(agency_id, e)

            saved_db_count += 1
        logger.info(f"✅ Toplam {saved_db_count} acente 'acenteler.db' veritabanına kaydedildi/güncellendi.")
    except Exception as e:
        logger.error(f"Scraper SQLite veritabanı güncelleme hatası: {e}")


# ======================================================================
# BÖLÜM 2: MANUEL / OTO MESAJ GÖNDERME FONKSİYONLARI
# ======================================================================
def open_and_fill_agency_form(
    page,
    agency_name: str,
    profile_url: str
) -> bool:
    """
    Acente profil sayfasına gider, 'MESSAGE' modalını açar ve tüm form alanlarını
    gönderime hazır şekilde doldurur.
    """
    custom_message = prepare_agency_message(agency_name)
    logger.info(f"\n-------------------------------------------------------")
    logger.info(f"Acente Açılıyor: [{agency_name}]")
    logger.info(f"URL: {profile_url}")

    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=35000)
        random_sleep(1.5, 2.5)

        # Cookie rıza banner'ı çıkarsa kapat
        cookie_btn = page.query_selector(".didomi-dismiss-button, #didomi-notice-agree-button")
        if cookie_btn:
            try:
                cookie_btn.click()
                random_sleep(0.5, 1.0)
            except Exception:
                pass

        # 'MESSAGE' butonunu tıkla
        btn_message = page.query_selector(".ContactsWrapper_wrapper__nTEOp button, button:has-text('MESSAGE'), button:has-text('message')")
        if not btn_message:
            logger.error(f"[{agency_name}] 'MESSAGE' butonu bulunamadı.")
            return False

        btn_message.click()
        logger.info(f"[{agency_name}] İletişim modalı açıldı.")
        random_sleep(1.0, 2.0)

        # Name Field
        input_name = page.query_selector("input[name='name']")
        if input_name:
            input_name.fill(SENDER_INFO["NAME"])

        # Email Field
        input_email = page.query_selector("input[name='email']")
        if input_email:
            input_email.fill(SENDER_INFO["EMAIL"])

        # Phone Field
        input_phone = page.query_selector("input[name='phone']")
        if input_phone:
            input_phone.fill(SENDER_INFO["PHONE"])

        # Message Field (Parametrik Metin)
        textarea_msg = page.query_selector("textarea[name='message']")
        if textarea_msg:
            textarea_msg.fill(custom_message)

        # Privacy & Adult Checkboxes (Gizlilik ve Yetişkinlik / 'I'm an adult' onay kutularını işaretle)
        checkbox_selectors = [
            "input[name='privacy']",
            "input[name='adult']",
            "input[name='isAdult']",
            "input[name='is_adult']",
            "input[name='age']",
            "input[name='terms']",
            "input[type='checkbox']"
        ]
        for sel in checkbox_selectors:
            for cb in page.query_selector_all(sel):
                try:
                    if not cb.is_checked():
                        cb.check(force=True)
                except Exception:
                    try:
                        cb.click(force=True)
                    except Exception:
                        pass

        # Adult & Privacy etiketi/yazısı barındıran label, span veya div elemanlarına JS üzerinden de tıkla ve event tetikle
        try:
            page.evaluate("""() => {
                // Tüm checkbox input'larını işaretle ve change eventi tetikle
                document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                    if (!cb.checked) {
                        cb.checked = true;
                        cb.dispatchEvent(new Event('change', { bubbles: true }));
                        cb.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                });
                // Text içeriğinde 'adult', 'punolet', 'privacy', '18', 'read' geçen etikete tıkla
                document.querySelectorAll('label, span, div, p').forEach(el => {
                    const txt = (el.innerText || '').toLowerCase();
                    if (txt.includes('adult') || txt.includes('punolet') || txt.includes('privacy') || txt.includes('18') || txt.includes('read')) {
                        const cb = el.querySelector('input[type="checkbox"]') || el.parentElement?.querySelector('input[type="checkbox"]');
                        if (cb && !cb.checked) {
                            cb.checked = true;
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        try { el.click(); } catch(e) {}
                    }
                });
            }""")
        except Exception:
            pass

        logger.info(f"[{agency_name}] Form alanları hazırlandı ve dolduruldu!")
        return True

    except Exception as e:
        logger.error(f"[{agency_name}] Form açma/doldurma hatası: {e}")
        return False


def run_manual_messaging_flow(agencies: List[Dict[str, str]]):
    """
    MANUEL MOD:
    - Form dolu olarak modal açılır.
    - Kullanıcının ekranda 'Send' butonuna tıklaması veya HTTP POST isteği anında yakalanır.
    - Yakalandığı anda acente `sent_messages_log.json` dosyasına yazılır.
    - Otomatik olarak sıradaki acenteye geçip onun popup'ını açar.
    """
    if not HAS_PLAYWRIGHT:
        logger.error("Manuel mod için Playwright gereklidir.")
        return

    # Gönderilmemiş acenteleri filtrele
    pending_agencies = []
    for a in agencies:
        url = a.get("Profil Linki")
        if url and not is_already_sent(url):
            pending_agencies.append(a)
        else:
            logger.info(f"Atlanıyor (Daha önce gönderildi): {a.get('Acente Adı')} ({url})")

    if not pending_agencies:
        logger.info("Tüm acentelere daha önce mesaj gönderilmiş. Gönderilecek yeni acente yok.")
        return

    logger.info(f"\n=======================================================")
    logger.info(f"MANUEL MOD BAŞLATILDI! Toplam {len(pending_agencies)} gönderilmeyi bekleyen acente var.")
    logger.info("Ekrandaki popup'ta 'Send' butonuna basmanız bekleniyor. Gönderince otomatik sıradakine geçecektir.")
    logger.info(f"=======================================================\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=CONFIG["USER_DATA_DIR"],
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        for idx, agency in enumerate(pending_agencies, 1):
            name = agency.get("Acente Adı", "Acente")
            url = agency.get("Profil Linki")

            logger.info(f"[{idx}/{len(pending_agencies)}] Hazırlanıyor: {name}")

            # Gönderim durumunu takip etmek için bayraklar
            post_sent_flag = [False]

            def on_request(req):
                if req.method == "POST" and ("contact" in req.url or "message" in req.url or "agency" in req.url or "send" in req.url):
                    logger.info(f"[{name}] POST isteği yakalandı! ({req.url})")
                    post_sent_flag[0] = True

            page.on("request", on_request)

            success = open_and_fill_agency_form(page, agency_name=name, profile_url=url)
            if not success:
                logger.warning(f"[{name}] Form açılamadı, sıradaki acenteye geçiliyor...")
                page.remove_listener("request", on_request)
                continue

            # Buton tıklama dinleyicisi ekle
            page.evaluate("""() => {
                window.__send_clicked = false;
                document.addEventListener('click', (e) => {
                    const btn = e.target.closest('button');
                    if (btn && (btn.type === 'submit' || btn.innerText.toLowerCase().includes('send') || btn.innerText.toLowerCase().includes('pošalji'))) {
                        window.__send_clicked = true;
                    }
                }, true);
            }""")

            logger.info(f"👉 [{name}] İçin Lütfen Ekranda 'Send' Butonuna Basın...")

            sent_detected = False
            start_wait = time.time()
            max_wait_seconds = 300  # 5 dakika

            while time.time() - start_wait < max_wait_seconds:
                # 1. HTTP POST İsteği Atıldı mı?
                if post_sent_flag[0]:
                    sent_detected = True
                    break

                # 2. Buton Tıklandı mı (JS Event)?
                try:
                    js_clicked = page.evaluate("() => window.__send_clicked || false")
                    if js_clicked:
                        sent_detected = True
                        break
                except Exception:
                    pass

                # 3. Başarı Metni Göründü mü?
                try:
                    success_text = page.query_selector(".msg_sended_succes, text='Message successfully sent', text='Poruka je uspešno poslata', text='Hvala'")
                    if success_text:
                        sent_detected = True
                        break
                except Exception:
                    pass

                time.sleep(0.5)

            page.remove_listener("request", on_request)

            if sent_detected:
                logger.info(f"✅ [{name}] MESAJ GÖNDERİMİ ALGINLANDI!")
                record_sent_agency(url, name)
                logger.info("3 saniye sonra sıradaki acenteye geçiliyor...\n")
                time.sleep(3.0)
            else:
                logger.warning(f"⏱️ [{name}] Zaman aşımına uğradı veya atlandı.")

        context.close()


def run_automatic_messaging_flow(agencies: List[Dict[str, str]], dry_run: bool = True):
    """TAM OTOMATİK MESAJ MODU"""
    if not HAS_PLAYWRIGHT:
        logger.error("Otomatik mesaj modu için Playwright gereklidir.")
        return

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=CONFIG["USER_DATA_DIR"],
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        for idx, agency in enumerate(agencies, 1):
            name = agency.get("Acente Adı", "Acente")
            url = agency.get("Profil Linki")

            if not url or is_already_sent(url):
                logger.info(f"Atlanıyor: {name} (Daha önce gönderildi veya geçersiz link)")
                continue

            open_and_fill_agency_form(page, agency_name=name, profile_url=url)

            if dry_run:
                logger.info(f"[{name}] TEST (DRY-RUN) MODU: Gönderim yapılmadı.")
            else:
                submit_btn = page.query_selector("button[type='submit'], button:has-text('send request')")
                if submit_btn:
                    submit_btn.click()
                    record_sent_agency(url, name)
                    logger.info(f"✅ [{name}] OTOMATİK GÖNDERİLDİ!")

            random_sleep(3.0, 5.0)

        context.close()


def run_slow_auto_messaging_flow(agencies: List[Dict[str, str]]):
    """
    YAVAŞ OTOMATİK MESAJ MODU (--mode slow-auto):
    - Headful tarayıcı açılır.
    - Daha önce mesaj gönderilen acenteler filtrelenir.
    - Her acente için profil ve iletişim modalı açılır.
    - Form ve onay kutuları (gizlilik, yetişkinlik/adult checkbox) doldurulur.
    - 2 ila 10 saniye arasında rastgele beklenip 'Send' butonuna basılır.
    - POST isteği / gönderim onaylandıktan sonra `sent_messages_log.json` kaydedilir.
    - Sıradaki acenteye geçilir.
    """
    if not HAS_PLAYWRIGHT:
        logger.error("Yavaş otomatik mesaj modu için Playwright gereklidir.")
        return

    # Gönderilmemiş acenteleri filtrele
    pending_agencies = []
    for a in agencies:
        url = a.get("Profil Linki")
        if url and not is_already_sent(url):
            pending_agencies.append(a)
        else:
            logger.info(f"Atlanıyor (Daha önce gönderildi): {a.get('Acente Adı')} ({url})")

    if not pending_agencies:
        logger.info("Tüm acentelere daha önce mesaj gönderilmiş. Gönderilecek yeni acente yok.")
        return

    logger.info(f"\n=======================================================")
    logger.info(f"YAVAŞ OTOMATİK MOD BAŞLATILDI! Toplam {len(pending_agencies)} gönderilmeyi bekleyen acente var.")
    logger.info("Her acente için form doldurulup 2-10 sn arası beklenerek otomatik gönderilecektir.")
    logger.info(f"=======================================================\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=CONFIG["USER_DATA_DIR"],
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        for idx, agency in enumerate(pending_agencies, 1):
            name = agency.get("Acente Adı", "Acente")
            url = agency.get("Profil Linki")

            logger.info(f"[{idx}/{len(pending_agencies)}] İşleniyor: {name}")

            post_sent_flag = [False]

            def on_request(req):
                if req.method == "POST" and ("contact" in req.url or "message" in req.url or "agency" in req.url or "send" in req.url or "lead" in req.url):
                    logger.info(f"[{name}] POST isteği yakalandı! ({req.url})")
                    post_sent_flag[0] = True

            page.on("request", on_request)

            success = open_and_fill_agency_form(page, agency_name=name, profile_url=url)
            if not success:
                logger.warning(f"[{name}] Form açılamadı, sıradaki acenteye geçiliyor...")
                page.remove_listener("request", on_request)
                continue

            # 2 ila 10 saniye arasında rastgele bekleme
            wait_time = random.uniform(2.0, 10.0)
            logger.info(f"⏳ [{name}] Mesaj gönderilmeden önce {wait_time:.2f} saniye bekleniyor...")
            time.sleep(wait_time)

            # Send butonunu bul ve tıkla
            submit_btn = page.query_selector("button[type='submit'], button:has-text('Send'), button:has-text('send'), button:has-text('Pošalji'), button:has-text('pošalji')")
            if submit_btn:
                try:
                    submit_btn.click()
                    logger.info(f"[{name}] 'Send' butonuna tıklandı.")
                except Exception as e:
                    logger.error(f"[{name}] Send butonuna tıklanırken hata: {e}")
            else:
                logger.error(f"[{name}] 'Send' butonu bulunamadı.")

            # Gönderim tespitini bekle
            sent_detected = False
            start_wait = time.time()
            max_wait_seconds = 10

            while time.time() - start_wait < max_wait_seconds:
                if post_sent_flag[0]:
                    sent_detected = True
                    break
                try:
                    success_text = page.query_selector(".msg_sended_succes, text='Message successfully sent', text='Poruka je uspešno poslata', text='Hvala'")
                    if success_text:
                        sent_detected = True
                        break
                except Exception:
                    pass
                time.sleep(0.5)

            page.remove_listener("request", on_request)

            if sent_detected or post_sent_flag[0]:
                logger.info(f"✅ [{name}] OTOMATİK MESAJ GÖNDERİLDİ VE ALGINLANDI!")
            else:
                logger.info(f"✅ [{name}] Mesaj gönderim işlemi tamamlandı.")

            record_sent_agency(url, name)
            logger.info("3 saniye sonra sıradaki acenteye geçiliyor...\n")
            time.sleep(3.0)

        context.close()


# ======================================================================
# MAIN EXECUTION & CLI HANDLER
# ======================================================================
def load_agencies_for_messaging(csv_path: Optional[str] = None, url: Optional[str] = None) -> List[Dict[str, str]]:
    """Mesaj gönderimi için acente listesini acenteler.db veritabanından veya verilen CSV'den yükler."""
    if csv_path and os.path.exists(csv_path):
        logger.info(f"Acente listesi CSV'den okunuyor: {csv_path}")
        df = pd.read_csv(csv_path)
        return df.to_dict(orient="records")

    # DB'den yükle
    try:
        import db
        conn = db.get_connection()
        cursor = conn.cursor()

        city_filter = ""
        if url:
            parsed_slug = urlparse(url).path.strip("/").split("/")[-1]
            if parsed_slug and parsed_slug != "agencije-za-nekretnine":
                city_filter = parsed_slug.replace("-okrug", "").replace("-", " ")

        if city_filter:
            cursor.execute("""
                SELECT a.name as 'Acente Adı', a.address as 'Adres', w.url as 'Profil Linki'
                FROM agencies a
                LEFT JOIN agency_websites w ON a.id = w.agency_id
                WHERE LOWER(a.city) LIKE LOWER(?) AND a.status = 'NEW'
            """, (f"%{city_filter}%",))
        else:
            cursor.execute("""
                SELECT a.name as 'Acente Adı', a.address as 'Adres', w.url as 'Profil Linki'
                FROM agencies a
                LEFT JOIN agency_websites w ON a.id = w.agency_id
                WHERE a.status = 'NEW'
            """)

        rows = cursor.fetchall()
        conn.close()

        if rows and len(rows) > 0:
            logger.info(f"✅ acenteler.db veritabanından {len(rows)} adet gönderilmemiş acente yüklendi.")
            return [dict(r) for r in rows if r['Profil Linki']]
    except Exception as e:
        logger.warning(f"DB'den acente okuma uyarısı: {e}")

    # Fallback: Canlı kazıma yap
    logger.info(f"Canlı acente verisi çekiliyor: {url}")
    return crawl_live_agencies(url)


def main():
    parser = argparse.ArgumentParser(description="Nekretnine.rs Emlak Acenteleri Kazıma ve Mesaj Otomasyonu")
    parser.add_argument("url", nargs="?", default=CONFIG["START_URL"], help="Bölge URL'si veya Acente Profil URL'si")
    parser.add_argument("-o", "--output", default=CONFIG["OUTPUT_CSV"], help="Çıktı CSV dosya adı")
    parser.add_argument("--mode", choices=["scrape", "message", "manual", "slow-auto"], default="scrape", help="İşlem modu: 'scrape' (kazıma), 'message' (oto mesaj), 'manual' (yarı-otomatik popup), 'slow-auto' (yavaş otomatik)")
    parser.add_argument("--csv", help="Mesaj modları için okunacak CSV dosyası")
    parser.add_argument("--send", action="store_true", help="Formu otomatik gönder (message modunda)")

    args = parser.parse_args()

    # 1. KAZIMA MODU
    if args.mode == "scrape":
        logger.info("=== Nekretnine.rs Kazıma Modu ===")
        logger.info(f"Hedef URL: {args.url}")
        logger.info(f"Çıktı Dosyası: {args.output}")

        agencies = crawl_live_agencies(args.url)
        if agencies:
            export_to_csv(agencies, args.output)
        else:
            logger.error("Canlı acente verisi çekilemedi.")

    # 2. YARI OTOMATİK MANUEL POPUP MODU
    elif args.mode == "manual":
        logger.info("=== Nekretnine.rs MANUEL YARI-OTOMATİK POPUP MODU ===")
        agencies_list = load_agencies_for_messaging(args.csv, args.url)
        if agencies_list:
            run_manual_messaging_flow(agencies_list)
        else:
            logger.error("İşlenecek acente listesi bulunamadı.")

    # 3. OTOMATİK MESAJ MODU
    elif args.mode == "message":
        logger.info("=== Nekretnine.rs Otomatik Mesaj Modu ===")
        agencies_list = load_agencies_for_messaging(args.csv or args.output, args.url)
        if agencies_list:
            dry_run = not args.send
            run_automatic_messaging_flow(agencies_list, dry_run=dry_run)
        else:
            logger.error("İşlenecek acente bulunamadı.")

    # 4. YAVAŞ OTOMATİK MESAJ MODU
    elif args.mode == "slow-auto":
        logger.info("=== Nekretnine.rs YAVAŞ OTOMATİK MESAJ MODU ===")
        agencies_list = load_agencies_for_messaging(args.csv, args.url)
        if agencies_list:
            run_slow_automatic_messaging_flow(agencies_list)
        else:
            logger.error("İşlenecek acente bulunamadı.")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
