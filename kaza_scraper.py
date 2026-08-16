#!/usr/bin/env python3
"""
kaza_scraper.py
----------------
Kaza.rs üzerindeki emlak acentelerini (https://www.kaza.rs/en/agencije-za-promet-nekretnina)
yüksek hassasiyetli insansı (human-like) tempoda tarayıp acenteler.db veritabanına `source = 'kaza'` olarak kaydeden betik.

Zengin Veri Özellikleri:
- Unvan, Şehir, Açık Adres, PIB, MB, Lisans / Sicil No
- Kurucu / Sahibi (Contact Person)
- Kuruluş Tarihi (establishment_date)
- Firma Ölçeği & Çalışan Sayısı (enterprise_size, employees_json)
- Google Puanı & Yorum Sayısı (notes alanına)
- Kredi / Blokaj / Vergi Borcu Durumu (notes alanına)
- Web sitesi, Telefonlar ve E-postalar

İnsansı Davranış & Ban Koruması:
- Her detay isteği arasında 4.5 - 9.0 saniye rastgele bekleme
- Her 10 detay isteğinde bir "kahve molası" (12 - 25 saniye ekstra bekleme)
- Listeleme sayfaları arasında 6.0 - 12.0 saniye bekleme
- HTTP 429/403 durumunda 45 saniye otomatik soğuma ve retry
- TLS/JA3 User-Agent rotasyonu (curl_cffi chrome120)
- Kaldığı yerden devam edebilme (system_meta: kaza_last_page)
"""

import os
import sys
import time
import random
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

import db

BASE_LIST_URL = "https://www.kaza.rs/en/agencije-za-promet-nekretnina"
BASE_DOMAIN = "https://www.kaza.rs"

# İnsansı Bekleme Parametreleri (Saniye)
MIN_DELAY_DETAILS = 4.5
MAX_DELAY_DETAILS = 9.0

MIN_DELAY_PAGES = 6.0
MAX_DELAY_PAGES = 12.0

COFFEE_BREAK_INTERVAL = 10
COFFEE_BREAK_MIN = 12.0
COFFEE_BREAK_MAX = 25.0

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kaza_scraper.log")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]


def log(msg: str):
    """Hem konsola hem de log dosyasına anlık yazan log fonksiyonu."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    print(formatted_msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")


def get_last_processed_page() -> int:
    """Veritabanından kalınan son sayfa numarasını okur."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM system_meta WHERE key = 'kaza_last_page'")
    row = cur.fetchone()
    conn.close()
    return int(row["value"]) if row else 1


def save_last_processed_page(page: int):
    """Kalınan son sayfa numarasını veritabanına kaydeder."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO system_meta (key, value, updated_at)
        VALUES ('kaza_last_page', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (str(page), datetime.now().isoformat()))
    conn.commit()
    conn.close()


def fetch_url(url: str, params: Optional[Dict] = None) -> Optional[str]:
    """curl_cffi ile TLS impersonate yaparak Kaza.rs sayfasını çeker."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,sr;q=0.8",
        "Referer": "https://www.kaza.rs/"
    }

    try:
        resp = cffi_requests.get(url, params=params, headers=headers, impersonate="chrome120", allow_redirects=True, timeout=25)
        if resp.status_code == 200:
            return resp.text
        elif resp.status_code in [429, 403]:
            log(f"⚠️ [ENGEL / LIMIT HASSASİYETİ] HTTP {resp.status_code}. 45 saniye soğuma bekleniyor...")
            time.sleep(45)
            return None
        else:
            log(f"❌ HTTP Hata: {resp.status_code} - {url}")
            return None
    except Exception as e:
        log(f"❌ İstek Hatası: {e}")
        return None


def parse_agency_detail(html: str, profile_url: str) -> Dict[str, Any]:
    """Detay sayfasından JSON-LD ve DOM kullanarak TÜM ekstra bilgileri ayıklar."""
    soup = BeautifulSoup(html, "html.parser")
    
    data = {
        "name": "",
        "city": "Beograd",
        "address": "",
        "pib": "",
        "mb": "",
        "license_no": "",
        "contact_person": "",
        "establishment_date": "",
        "enterprise_size": "",
        "employee_count": None,
        "google_rating": "",
        "google_reviews": "",
        "badges": [],
        "website": "",
        "activity_code": "",
        "phones": [],
        "emails": [],
        "profile_url": profile_url
    }

    # 1. JSON-LD Parse
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(s.string)
            if isinstance(ld, dict) and (ld.get("@type") == "RealEstateAgent" or "RealEstateAgent" in ld.get("@type", [])):
                data["name"] = ld.get("name") or ld.get("legalName") or ""
                
                addr_obj = ld.get("address")
                if isinstance(addr_obj, dict):
                    data["address"] = addr_obj.get("streetAddress", "")
                    locality = addr_obj.get("addressLocality", "")
                    if locality:
                        data["city"] = locality.split(",")[0].strip()

                if ld.get("taxID"): data["pib"] = str(ld["taxID"]).strip()
                if ld.get("vatID"): data["mb"] = str(ld["vatID"]).strip()
                if ld.get("naics"): data["activity_code"] = str(ld["naics"]).strip()
                if ld.get("foundingDate"): data["establishment_date"] = str(ld["foundingDate"]).strip()
                if ld.get("numberOfEmployees") is not None: data["employee_count"] = ld["numberOfEmployees"]
                
                if ld.get("url") and "kaza.rs" not in ld["url"]:
                    data["website"] = ld["url"].strip()
                if ld.get("telephone"):
                    data["phones"].append(str(ld["telephone"]).strip())
                if isinstance(ld.get("founder"), dict) and ld["founder"].get("name"):
                    data["contact_person"] = ld["founder"]["name"].strip()
        except Exception:
            pass

    text = soup.get_text()

    # 2. Unvan Fallback
    if not data["name"]:
        h1 = soup.find("h1")
        if h1:
            data["name"] = h1.get_text(strip=True)

    # 3. Google Rating & Reviews Parse
    rating_m = re.search(r"★\s*([0-9.,]+)\s*·\s*(\d+)\s*reviews", text)
    if rating_m:
        data["google_rating"] = rating_m.group(1).replace(",", ".")
        data["google_reviews"] = rating_m.group(2)
    else:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            m_m = re.search(r"Google rating:\s*([0-9.,]+)★\s*\((\d+)\)", meta_desc["content"])
            if m_m:
                data["google_rating"] = m_m.group(1).replace(",", ".")
                data["google_reviews"] = m_m.group(2)

    # 4. Badges (No blokada, No tax debt, No court cases, Credit rating)
    if "No blokada" in text or "Verified via NBS" in text:
        data["badges"].append("NBS Blokaj Yok")
    if "No tax debt" in text:
        data["badges"].append("Vergi Borcu Yok")
    if "No court cases" in text:
        data["badges"].append("Mahkeme/Dava Yok")
    if "Credit rating" in text:
        data["badges"].append("Kredi Derecelendirmeli")

    # 5. Firma Ölçeği & Sahibi Fallback
    size_m = re.search(r"Company size\s*([A-Za-z\s]+?)(?:\d+ employee|Ownership|$)", text)
    if size_m:
        data["enterprise_size"] = size_m.group(1).strip()

    owner_m = re.search(r"Ownership & leadership\s*([A-ZŠĐČĆŽa-zšđčćž\s]+?)(?:Owner|Director|Manager|$)", text)
    if owner_m and not data["contact_person"]:
        data["contact_person"] = owner_m.group(1).strip()

    # 6. Reg / PIB / MB Fallbacks
    if not data["pib"]:
        pib_m = re.search(r"TIN\s*(\d{9})", text)
        if pib_m: data["pib"] = pib_m.group(1)

    if not data["mb"]:
        mb_m = re.search(r"Registration number\s*(\d{8})", text)
        if mb_m: data["mb"] = mb_m.group(1)

    reg_m = re.search(r"Registry number\s*(\d+)", text)
    if reg_m: data["license_no"] = reg_m.group(1)

    # Telefonlar
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("tel:"):
            ph = a["href"].replace("tel:", "").strip()
            if ph and ph not in data["phones"]:
                data["phones"].append(ph)

    # E-postalar
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("mailto:"):
            em = a["href"].replace("mailto:", "").strip()
            if em and not em.endswith("kaza.rs") and em not in data["emails"]:
                data["emails"].append(em)

    # Web sitesi
    if not data["website"]:
        for a in soup.find_all("a", href=True):
            if "Visit website" in a.get_text():
                href = a["href"]
                if "kaza.rs" not in href and "google.com" not in href and "facebook.com" not in href:
                    data["website"] = href.strip()
                    break

    return data


def scrape_kaza(max_pages: Optional[int] = None):
    """Kaza.rs acentelerini tarar ve DB'ye ekler."""
    db.init_db()
    start_page = get_last_processed_page()
    log(f"🚀 Kaza.rs Emlak Acenteleri Zengin Veri Taraması Başlatılıyor... (Başlangıç Sayfası: {start_page})")

    curr_page = start_page
    total_added = 0
    pages_processed = 0
    detail_counter = 0

    while True:
        if max_pages and pages_processed >= max_pages:
            log(f"🛑 Belirtilen maksimum sayfa sınırına ({max_pages}) ulaşıldı.")
            break

        log(f"📄 Listeleme Sayfası {curr_page} çekiliyor...")
        params = {"page": str(curr_page)} if curr_page > 1 else None
        
        html = fetch_url(BASE_LIST_URL, params=params)
        if not html:
            log(f"⚠️ Sayfa {curr_page} alınamadı. 15 sn bekleniyor...")
            time.sleep(15)
            continue

        soup = BeautifulSoup(html, "html.parser")
        company_urls = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/en/company/" in href and href not in seen:
                seen.add(href)
                full_url = BASE_DOMAIN + href if href.startswith("/") else href
                company_urls.append(full_url)

        log(f"📊 Sayfa {curr_page}: {len(company_urls)} firma bağlantısı tespit edildi.")

        if not company_urls:
            log(f"✅ Sayfa {curr_page}'de firma bulunamadı. Tarama tamamlandı.")
            break

        for idx, comp_url in enumerate(company_urls, start=1):
            detail_counter += 1
            log(f"  [{idx}/{len(company_urls)}] 🔍 Detay Çekiliyor: {comp_url.split('/')[-1]}...")
            detail_html = fetch_url(comp_url)
            
            if not detail_html:
                continue

            parsed = parse_agency_detail(detail_html, comp_url)
            if not parsed["name"]:
                continue

            # DB Ekle / Güncelle
            ag_id = db.add_or_get_agency(
                name=parsed["name"],
                city=parsed["city"],
                address=parsed["address"],
                pib=parsed["pib"],
                mb=parsed["mb"],
                license_no=parsed["license_no"],
                contact_person=parsed["contact_person"],
                status="NEW",
                profile_url=comp_url
            )

            # Ekstra Zengin Bilgileri Güncelle
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE agencies SET source = 'kaza' WHERE id = ?", (ag_id,))
            if parsed["activity_code"]:
                cur.execute("UPDATE agencies SET activity_code = ? WHERE id = ?", (parsed["activity_code"], ag_id))
            conn.commit()
            conn.close()

            # Rich Info (Kuruluş Tarihi, Firma Ölçeği, Çalışan Sayısı)
            employees_json = json.dumps({"count": parsed["employee_count"]}) if parsed["employee_count"] is not None else None
            db.update_agency_rich_info(
                agency_id=ag_id,
                long_name=parsed["name"],
                establishment_date=parsed["establishment_date"],
                enterprise_size=parsed["enterprise_size"],
                employees_json=employees_json
            )

            # Notes Alanına Zengin Notları Yaz (Google Puanı & Rozetler)
            note_parts = []
            if parsed["google_rating"]:
                note_parts.append(f"Google: {parsed['google_rating']}★ ({parsed['google_reviews']} Yorum)")
            if parsed["badges"]:
                note_parts.append("Durum: " + ", ".join(parsed["badges"]))
            
            if note_parts:
                notes_str = " | ".join(note_parts)
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE agencies SET notes = ? WHERE id = ? AND (notes IS NULL OR notes = '')", (notes_str, ag_id))
                conn.commit()
                conn.close()

            # Web sitesi
            if parsed["website"]:
                db.add_agency_website(ag_id, parsed["website"], site_type="kaza")

            # E-posta
            for em in parsed["emails"]:
                db.add_agency_email(ag_id, em)

            # Telefon
            for ph in parsed["phones"]:
                db.add_agency_phone(ag_id, ph)

            extra_log = f"Google: {parsed['google_rating']}★" if parsed["google_rating"] else "Kaza Verisi"
            log(f"  [{idx}/{len(company_urls)}] ✅ Kaydedildi ID={ag_id} | {parsed['name']} ({parsed['city']}) | {extra_log}")
            total_added += 1

            # İnsansı Bekleme & Periyodik Kahve Molası
            if detail_counter % COFFEE_BREAK_INTERVAL == 0:
                coffee_delay = random.uniform(COFFEE_BREAK_MIN, COFFEE_BREAK_MAX)
                log(f"☕ [İNSANSI MOLA] 10 firma tarandı, {round(coffee_delay, 1)} saniye kahve molası veriliyor...")
                time.sleep(coffee_delay)
            else:
                delay = random.uniform(MIN_DELAY_DETAILS, MAX_DELAY_DETAILS)
                time.sleep(delay)

        save_last_processed_page(curr_page + 1)
        log(f"💾 Sayfa {curr_page} tamamlandı. Sonraki sayfa: {curr_page + 1}")

        curr_page += 1
        pages_processed += 1
        
        page_delay = random.uniform(MIN_DELAY_PAGES, MAX_DELAY_PAGES)
        log(f"☕ [SAYFA GEÇİŞİ DİNLENMESİ] {round(page_delay, 1)}s bekleniyor...")
        time.sleep(page_delay)

    log(f"🎉 Tarama işlemi bitti! İşlenen Sayfa: {pages_processed} | Eklenen/Güncellenen Kayıt: {total_added}")


if __name__ == "__main__":
    max_p = int(sys.argv[1]) if len(sys.argv) > 1 else None
    scrape_kaza(max_pages=max_p)
