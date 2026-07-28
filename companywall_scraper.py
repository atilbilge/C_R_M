#!/usr/bin/env python3
"""
companywall_scraper.py
----------------------
CompanyWall Serbia (companywall.rs) platformundan 6831 (Emlak Acenteleri ve Yönetimi)
kodlu tüm resmi şirketlerin, iletişim bilgilerinin, e-postalarının, telefonlarının,
PIB ve Matični Broj (MB) verilerinin kazınarak acenteler.db veritabanına aktarılması.
"""

import os
import sys
import re
import time
import random
import html
import argparse
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin

try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    import urllib.request
    HAS_CFFI = False

import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamFormatter(sys.stdout)] if hasattr(logging, 'StreamFormatter') else [logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CompanyWallScraper")

BASE_URL = "https://www.companywall.rs"
SEARCH_URL = "https://www.companywall.rs/pretraga?cr=RSD&n=&mv=&r=&c=&cp=&at=6831&area=&subarea=&sbjact=t&blckd=&dbf=&dbt=&type=&hr=&bly=2025&dsm%5B0%5D.Code=1101&dsm%5B0%5D.From=0&dsm%5B0%5D.To=0&dsm%5B1%5D.Code=966&dsm%5B1%5D.From=0&dsm%5B1%5D.To=0&dsm%5B-1%5D.Code=0&dsm%5B-1%5D.From=0&dsm%5B-1%5D.To=0&distinctcodes=&xpnd=true"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_url_html(url: str) -> Optional[str]:
    """URL'den HTML içeriğini çeker."""
    if HAS_CFFI:
        try:
            r = cffi_requests.get(url, impersonate="chrome124", headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            logger.debug(f"cffi request hatası ({url}): {e}")

    # Fallback to urllib
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"urllib fetch hatası ({url}): {e}")

    return None


def extract_company_links_from_search_page(html_text: str) -> List[str]:
    """Arama sayfasındaki tüm firma detay URL'lerini ayıklar."""
    pattern = r'href=["\'](/firma/[^"\']+)["\']'
    raw_links = re.findall(pattern, html_text)
    
    seen = set()
    links = []
    for link in raw_links:
        full = urljoin(BASE_URL, link)
        if full not in seen:
            seen.add(full)
            links.append(full)
    return links


def parse_company_detail_page(url: str, html_text: str) -> Dict[str, any]:
    """Firma detay sayfasındaki tüm kurumsal verileri ayrıştırır."""
    # 1. Unvan
    title_match = re.search(r'itemprop=["\']name["\'][^>]*>(.*?)</h1>', html_text, re.DOTALL)
    if not title_match:
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.DOTALL)
    name = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
    name = html.unescape(name)

    # 2. Adres & Şehir
    street_match = re.search(r'itemprop=["\']streetAddress["\'][^>]*>(.*?)</span>', html_text, re.DOTALL)
    locality_match = re.search(r'itemprop=["\']addressLocality["\'][^>]*>(.*?)</span>', html_text, re.DOTALL)

    street = re.sub(r'<[^>]+>', '', street_match.group(1)).strip() if street_match else ""
    city = re.sub(r'<[^>]+>', '', locality_match.group(1)).strip() if locality_match else ""

    address = f"{street}, {city}".strip(", ") if street or city else ""

    # 3. PIB & MB
    pib_match = re.search(r'itemprop=["\']vatID["\'][^>]*>(.*?)</span>', html_text, re.DOTALL)
    if not pib_match:
        pib_match = re.search(r'PIB[^<]*</span>\s*<span[^>]*>(\d+)', html_text, re.IGNORECASE)
    pib = re.sub(r'<[^>]+>', '', pib_match.group(1)).strip() if pib_match else ""

    mb_match = re.search(r'MB[^<]*</span>\s*<span>(\d+)</span>', html_text, re.IGNORECASE)
    if not mb_match:
        mb_match = re.search(r'Matični broj:[^\d]*(\d+)', html_text, re.IGNORECASE)
    mb = re.sub(r'<[^>]+>', '', mb_match.group(1)).strip() if mb_match else ""

    # 4. Telefon Numaraları
    phones = set()
    for p in re.findall(r'(?:\+381|0)[0-9\s/\-]{7,15}', html_text):
        cleaned_phone = re.sub(r'[^\d+]', '', p)
        if len(cleaned_phone) >= 8 and not cleaned_phone.startswith("000"):
            phones.add(p.strip())

    # 5. E-Posta Adresleri
    raw_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html_text)
    emails = set()
    for e in raw_emails:
        el = e.lower().strip()
        if not any(ign in el for ign in ['companywall', 'facebook', 'google', 'sentry', 'w3.org', 'schema.org']):
            emails.add(el)

    return {
        "name": name,
        "address": address,
        "city": city,
        "pib": pib,
        "mb": mb,
        "phones": list(phones),
        "emails": list(emails),
        "companywall_url": url
    }


def crawl_companywall(max_pages: int = 10, delay_range: Tuple[float, float] = (1.0, 2.0)):
    """CompanyWall sayfalarını sırayla taranıp acenteler.db veritabanına aktarılır."""
    db.init_db()

    total_added = 0
    total_emails = 0
    total_phones = 0

    page = 1
    while True:
        if max_pages > 0 and page > max_pages:
            logger.info(f"Maksimum sayfa sınırına ({max_pages}) ulaşıldı.")
            break

        page_url = f"{SEARCH_URL}&p={page}"
        logger.info(f"CompanyWall Sayfa {page} taranıyor... ({page_url})")

        html_text = fetch_url_html(page_url)
        if not html_text:
            logger.warning(f"Sayfa {page} alınamadı veya son sayfaya ulaşıldı.")
            break

        company_links = extract_company_links_from_search_page(html_text)
        if not company_links:
            logger.info(f"Sayfa {page}'de daha fazla firma linki bulunamadı.")
            break

        logger.info(f"Sayfa {page}: Toplam {len(company_links)} firma bulundu. Detaylar çekiliyor...")

        for idx, link in enumerate(company_links, 1):
            detail_html = fetch_url_html(link)
            if not detail_html:
                continue

            company_data = parse_company_detail_page(link, detail_html)
            name = company_data["name"]

            if not name:
                continue

            # Veritabanına Ekle / Güncelle
            agency_id = db.add_or_get_agency(
                name=name,
                city=company_data["city"],
                address=company_data["address"],
                pib=company_data["pib"],
                mb=company_data["mb"],
                profile_url=company_data["companywall_url"]
            )

            # Telefonları Ekle
            for ph in company_data["phones"]:
                db.add_agency_phone(agency_id, ph)
                total_phones += 1

            # E-postaları Ekle
            for em in company_data["emails"]:
                db.add_agency_email(agency_id, em)
                total_emails += 1

            total_added += 1
            logger.info(f"  [{idx}/{len(company_links)}] {name} (PIB: {company_data['pib'] or '-'}, Şehir: {company_data['city'] or '-'}) -> DB ID: {agency_id}")

            time.sleep(random.uniform(*delay_range))

        page += 1

    logger.info(f"\n=======================================================")
    logger.info(f"CompanyWall Taraması Tamamlandı!")
    logger.info(f"İşlenen Firma Sayısı: {total_added}")
    logger.info(f"Eklenen E-Postalar  : {total_emails}")
    logger.info(f"Eklenen Telefonlar  : {total_phones}")
    logger.info(f"=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="CompanyWall.rs Emlak Şirketleri Kazıma Betiği")
    parser.add_argument("--max-pages", type=int, default=10, help="Taranacak maksimum arama sayfası sayısı (0 = tümü)")
    parser.add_argument("--min-delay", type=float, default=1.0, help="Sayfa arası minimum bekleme süresi (saniye)")
    parser.add_argument("--max-delay", type=float, default=2.0, help="Sayfa arası maksimum bekleme süresi (saniye)")

    args = parser.parse_args()

    crawl_companywall(max_pages=args.max_pages, delay_range=(args.min_delay, args.max_delay))


if __name__ == "__main__":
    main()
