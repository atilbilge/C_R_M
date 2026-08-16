#!/usr/bin/env python3
"""
scan_contact_forms.py
---------------------
Acentelerin kendi web sitelerindeki doğrudan web mesaj / iletişim formlarını
(name, email, message/poruka girdileri içeren <form> etiketleri) ve tam form URL'lerini
(kontakt.html, kontakt-opcije.html, contact-us vb.) otomatik tespit edip `agency_websites`
tablosuna `type = 'contact_form'` olarak kaydeden betik.
"""

import os
import sys
import time
import sqlite3
import random
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acenteler.db")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contact_forms.log")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


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


def is_contact_form(form_el: BeautifulSoup) -> bool:
    """Bir <form> etiketinin mesaj gönderme iletişim formu olup olmadığını doğrular."""
    inputs = []
    for inp in form_el.find_all(["input", "textarea", "select"]):
        name = (inp.get("name") or "").lower()
        inp_id = (inp.get("id") or "").lower()
        inp_type = (inp.get("type") or "").lower()
        inputs.append(f"{name} {inp_id} {inp_type}")
        
    inp_str = " ".join(inputs)
    has_email = any(k in inp_str for k in ["email", "mail", "sender"])
    has_msg = any(k in inp_str for k in ["message", "poruka", "text", "comment", "sadrzaj", "upit", "body"])
    has_name = any(k in inp_str for k in ["name", "ime", "naslov", "subject"])
    
    return has_email and (has_msg or has_name)


def detect_agency_contact_form(agency: Dict[str, Any]) -> Tuple[int, str, Optional[str]]:
    """Tek bir acentenin web sitesindeki aktif iletişim formunu bulur."""
    ag_id = agency["id"]
    ag_name = agency["name"]
    site_url = agency["url"].replace(" ", "").strip()

    if not site_url.startswith("http://") and not site_url.startswith("https://"):
        site_url = "https://" + site_url

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = cffi_requests.get(site_url, headers=headers, timeout=10, verify=False, allow_redirects=True)
        if resp.status_code != 200 or not resp.text:
            return ag_id, ag_name, None

        html = resp.text
        curr_url = resp.url
        soup = BeautifulSoup(html, "html.parser")

        # 1. Ana Sayfa Form Kontrolü
        for form in soup.find_all("form"):
            if is_contact_form(form):
                return ag_id, ag_name, curr_url

        # 2. İletişim / Kontakt Bağlantılarını Tara
        contact_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text().strip().lower()
            href_lower = href.lower()

            if any(k in href_lower or k in text for k in ["kontakt", "contact", "o-nama", "about", "impresum", "upit"]):
                full_link = urljoin(curr_url, href)
                parsed = urlparse(full_link)
                if parsed.netloc == urlparse(curr_url).netloc:
                    contact_links.append(full_link)

        # Standart Yollar
        parsed_base = urlparse(curr_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
        standard_paths = [
            f"{base_domain}/kontakt", f"{base_domain}/contact", f"{base_domain}/kontakt.html",
            f"{base_domain}/kontakt-opcije.html", f"{base_domain}/o-nama"
        ]
        for sp in standard_paths:
            if sp not in contact_links:
                contact_links.append(sp)

        # İletişim Sayfalarını Teker Teker İncele (Maksimum 4 Sayfa)
        for cl in list(set(contact_links))[:4]:
            try:
                c_resp = cffi_requests.get(cl, headers=headers, timeout=8, verify=False, allow_redirects=True)
                if c_resp.status_code == 200 and c_resp.text:
                    c_soup = BeautifulSoup(c_resp.text, "html.parser")
                    for form in c_soup.find_all("form"):
                        if is_contact_form(form):
                            return ag_id, ag_name, c_resp.url
            except Exception:
                pass

    except Exception:
        pass

    return ag_id, ag_name, None


def scan_all_contact_forms(max_workers: int = 10):
    """Veritabanındaki tüm harici acente sitelerini tarayarak mesaj formlarını tespit eder."""
    log("🚀 Acente Web Mesaj Formları Taraması Başlatılıyor...")

    conn = get_db_connection()
    cur = conn.cursor()

    sql = """
        SELECT DISTINCT a.id, a.name, w.url
        FROM agencies a
        JOIN agency_websites w ON a.id = w.agency_id
        WHERE w.url NOT LIKE '%kaza.rs%'
        AND w.url NOT LIKE '%nekretnine.rs%'
        AND w.url NOT LIKE '%indomio.rs%'
        AND w.url NOT LIKE '%companywall.rs%'
        AND w.url NOT LIKE '%linkedin.com%'
        AND w.url NOT LIKE '%facebook.com%'
        AND w.url NOT LIKE '%instagram.com%'
        AND w.url NOT LIKE '%youtube.com%'
        AND w.url NOT LIKE '%twitter.com%'
        AND w.url NOT LIKE '%x.com%'
        GROUP BY a.id ORDER BY a.id ASC
    """

    cur.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    total_sites = len(rows)
    log(f"📋 Taranacak Harici Web Siteli Acente Sayısı: {total_sites}")

    if total_sites == 0:
        log("✅ Taranacak harici site bulunamadı.")
        return

    forms_found = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(detect_agency_contact_form, row): row for row in rows}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            ag_id, ag_name, form_url = future.result()

            if form_url:
                forms_found += 1
                conn = get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO agency_websites (agency_id, url, type)
                        VALUES (?, ?, 'contact_form')
                    """, (ag_id, form_url))
                    conn.commit()
                except Exception:
                    pass
                conn.close()

                log(f" [{completed}/{total_sites}] 🎯 FORM BULUNDU! ID={ag_id} | {ag_name} -> {form_url}")
            else:
                if completed % 50 == 0 or completed == total_sites:
                    log(f" [{completed}/{total_sites}] 🔍 İşleniyor... (Şu ana kadar {forms_found} acentede mesaj formu bulundu)")

    log(f"🎉 Mesaj Formu Taraması Tamamlandı! İşlenen Site: {total_sites} | Mesaj Formu Bulunan Acente: {forms_found}")


if __name__ == "__main__":
    scan_all_contact_forms()
