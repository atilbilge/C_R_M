#!/usr/bin/env python3
"""
companywall_6831_scraper.py
----------------------------
CompanyWall.rs üzerindeki 6831 faaliyet kodlu (Upravljanje nekretninama za naknadu ili na osnovu ugovora)
firmaları insansı (human-like) tempoda tarayıp acenteler.db veritabanına kaydeden kazıma betiği.

- Doğru Parametre: `at=6831` (Šifra delatnosti)
- Sistem Geneli VPN Desteği (curl_cffi TLS impersonate)
- Kaldığı yerden devam edebilme (Resume Support via system_meta & PIB checks)
- Canlı İlerleme Takibi (Log dosyası & DB İlerleme Durumu)
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

TARGET_ACTIVITY_CODE = "6831"
BASE_SEARCH_URL = "https://www.companywall.rs/pretraga"

MIN_DELAY_BETWEEN_PAGES = 5.0
MAX_DELAY_BETWEEN_PAGES = 10.0

MIN_DELAY_BETWEEN_DETAILS = 4.0
MAX_DELAY_BETWEEN_DETAILS = 8.0

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "companywall_6831.log")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
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
    cur.execute("SELECT value FROM system_meta WHERE key = 'cw_6831_last_page'")
    row = cur.fetchone()
    conn.close()
    return int(row["value"]) if row else 1


def save_last_processed_page(page: int):
    """Kalınan son sayfa numarasını veritabanına kaydeder."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO system_meta (key, value, updated_at)
        VALUES ('cw_6831_last_page', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (str(page), datetime.now().isoformat()))
    conn.commit()
    conn.close()


def fetch_url(url: str, params: Optional[Dict] = None) -> Optional[str]:
    """curl_cffi ile TLS/JA3 fingerprint taklidi yaparak CompanyWall sayfasını çeker."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.companywall.rs/"
    }

    try:
        resp = cffi_requests.get(url, params=params, headers=headers, impersonate="chrome120", allow_redirects=False, timeout=20)
        if resp.status_code == 200:
            return resp.text
        elif resp.status_code == 302 and "TooManyRequests" in resp.headers.get("Location", ""):
            log("⚠️ [GEÇİCİ ENGEL] TooManyRequests. 30 saniye insansı dinlenme bekleniyor...")
            time.sleep(30)
            return None
        else:
            log(f"❌ HTTP Hata: {resp.status_code} - {url}")
            return None
    except Exception as e:
        log(f"❌ İstek Hatası: {e}")
        return None


def scrape_companywall_6831():
    """6831 faaliyet kodlu firmaları VPN / curl_cffi motoru ile insansı tempoda tarar."""
    db.init_db()
    
    start_page = get_last_processed_page()
    log(f"🚀 CompanyWall 6831 Taraması Başlatılıyor... (Kalınan Sayfa: {start_page})")

    curr_page = start_page
    total_scraped = 0
    total_skipped = 0

    while True:
        log(f"📄 Sayfa {curr_page} çekiliyor (at={TARGET_ACTIVITY_CODE})...")
        params = {
            "at": TARGET_ACTIVITY_CODE,
            "p": str(curr_page)
        }

        html = fetch_url(BASE_SEARCH_URL, params=params)
        if not html:
            log(f"⚠️ Sayfa {curr_page} alınamadı, 8 sn beklenip tekrar denenecek...")
            time.sleep(8)
            continue

        soup = BeautifulSoup(html, "html.parser")
        companies = []
        seen_hrefs = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            name = a.get_text(strip=True)
            if "/firma/" in href and name and href not in seen_hrefs:
                seen_hrefs.add(href)
                full_url = "https://www.companywall.rs" + href if href.startswith("/") else href
                companies.append({"name": name, "url": full_url})

        log(f"📊 Sayfa {curr_page}: {len(companies)} firma tespit edildi.")

        if not companies:
            log(f"✅ Sayfa {curr_page}'de yeni firma bulunamadı. Tarama tamamlandı.")
            break

        for idx, comp in enumerate(companies, start=1):
            comp_url = comp["url"]
            comp_name = comp["name"]

            # ZATEN EKLENMİŞ Mİ KONTROLÜ (RESUMABLE / KALDIĞI YERDEN DEVAM)
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id FROM agency_websites WHERE url = ?", (comp_url,))
            existing = cur.fetchone()
            conn.close()

            if existing:
                log(f"  [{idx}/{len(companies)}] ⏭️ Zaten Kayıtlı (Atlanıyor): {comp_name}")
                total_skipped += 1
                continue

            # Firma detayını insansı tempoda çek
            log(f"  [{idx}/{len(companies)}] 🔍 Detay Çekiliyor: {comp_name}...")
            detail_html = fetch_url(comp_url)

            pib = ""
            mb = ""
            city = "Beograd"
            address = ""
            long_name = comp_name
            est_date = ""
            enterprise_size = "Mikro"
            emails = []
            phones = []

            if detail_html:
                pib_match = re.search(r"PIB:?\s*(\d{9})", detail_html)
                if pib_match: pib = pib_match.group(1)

                mb_match = re.search(r"MB:?\s*(\d{8})", detail_html)
                if mb_match: mb = mb_match.group(1)

                found_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", detail_html))
                emails = [e for e in found_emails if not e.endswith("companywall.rs") and not e.endswith(".png") and not e.endswith(".jpg")]

                found_phones = set(re.findall(r"\+381\s?\d{2}\s?\d{6,7}", detail_html))
                phones = list(found_phones)

            # Veritabanına kaydet
            ag_id = db.add_or_get_agency(
                name=comp_name,
                city=city,
                address=address,
                pib=pib,
                mb=mb,
                status="NEW",
                profile_url=comp_url
            )

            db.update_agency_rich_info(
                agency_id=ag_id,
                long_name=long_name,
                establishment_date=est_date,
                enterprise_size=enterprise_size
            )

            if comp_url:
                db.add_agency_website(ag_id, comp_url)

            for em in emails:
                db.add_agency_email(ag_id, em)

            for ph in phones:
                db.add_agency_phone(ag_id, ph)

            # Faaliyet kodunu 6831 olarak güncelle
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE agencies SET activity_code = '6831', segment = 'D-Kucuk' WHERE id = ?", (ag_id,))
            conn.commit()
            conn.close()

            total_scraped += 1
            log(f"  [{idx}/{len(companies)}] ✅ Veritabanına Kaydedildi (ID: {ag_id} | PIB: {pib or '-'})")

            # İnsansı Bekleme (Firma detayları arası)
            delay = random.uniform(MIN_DELAY_BETWEEN_DETAILS, MAX_DELAY_BETWEEN_DETAILS)
            time.sleep(delay)

        # Sayfa tamamlandı, kalınan sayfayı kaydet
        save_last_processed_page(curr_page + 1)
        log(f"💾 Sayfa {curr_page} tamamlandı. Sonraki başlama sayfası: {curr_page + 1}")

        curr_page += 1
        page_delay = random.uniform(MIN_DELAY_BETWEEN_PAGES, MAX_DELAY_BETWEEN_PAGES)
        log(f"☕ İnsansı Dinlenme ({round(page_delay, 1)}s beklemeyle sonraki sayfaya geçiliyor)...")
        time.sleep(page_delay)

    log("🎉 TÜM FAALİYET KODU 6831 TARAMASI EKSİKSİZ TAMAMLANDI!")


if __name__ == "__main__":
    scrape_companywall_6831()
