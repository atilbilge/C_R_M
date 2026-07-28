#!/usr/bin/env python3
"""
indomio_scraper.py
------------------
Indomio Serbia (indomio.rs) portalından tüm emlak acentelerinin, yetkili yöneticilerinin,
adreslerinin, telefon numaralarının (Base64 çözümlenmiş) ve resmi lisans numaralarının
kazınarak acenteler.db veritabanına aktarılması.
"""

import os
import sys
import re
import time
import base64
import random
import html
import argparse
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("IndomioScraper")

BASE_URL = "https://www.indomio.rs"
AGENTS_URL = "https://www.indomio.rs/en/agents"


def decode_base64_phone(b64_str: str) -> Optional[str]:
    """Base64 kodlanmış telefon numarasını çözer."""
    try:
        decoded = base64.b64decode(b64_str.strip()).decode('utf-8')
        cleaned = re.sub(r'[^\d+]', '', decoded)
        if len(cleaned) >= 8:
            return decoded
    except Exception:
        pass
    return None


def parse_indomio_agent_profile(html_text: str, profile_url: str) -> Dict[str, any]:
    """Indomio acente profil sayfasını ayrıştırır."""
    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Acente Unvanı
    title_el = soup.find("h1")
    name = title_el.get_text(strip=True) if title_el else ""
    if not name:
        title_match = re.search(r'Estate Agent\s+([^|]+)\|', soup.title.get_text() if soup.title else "")
        if title_match:
            name = title_match.group(1).strip()

    # 2. Sayfa metin hatlarını incele
    body_text = soup.get_text(separator="\n", strip=True)
    lines = [l for l in body_text.splitlines() if len(l) > 1]

    contact_person = ""
    address = ""
    city = ""
    license_no = ""
    phones = set()

    # Lisans No
    lic_match = re.search(r'License\s*#:\s*(\d+)|Registar posrednika\s*#:\s*(\d+)', body_text, re.IGNORECASE)
    if lic_match:
        license_no = lic_match.group(1) or lic_match.group(2)

    # İlgili satırları bul
    if name and name in lines:
        idx = lines.index(name)
        # Genelde name'den sonraki 1. satır Yetkili Temsilci, 2. satır Adres
        if idx + 1 < len(lines):
            cand_person = lines[idx + 1]
            if not any(kw in cand_person for kw in ["Telephone", "Website", "License", "Send message", "More"]):
                contact_person = cand_person

        if idx + 2 < len(lines):
            cand_addr = lines[idx + 2]
            if not any(kw in cand_addr for kw in ["Telephone", "Website", "License", "Send message", "More"]):
                address = cand_addr

    # Şehir belirleme
    if "Belgrade" in address or "Beograd" in address:
        city = "Beograd"
    elif "Novi Sad" in address:
        city = "Novi Sad"
    elif "Niš" in address or "Nis" in address:
        city = "Niš"
    elif "," in address:
        city = address.split(",")[-1].strip()

    # Base64 Telefonları ayıkla
    b64_matches = re.findall(r'[A-Za-z0-9+/]{20,40}==', html_text)
    for b64 in b64_matches:
        phone = decode_base64_phone(b64)
        if phone:
            phones.add(phone)

    # Düz telefon desenleri (örn. 064..., +381...)
    raw_phones = re.findall(r'(?:\+381|0)[0-9\s/\-]{7,15}', body_text)
    for p in raw_phones:
        cleaned = re.sub(r'[^\d+]', '', p)
        if len(cleaned) >= 8 and not cleaned.startswith("000"):
            phones.add(p.strip())

    # href="tel:..." olan bağlantıları ayıkla (Base64 kod çözümü dahil)
    for a in soup.select("a[href*='tel:']"):
        tel = a.get("href").replace("tel:", "").strip()
        dec = decode_base64_phone(tel)
        if dec:
            phones.add(dec)
        else:
            cleaned = re.sub(r'[^\d+]', '', tel)
            if len(cleaned) >= 8 and not cleaned.startswith("000"):
                phones.add(tel)

    return {
        "name": name,
        "contact_person": contact_person,
        "address": address,
        "city": city,
        "license_no": license_no,
        "phones": list(phones),
        "profile_url": profile_url
    }


def crawl_indomio(max_pages: int = 10, delay: float = 1.5, headless: bool = True):
    """Indomio acente listesini tarar ve acenteler.db veritabanına kaydeder."""
    db.init_db()

    total_added = 0
    total_phones = 0

    with sync_playwright() as p:
        logger.info("Playwright Chromium başlatılıyor...")
        browser = p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            ]
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        p_num = 1
        while True:
            if max_pages > 0 and p_num > max_pages:
                logger.info(f"Maksimum sayfa sınırına ({max_pages}) ulaşıldı.")
                break

            target_url = AGENTS_URL if p_num == 1 else f"{AGENTS_URL}?page={p_num}"
            logger.info(f"Indomio Sayfa {p_num} taranıyor... ({target_url})")

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_selector("a[href*='/agent/']", timeout=8000)
                except Exception:
                    pass
                time.sleep(2)
            except Exception as e:
                logger.error(f"Sayfa {p_num} yükleme hatası: {e}")
                break

            soup = BeautifulSoup(page.content(), "html.parser")
            agent_links = soup.select("a[href*='/en/agent/'], a[href*='/agent/']")
            
            seen_links = set()
            links = []
            for a in agent_links:
                href = a.get("href")
                if href and href not in seen_links and a.get_text(strip=True):
                    seen_links.add(href)
                    links.append(urljoin(BASE_URL, href))

            if not links:
                logger.info(f"Sayfa {p_num}'de acente bulunamadı. Tarama tamamlandı.")
                break

            logger.info(f"Sayfa {p_num}: {len(links)} adet acente linki bulundu. Detaylar çekiliyor...")

            for idx, link in enumerate(links, 1):
                try:
                    page.goto(link, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(1)
                    try:
                        # Playwright get_by_text kullanarak "Telephone number" / "Prikaži telefon" butonunu tıkla
                        btn1 = page.get_by_text("Telephone number")
                        if btn1.count() > 0:
                            btn1.first.click(timeout=2000)
                            time.sleep(0.5)

                        btn2 = page.get_by_text("Prikaži telefon")
                        if btn2.count() > 0:
                            btn2.first.click(timeout=2000)
                            time.sleep(0.5)
                    except Exception:
                        pass

                    agent_data = parse_indomio_agent_profile(page.content(), link)
                except Exception as err:
                    logger.warning(f"  [{idx}/{len(links)}] Detay çekme uyarısı ({link}): {err}")
                    continue

                name = agent_data["name"]
                if not name:
                    continue

                # Veritabanına Ekle / Güncelle
                agency_id = db.add_or_get_agency(
                    name=name,
                    city=agent_data["city"],
                    address=agent_data["address"],
                    license_no=agent_data["license_no"],
                    contact_person=agent_data["contact_person"],
                    profile_url=agent_data["profile_url"]
                )

                # Telefonları Ekle
                for ph in agent_data["phones"]:
                    db.add_agency_phone(agency_id, ph)
                    total_phones += 1

                total_added += 1
                lic_info = f", Lisans: {agent_data['license_no']}" if agent_data['license_no'] else ""
                contact_info = f", Yetkili: {agent_data['contact_person']}" if agent_data['contact_person'] else ""
                logger.info(f"  [{idx}/{len(links)}] {name} (Şehir: {agent_data['city'] or '-'}{contact_info}{lic_info}) -> DB ID: {agency_id}")

                time.sleep(random.uniform(delay, delay + 1.0))

            p_num += 1

        browser.close()

    logger.info(f"\n=======================================================")
    logger.info(f"Indomio Serbia Taraması Tamamlandı!")
    logger.info(f"İşlenen Acente Sayısı: {total_added}")
    logger.info(f"Eklenen Telefon Sayısı: {total_phones}")
    logger.info(f"=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Indomio.rs Emlak Acenteleri Kazıma Betiği")
    parser.add_argument("--max-pages", type=int, default=18, help="Taranacak maksimum arama sayfası sayısı (varsayılan: 18)")
    parser.add_argument("--delay", type=float, default=1.5, help="Bekleme süresi (saniye)")

    args = parser.parse_args()

    crawl_indomio(max_pages=args.max_pages, delay=args.delay)


if __name__ == "__main__":
    main()
