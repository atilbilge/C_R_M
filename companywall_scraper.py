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
    """Firma detay sayfasındaki tüm kurumsal ve finansal verileri ayrıştırır (JSON-LD + DOM)."""
    res = {
        "name": "",
        "long_name": "",
        "establishment_date": "",
        "enterprise_size": "",
        "activity": "",
        "pib": "",
        "mb": "",
        "city": "",
        "address": "",
        "phones": set(),
        "emails": set(),
        "websites": set(),
        "employees_3yr": {},
        "income_3yr": {},
        "companywall_url": url
    }

    # 1. Unvan (H1)
    title_match = re.search(r'itemprop=["\']name["\'][^>]*>(.*?)</h1>', html_text, re.DOTALL)
    if not title_match:
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.DOTALL)
    name = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
    res["name"] = html.unescape(name)

    # 2. Yöntem 1: JSON Scriptleri (FAQPage, LocalBusiness, Dataset)
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html_text, re.DOTALL)
    for s in scripts:
        s_strip = s.strip()
        if s_strip.startswith('{') and s_strip.endswith('}'):
            try:
                data = json.loads(s_strip)
                t = data.get('@type')
                if t == 'LocalBusiness':
                    if data.get('name') and not res['long_name']:
                        res['long_name'] = html.unescape(data['name'])
                    addr = data.get('address', {})
                    if isinstance(addr, dict):
                        if addr.get('addressLocality') and not res['city']:
                            res['city'] = html.unescape(addr['addressLocality'])
                        if addr.get('streetAddress') and not res['address']:
                            res['address'] = html.unescape(addr['streetAddress'])
                    if data.get('telephone'):
                        ph_clean = re.sub(r'[^\d+]', '', data['telephone'])
                        if len(ph_clean) >= 8:
                            res['phones'].add(data['telephone'].strip())
                elif t == 'FAQPage':
                    for entity in data.get('mainEntity', []):
                        q = entity.get('name', '').lower()
                        ans = entity.get('acceptedAnswer', {}).get('text', '')
                        if ('datum osnivanja' in q or 'osnovan' in q) and not res['establishment_date']:
                            dm = re.search(r'\b(\d{1,2}\.\d{1,2}\.\d{4}\.?)', ans)
                            if dm: res['establishment_date'] = dm.group(1)
                elif t == 'Dataset':
                    for d in data.get('data', []):
                        yr = str(d.get('Godina') or d.get('Year') or '')
                        inc = d.get('Ukupni prihodi') or d.get('Total income')
                        if yr and inc:
                            res['income_3yr'][yr] = str(inc).strip()
            except Exception:
                pass

    # 3. Yöntem 2: DOM dt/dd Çiftleri (Basic Information & Contacts)
    dls = re.findall(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', html_text, re.DOTALL)
    for dt, dd in dls:
        c_dt = html.unescape(re.sub(r'<[^>]+>', '', dt)).strip()
        c_dd = html.unescape(re.sub(r'<[^>]+>', '', dd)).strip()
        c_dt_lower = c_dt.lower()

        if ('puno' in c_dt_lower or 'long name' in c_dt_lower or c_dt_lower == 'naziv') and not res['long_name']:
            res['long_name'] = c_dd
        elif ('datum osnivanja' in c_dt_lower or 'establishment' in c_dt_lower) and not res['establishment_date']:
            res['establishment_date'] = c_dd
        elif 'veli' in c_dt_lower or 'size' in c_dt_lower:
            res['enterprise_size'] = c_dd
        elif 'delatnost' in c_dt_lower or 'activity' in c_dt_lower:
            res['activity'] = c_dd
        elif 'pib' in c_dt_lower and not res['pib']:
            m = re.search(r'\d{8,9}', c_dd)
            if m: res['pib'] = m.group(0)
        elif ('mb' in c_dt_lower or 'matični' in c_dt_lower) and not res['mb']:
            m = re.search(r'\d{7,8}', c_dd)
            if m: res['mb'] = m.group(0)
        elif 'web' in c_dt_lower:
            found_urls = re.findall(r'(?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s"<>]*)?', dd)
            for w in found_urls:
                w_clean = w.strip().rstrip('.')
                if not any(ign in w_clean.lower() for ign in ['companywall', 'facebook', 'google', 'sentry', 'w3.org', 'schema.org']):
                    full_w = w_clean if w_clean.startswith('http') else 'https://' + w_clean
                    res['websites'].add(full_w)
        elif 'mail' in c_dt_lower:
            found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', dd)
            for em in found_emails:
                em_clean = em.lower().strip()
                if not any(ign in em_clean for ign in ['companywall', 'facebook', 'google', 'sentry', 'w3.org']):
                    res['emails'].add(em_clean)

    # 4. Fallback PIB / MB
    if not res['pib']:
        pib_match = re.search(r'itemprop=["\']vatID["\'][^>]*>(.*?)</span>', html_text, re.DOTALL)
        if not pib_match:
            pib_match = re.search(r'PIB[^<]*</span>\s*<span[^>]*>(\d+)', html_text, re.IGNORECASE)
        res['pib'] = re.sub(r'<[^>]+>', '', pib_match.group(1)).strip() if pib_match else ""

    if not res['mb']:
        mb_match = re.search(r'MB[^<]*</span>\s*<span>(\d+)</span>', html_text, re.IGNORECASE)
        if not mb_match:
            mb_match = re.search(r'Matični broj:[^\d]*(\d+)', html_text, re.IGNORECASE)
        res['mb'] = re.sub(r'<[^>]+>', '', mb_match.group(1)).strip() if mb_match else ""

    # 5. 3 Yıllık Çalışan ve Finansal Tablo (table.document-detail-inline & data-title)
    tbl_match = re.search(r'<table[^>]*class=["\'][^"\']*document-detail-inline[^"\']*["\'][^>]*>(.*?)</table>', html_text, re.DOTALL)
    if tbl_match:
        tbl_html = tbl_match.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl_html, re.DOTALL)
        for r in rows:
            label_match = re.search(r'<span[^>]*>(.*?)</span>', r, re.DOTALL)
            if not label_match: continue
            label = html.unescape(re.sub(r'<[^>]+>', '', label_match.group(1))).strip().lower()

            val_tds = re.findall(r'<td[^>]*data-title=["\'](\d{4})["\'][^>]*>(.*?)</td>', r, re.DOTALL)
            for yr, val_raw in val_tds:
                val = html.unescape(re.sub(r'<[^>]+>', '', val_raw)).strip()
                if label == 'broj zaposlenih' or label == 'number of employees':
                    res['employees_3yr'][yr] = val
                elif label == 'ukupni prihodi' or label == 'total income':
                    res['income_3yr'][yr] = val

    # 6. Genel Sayfa Telefon & E-posta Taraması
    for p in re.findall(r'(?:\+381|0)[0-9\s/\-]{7,15}', html_text):
        cleaned_phone = re.sub(r'[^\d+]', '', p)
        if len(cleaned_phone) >= 8 and not cleaned_phone.startswith("000"):
            res['phones'].add(p.strip())

    for e in re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html_text):
        el = e.lower().strip()
        if not any(ign in el for ign in ['companywall', 'facebook', 'google', 'sentry', 'w3.org', 'schema.org']):
            res['emails'].add(el)

    return res


def crawl_companywall(max_pages: int = 10, delay_range: Tuple[float, float] = (1.0, 2.0)):
    """CompanyWall sayfalarını sırayla taranıp acenteler.db veritabanına aktarılır."""
    import json
    db.init_db()

    total_added = 0
    total_emails = 0
    total_phones = 0
    total_websites = 0

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

            # Zengin Kurumsal/Finansal Bilgileri Güncelle
            db.update_agency_rich_info(
                agency_id=agency_id,
                long_name=company_data["long_name"],
                establishment_date=company_data["establishment_date"],
                enterprise_size=company_data["enterprise_size"],
                employees_json=json.dumps(company_data["employees_3yr"], ensure_ascii=False) if company_data["employees_3yr"] else "",
                income_json=json.dumps(company_data["income_3yr"], ensure_ascii=False) if company_data["income_3yr"] else ""
            )

            # Telefonları Ekle
            for ph in company_data["phones"]:
                db.add_agency_phone(agency_id, ph)
                total_phones += 1

            # E-postaları Ekle
            for em in company_data["emails"]:
                db.add_agency_email(agency_id, em)
                total_emails += 1

            # Resmi Web Sitelerini Ekle
            for web_url in company_data["websites"]:
                db.add_agency_website(agency_id, web_url, site_type="website")
                total_websites += 1

            total_added += 1
            emp_info = company_data["employees_3yr"]
            inc_info = company_data["income_3yr"]
            logger.info(f"  [{idx}/{len(company_links)}] {name} (Long: {company_data['long_name'] or '-'}, Kur: {company_data['establishment_date'] or '-'}, Çalışan: {emp_info or '-'}) -> DB ID: {agency_id}")

            time.sleep(random.uniform(*delay_range))

        page += 1

    logger.info(f"\n=======================================================")
    logger.info(f"CompanyWall Taraması Tamamlandı!")
    logger.info(f"İşlenen Firma Sayısı: {total_added}")
    logger.info(f"Eklenen E-Postalar  : {total_emails}")
    logger.info(f"Eklenen Telefonlar  : {total_phones}")
    logger.info(f"Eklenen Web Siteleri : {total_websites}")
    logger.info(f"=======================================================\n")
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
