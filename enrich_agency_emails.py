#!/usr/bin/env python3
"""
enrich_agency_emails.py
------------------------
Veritabanında (`acenteler.db`) e-postası olmayan acentelerin harici (kendi) web sitelerini
(libero.rs, feniks.rs, ags-nekretnine.com, coronasmnekretnine.com, gaknekretnine.com vb.) tarayarak
e-posta adreslerini (info@, office@, kontakt@) otomatik bulan ve `agency_emails` tablosuna ekleyen zenginleştirme betiği.

Gelişmiş Özellikler:
- Portalları (kaza.rs, nekretnine.rs, indomio.rs, facebook, instagram vb.) otomatik eler.
- Cloudflare Email Protection (`data-cfemail` ve `/cdn-cgi/l/email-protection#...`) korumasını otomatik çözer (XOR Decoder).
- Cloudflare 403 Turnstile engeli bulunan siteler için DuckDuckGo Arama İndeksi yedeklemesini (`site:domain.com`) kullanır.
- Ana sayfadaki mailto: bağlantılarını ve regex e-posta kalıplarını tarar.
- JS yönlendirmelerini (window.location, location.href) ve Meta Refresh etiketlerini takip eder.
- E-posta bulunamazsa `/kontakt`, `/contact`, `/o-nama`, `/kontakt-opcije` ve ana sayfadaki iletişim sayfalarını tarar.
- Görsel/CSS/Yazılım satıcı uzantılı sahte e-postaları (.png, .jpg, @sentry.io, @glitchtip, @2x vb.) filtreler.
- URL-encoded e-postaları (%20kontakt@...) otomatik çözer (unquote).
- Çoklu iş parçacığı (ThreadPoolExecutor) ile yüksek hızda çalışır.
"""

import os
import sys
import re
import time
import sqlite3
import random
from typing import List, Set, Dict, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse, unquote
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

EXCLUDED_EMAIL_PATTERNS = [
    "example.com", "domain.com", "yourdomain.com", "email.com", "test.com",
    "sentry.io", "wixpress.com", "schema.org", "glitchtip.com", "opencart.com",
    "wordpress.org", "github.com", "elementor.com", "cloudflare.com", "google.com",
    "facebook.com", "pravnakomora.rs", "vortexdesign.net", "la-studioweb.com",
    "favethemes.com", "duckduckgo.com", "bing.com", "@2x", "@3x", ".png", ".jpg",
    ".jpeg", ".gif", ".svg", ".webp", ".js", ".css"
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


def decode_cloudflare_email(cfemail_hex: str) -> str:
    """Cloudflare Email Protection hex dizesini XOR anahtarıyla gerçek e-postaya dönüştürür."""
    try:
        r = int(cfemail_hex[:2], 16)
        email_chars = []
        for n in range(2, len(cfemail_hex), 2):
            char_code = int(cfemail_hex[n:n+2], 16) ^ r
            email_chars.append(chr(char_code))
        return "".join(email_chars)
    except Exception:
        return ""


def clean_email(email: str) -> str:
    """URL-encoded karaketerleri çözüp e-postadaki gereksiz ekleri temizler."""
    email = unquote(email).strip().strip(".:;,")
    if email.lower().startswith("mailto:"):
        email = email[7:].split("?")[0]
    return email.lower().strip()


def is_valid_email(email: str) -> bool:
    """E-postanın geçerli ve gerçek bir iletişim adresi olup olmadığını doğrular."""
    if not email or "@" not in email:
        return False
    email = clean_email(email)
    
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


def extract_emails_from_html(html: str) -> Set[str]:
    """HTML içeriğinden mailto, Cloudflare Email Protection ve regex ile e-postaları çıkarır."""
    found_emails = set()
    soup = BeautifulSoup(html, "html.parser")

    # 1. mailto: ve Cloudflare link etiketleri
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            em = clean_email(href)
            if is_valid_email(em):
                found_emails.add(em)
        elif "email-protection#" in href:
            hex_str = href.split("email-protection#")[-1].split("?")[0].strip()
            decoded = clean_email(decode_cloudflare_email(hex_str))
            if is_valid_email(decoded):
                found_emails.add(decoded)

    # 2. Cloudflare data-cfemail öznitelikleri
    for el in soup.find_all(attrs={"data-cfemail": True}):
        decoded = clean_email(decode_cloudflare_email(el["data-cfemail"]))
        if is_valid_email(decoded):
            found_emails.add(decoded)

    # 3. Cloudflare regex araması (HTML genelinde)
    for m in re.findall(r'email-protection#([a-fA-F0-9]+)', html):
        decoded = clean_email(decode_cloudflare_email(m))
        if is_valid_email(decoded):
            found_emails.add(decoded)

    for m in re.findall(r'data-cfemail=["\']([a-fA-F0-9]+)["\']', html):
        decoded = clean_email(decode_cloudflare_email(m))
        if is_valid_email(decoded):
            found_emails.add(decoded)

    # 4. Düz metin regex kalıpları
    raw_matches = EMAIL_REGEX.findall(html)
    for em in raw_matches:
        cleaned = clean_email(em)
        if is_valid_email(cleaned):
            found_emails.add(cleaned)

    return found_emails


def fetch_url_with_redirects(url: str, timeout: int = 10, max_redirects: int = 3) -> Tuple[Optional[str], str]:
    """
    HTTP 301/302 yanı sıra JS Redirect (window.location) ve Meta Refresh etiketlerini
    otomatik takip eden gelişmiş URL çekme fonksiyonu.
    """
    if max_redirects <= 0:
        return None, url

    url = url.replace(" ", "").strip()
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sr,en-US;q=0.9,en;q=0.8",
    }
    
    try:
        resp = cffi_requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
        if resp.status_code != 200 or not resp.text:
            return None, url
            
        html = resp.text
        curr_url = resp.url

        soup = BeautifulSoup(html, "html.parser")

        # 1. Meta Refresh kontrolü
        meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
        if meta_refresh and "content" in meta_refresh.attrs:
            content = meta_refresh["content"]
            if "url=" in content.lower():
                redirect_url = content.split("url=")[-1].strip(" \"'").strip()
                if redirect_url:
                    full_redirect = urljoin(curr_url, redirect_url)
                    return fetch_url_with_redirects(full_redirect, timeout, max_redirects - 1)

        # 2. JS location redirect kontrolü
        js_match = re.search(r'(?:window\.|document\.)?location(?:\.href|\.replace)?\s*(?:=|\()\s*["\']([^"\']+)["\']', html, re.I)
        if js_match:
            redirect_url = js_match.group(1).strip()
            if redirect_url and not redirect_url.startswith("javascript:") and redirect_url != curr_url:
                full_redirect = urljoin(curr_url, redirect_url)
                return fetch_url_with_redirects(full_redirect, timeout, max_redirects - 1)

        # 3. Frame / Iframe kontrolü (ana sayfada bağlantı yoksa)
        if len(soup.find_all("a")) == 0:
            frames = soup.find_all(["frame", "iframe"], src=True)
            if frames:
                frame_src = frames[0]["src"].strip()
                if frame_src:
                    full_redirect = urljoin(curr_url, frame_src)
                    return fetch_url_with_redirects(full_redirect, timeout, max_redirects - 1)

        return html, curr_url
    except Exception:
        pass

    return None, url


def search_duckduckgo_emails(domain: str) -> Set[str]:
    """Sitenin kendisinden e-posta alınamazsa veya 403 Cloudflare engeli varsa DDG arama indeksinden e-postayı çeker."""
    if not domain or len(domain) < 4:
        return set()
    url = f"https://html.duckduckgo.com/html/?q=site:{domain}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    found_emails = set()
    try:
        resp = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=10)
        if resp.status_code == 200 and resp.text:
            raw_matches = EMAIL_REGEX.findall(resp.text)
            for em in raw_matches:
                cleaned = clean_email(em)
                if is_valid_email(cleaned) and not any(p in cleaned for p in ["duckduckgo", "bing", "google"]):
                    found_emails.add(cleaned)
    except Exception:
        pass
    return found_emails


def process_agency(agency: Dict[str, Any]) -> Tuple[int, str, List[str]]:
    """Tek bir acentenin harici web sitesini ve iletişim sayfalarını JS, Cloudflare ve Arama İndeksi ile tarar."""
    ag_id = agency["id"]
    ag_name = agency["name"]
    site_url = agency["url"].replace(" ", "").strip()

    if not site_url.startswith("http://") and not site_url.startswith("https://"):
        site_url = "https://" + site_url

    emails_found = set()

    # 1. Ana Sayfayı Çek ve Tara
    html, final_url = fetch_url_with_redirects(site_url)
    if html:
        emails_found.update(extract_emails_from_html(html))

    # 2. E-posta bulunamadıysa İletişim / Kontakt Sayfalarını Tara
    if not emails_found and html:
        soup = BeautifulSoup(html, "html.parser")
        contact_links = []

        # Sayfa içi iletişim bağlantılarını tespit et
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text().strip().lower()
            href_lower = href.lower()
            
            if any(k in href_lower or k in text for k in ["kontakt", "contact", "o-nama", "about", "impresum", "poslovanje", "tim"]):
                full_link = urljoin(final_url, href)
                parsed = urlparse(full_link)
                if parsed.netloc == urlparse(final_url).netloc:
                    contact_links.append(full_link)

        # Bilinen standart iletişim yollarını da ekle
        parsed_base = urlparse(final_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
        standard_paths = [
            f"{base_domain}/kontakt", f"{base_domain}/contact", f"{base_domain}/o-nama",
            f"{base_domain}/kontakt.html", f"{base_domain}/kontakt-opcije.html"
        ]
        for sp in standard_paths:
            if sp not in contact_links:
                contact_links.append(sp)

        # Bulunan iletişim sayfalarını dene (maksimum 4 sayfa)
        for cl in list(set(contact_links))[:4]:
            c_html, c_final = fetch_url_with_redirects(cl, timeout=8)
            if c_html:
                c_emails = extract_emails_from_html(c_html)
                if c_emails:
                    emails_found.update(c_emails)
                    break

    # 3. Hala E-posta bulunamadıysa (403 Cloudflare engeli veya doğrudan gizlenme durumunda) Arama İndeksinden Çek
    if not emails_found:
        parsed_domain = urlparse(site_url).netloc.replace("www.", "")
        ddg_emails = search_duckduckgo_emails(parsed_domain)
        if ddg_emails:
            emails_found.update(ddg_emails)

    return ag_id, ag_name, list(emails_found)


def enrich_agency_emails(source_filter: Optional[str] = None, max_workers: int = 8):
    """E-postası eksik olan acenteleri harici sitelerinden tarayarak veritabanını günceller."""
    log("🚀 Cloudflare, JS & Search Index Destekli Web Sitesi E-posta Zenginleştirme İşlemi Başlatılıyor...")

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
