#!/usr/bin/env python3
"""
enrich_agency_emails.py
------------------------
Veritabanında (`acenteler.db`) e-postası olmayan acentelerin harici (kendi) web sitelerini
(libero.rs, feniks.rs vb.) tarayarak e-posta adreslerini (info@, office@, kontakt@) otomatik
bulan ve `agency_emails` tablosuna ekleyen zenginleştirme betiği.

Özellikler:
- Portalları (kaza.rs, nekretnine.rs, indomio.rs, facebook, instagram vb.) otomatik eler.
- Ana sayfadaki mailto: bağlantılarını ve regex e-posta kalıplarını tarar.
- E-posta bulunamazsa `/kontakt`, `/contact`, `/o-nama` ve ana sayfadaki iletişim sayfalarını tarar.
- Görsel/CSS uzantılı sahte e-postaları (.png, .jpg, @sentry.io, @2x vb.) filtreler.
- Çoklu iş parçacığı (ThreadPoolExecutor) ile yüksek hızda çalışır.
"""

import os
import sys
import re
import time
import sqlite3
import random
from typing import List, Set, Dict, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acenteler.db")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enrich_emails.log")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
]

# Elenecek alan adları ve uzantılar
EXCLUDED_DOMAINS = [
    "kaza.rs", "nekretnine.rs", "indomio.rs", "companywall.rs", "linkedin.com",
    "facebook.com", "instagram.com", "youtube.com", "twitter.com", "x.com",
    "google.com", "wixpress.com", "sentry.io", "schema.org", "wordpress.org"
]

EXCLUDED_EMAIL_PATTERNS = [
    "example.com", "domain.com", "yourdomain.com", "email.com", "test.com",
    "sentry.io", "wixpress.com", "schema.org", "glitchtip.com", "opencart.com",
    "wordpress.org", "github.com", "elementor.com", "cloudflare.com", "google.com",
    "facebook.com", "@2x", "@3x", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".js", ".css"
]

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


def log(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def is_valid_email(email: str) -> bool:
    """E-postanın geçerli ve gerçek bir iletişim adresi olup olmadığını doğrular."""
    if not email or "@" not in email:
        return False
    email = email.lower().strip().strip(".:;,")
    
    # Uzantı ve sahte desen kontrolleri
    for pat in EXCLUDED_EMAIL_PATTERNS:
        if pat in email:
            return False
            
    # TLD kontrolü (.com, .rs, .net vb.)
    parts = email.split("@")
    if len(parts) != 2:
        return False
    domain = parts[1]
    if "." not in domain or len(domain.split(".")[-1]) < 2:
        return False
        
    return True


def clean_email(email: str) -> str:
    """E-postadaki gereksiz ekleri ve noktalama işaretlerini temizler."""
    email = email.strip().strip(".:;,")
    if email.startswith("mailto:"):
        email = email.replace("mailto:", "").split("?")[0]
    return email.lower().strip()


def extract_emails_from_html(html: str, base_url: str) -> Set[str]:
    """HTML içeriğinden mailto ve regex ile e-postaları filtreleyerek çıkarır."""
    found_emails = set()
    soup = BeautifulSoup(html, "html.parser")

    # 1. mailto: etiketleri
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            em = clean_email(href)
            if is_valid_email(em):
                found_emails.add(em)

    # 2. Metin içerisindeki regex kalıpları
    raw_matches = EMAIL_REGEX.findall(html)
    for em in raw_matches:
        cleaned = clean_email(em)
        if is_valid_email(cleaned):
            found_emails.add(cleaned)

    return found_emails


def fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    """CURL Impersonate ile TLS korumalı URL isteği atar."""
    url = url.replace(" ", "").strip()
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sr,en-US;q=0.9,en;q=0.8",
    }
    try:
        resp = cffi_requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
        if resp.status_code == 200 and resp.text:
            return resp.text
    except Exception:
        pass
    return None


def process_agency(agency: Dict[str, Any]) -> Tuple[int, str, List[str]]:
    """Tek bir acentenin harici web sitesini ve iletişim sayfalarını tarar."""
    ag_id = agency["id"]
    ag_name = agency["name"]
    site_url = agency["url"].replace(" ", "").strip()

    if not site_url.startswith("http://") and not site_url.startswith("https://"):
        site_url = "https://" + site_url

    emails_found = set()

    # 1. Ana Sayfayı Çek ve Tara
    html = fetch_url(site_url)
    if html:
        emails_found.update(extract_emails_from_html(html, site_url))

    # 2. E-posta bulunamadıysa İletişim / Kontakt Sayfalarını Tara
    if not emails_found and html:
        soup = BeautifulSoup(html, "html.parser")
        contact_links = []

        # Sayfa içi iletişim bağlantılarını tespit et
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text().strip().lower()
            href_lower = href.lower()
            
            if any(k in href_lower or k in text for k in ["kontakt", "contact", "o-nama", "about", "impresum"]):
                full_link = urljoin(site_url, href)
                parsed = urlparse(full_link)
                if parsed.netloc == urlparse(site_url).netloc:
                    contact_links.append(full_link)

        # Bilinen standart iletişim yollarını da ekle
        base_domain = f"{urlparse(site_url).scheme}://{urlparse(site_url).netloc}"
        standard_paths = [f"{base_domain}/kontakt", f"{base_domain}/contact", f"{base_domain}/o-nama"]
        for sp in standard_paths:
            if sp not in contact_links:
                contact_links.append(sp)

        # Bulunan iletişim sayfalarını dene (maksimum 3 sayfa)
        for cl in list(set(contact_links))[:3]:
            c_html = fetch_url(cl, timeout=8)
            if c_html:
                c_emails = extract_emails_from_html(c_html, cl)
                if c_emails:
                    emails_found.update(c_emails)
                    break

    return ag_id, ag_name, list(emails_found)


def enrich_agency_emails(source_filter: Optional[str] = None, max_workers: int = 8):
    """E-postası eksik olan acenteleri harici sitelerinden tarayarak veritabanını günceller."""
    log("🚀 Web Sitesinden E-posta Zenginleştirme İşlemi Başlatılıyor...")

    conn = get_db_connection()
    cur = conn.cursor()

    sql = """
        SELECT DISTINCT a.id, a.name, w.url
        FROM agencies a
        JOIN agency_websites w ON a.id = w.agency_id
        LEFT JOIN agency_emails e ON a.id = e.agency_id
        WHERE (e.email IS NULL OR e.email = '')
        AND w.url NOT LIKE '%kaza.rs%'
        AND w.url NOT LIKE '%nekretnine.rs%'
        AND w.url NOT LIKE '%indomio.rs%'
        AND w.url NOT LIKE '%companywall.rs%'
        AND w.url NOT LIKE '%linkedin.com%'
        AND w.url NOT LIKE '%facebook.com%'
        AND w.url NOT LIKE '%instagram.com%'
        AND w.url NOT LIKE '%youtube.com%'
        AND w.url NOT LIKE '%twitter.com%'
        AND w.url NOT LIKE '%x.com%'
    """
    params = []
    if source_filter:
        sql += " AND a.source = ?"
        params.append(source_filter)

    sql += " GROUP BY a.id ORDER BY a.id ASC"

    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    total_target = len(rows)
    log(f"📋 Taranacak E-postası Olmayan Harici Web Siteli Acente Sayısı: {total_target}")

    if total_target == 0:
        log("✅ Taranacak eksik acente bulunamadı.")
        return

    found_count = 0
    added_emails_total = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_agency, row): row for row in rows}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            ag_id, ag_name, emails = future.result()

            if emails:
                found_count += 1
                conn = get_db_connection()
                cur = conn.cursor()
                for em in emails:
                    try:
                        cur.execute("""
                            INSERT OR IGNORE INTO agency_emails (agency_id, email, created_at)
                            VALUES (?, ?, datetime('now'))
                        """, (ag_id, em))
                        if cur.rowcount > 0:
                            added_emails_total += 1
                    except Exception:
                        pass
                conn.commit()
                conn.close()

                log(f" [{completed}/{total_target}] 🎉 BULUNDU! ID={ag_id} | {ag_name} -> {', '.join(emails)}")
            else:
                if completed % 25 == 0 or completed == total_target:
                    log(f" [{completed}/{total_target}] 🔍 İşleniyor... (Şu ana kadar {found_count} acenteye {added_emails_total} e-posta bulundu)")

    log(f"🎉 E-posta Zenginleştirme Tamamlandı! İşlenen Acente: {total_target} | E-postası Bulunan Acente: {found_count} | Eklenen Toplam E-posta: {added_emails_total}")


if __name__ == "__main__":
    src_filter = sys.argv[1] if len(sys.argv) > 1 else None
    enrich_agency_emails(source_filter=src_filter)
