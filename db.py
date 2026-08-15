#!/usr/bin/env python3
"""
acenteler.db Veritabanı Modülü
------------------------------
Acenteler, iletişim bilgileri, iletişim tarihçesi ve referans sistemi için SQLite veritabanı işlemlerini yürütür.
"""

import sqlite3
import os
import re
import json
import secrets
import string
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acenteler.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Veritabanı bağlantısı açar ve foreign key desteğini etkinleştirir."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH):
    """Veritabanı tablolarını ve indekslerini oluşturur."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Acenteler Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        city TEXT,
        address TEXT,
        pib TEXT,
        mb TEXT,
        license_no TEXT,
        contact_person TEXT,
        status TEXT DEFAULT 'NEW',
        ref_code TEXT UNIQUE NOT NULL,
        referred_by_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referred_by_id) REFERENCES agencies(id) ON DELETE SET NULL
    );
    """)

    # Migration checks for existing DB
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN pib TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN mb TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN license_no TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN contact_person TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN long_name TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN establishment_date TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN enterprise_size TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN employees_json TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN income_json TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN segment TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE agencies ADD COLUMN activity_code TEXT;")
    except sqlite3.OperationalError:
        pass

    # 2. Telefon Numaraları Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agency_phones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agency_id INTEGER NOT NULL,
        phone TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (agency_id) REFERENCES agencies(id) ON DELETE CASCADE,
        UNIQUE(agency_id, phone)
    );
    """)

    # 3. E-Posta Adresleri Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agency_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agency_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (agency_id) REFERENCES agencies(id) ON DELETE CASCADE,
        UNIQUE(agency_id, email)
    );
    """)

    # 4. İnternet / Profil Adresleri Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agency_websites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agency_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        type TEXT DEFAULT 'website',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (agency_id) REFERENCES agencies(id) ON DELETE CASCADE,
        UNIQUE(agency_id, url)
    );
    """)

    # 5. İletişim Tarihçesi Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS communications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agency_id INTEGER NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sender TEXT NOT NULL,
        recipient TEXT NOT NULL,
        message TEXT NOT NULL,
        channel TEXT DEFAULT 'NEKRETNINE_FORM',
        status TEXT DEFAULT 'SENT',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (agency_id) REFERENCES agencies(id) ON DELETE CASCADE
    );
    """)

    # 6. Referans Sistemi Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_agency_id INTEGER NOT NULL,
        referred_agency_id INTEGER NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        code_used TEXT,
        status TEXT DEFAULT 'PENDING',
        FOREIGN KEY (referrer_agency_id) REFERENCES agencies(id) ON DELETE CASCADE,
        FOREIGN KEY (referred_agency_id) REFERENCES agencies(id) ON DELETE CASCADE,
        UNIQUE(referrer_agency_id, referred_agency_id)
    );
    """)

    # 7. Sistem Meta Verileri Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 8. E-posta Kampanyaları Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subject TEXT NOT NULL,
        body_html TEXT NOT NULL,
        sender_name TEXT DEFAULT 'Stanomer Ekibi',
        sender_email TEXT DEFAULT 'atilbilge@gmail.com',
        target_filter_json TEXT DEFAULT '{}',
        lang TEXT DEFAULT 'SR_LAT',
        status TEXT DEFAULT 'DRAFT',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Migration for campaigns.lang
    try:
        cursor.execute("ALTER TABLE campaigns ADD COLUMN lang TEXT DEFAULT 'SR_LAT';")
    except sqlite3.OperationalError:
        pass

    # Migration for communications.campaign_id
    try:
        cursor.execute("ALTER TABLE communications ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL;")
    except sqlite3.OperationalError:
        pass

    # 9. Abonelikten Çıkanlar (Unsubscribes) Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS unsubscribes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        agency_id INTEGER,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # İndeksler
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_name ON agencies(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_city ON agencies(city);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_status ON agencies(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_ref_code ON agencies(ref_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_url ON agency_websites(url);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_communications_agency_id ON communications(agency_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_unsubscribes_email ON unsubscribes(email);")

    conn.commit()
    conn.close()


def generate_ref_code(prefix: str = "REF") -> str:
    """Acente için benzersiz bir referans kodu üretir."""
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(6))
    return f"{prefix}-{random_part}"


def add_or_get_agency(
    name: str,
    city: str = "",
    address: str = "",
    pib: str = "",
    mb: str = "",
    license_no: str = "",
    contact_person: str = "",
    status: str = "NEW",
    profile_url: str = "",
    db_path: str = DB_PATH
) -> int:
    """
    Acenteyi ekler veya var olan acenteyi PIB/MB/profil linki/adına göre bulup ID'sini döner.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    name = name.strip()
    city = city.strip()
    address = address.strip()
    pib = pib.strip()
    mb = mb.strip()
    license_no = license_no.strip()
    contact_person = contact_person.strip()

    agency_id = None

    # 1. PIB veya MB'ye göre var olan acenteyi ara
    if pib and pib != "N/A":
        cursor.execute("SELECT id FROM agencies WHERE pib = ?", (pib,))
        row = cursor.fetchone()
        if row:
            agency_id = row['id']

    if not agency_id and mb and mb != "N/A":
        cursor.execute("SELECT id FROM agencies WHERE mb = ?", (mb,))
        row = cursor.fetchone()
        if row:
            agency_id = row['id']

    # 2. Profil URL'sine göre var olan acenteyi ara
    if not agency_id and profile_url:
        cursor.execute(
            "SELECT agency_id FROM agency_websites WHERE url = ?", (profile_url.strip(),)
        )
        row = cursor.fetchone()
        if row:
            agency_id = row['agency_id']

    # 3. İsim ve şehre göre var olan acenteyi ara (eğer URL ile bulunamadıysa)
    if not agency_id and name:
        cursor.execute(
            "SELECT id FROM agencies WHERE LOWER(name) = LOWER(?)", (name,)
        )
        row = cursor.fetchone()
        if row:
            agency_id = row['id']
        else:
            clean_name = re.sub(r'(?i)\bnekretnine\b|\bdoo\b|\bd.o.o.\b|\bpr\b', '', name).strip().lower()
            if len(clean_name) >= 3:
                cursor.execute(
                    "SELECT id FROM agencies WHERE LOWER(name) LIKE ?",
                    (f"%{clean_name}%",)
                )
                row = cursor.fetchone()
                if row:
                    agency_id = row['id']

    # 4. Bulunamadıysa yeni acente oluştur
    if not agency_id:
        ref_code = generate_ref_code()
        while True:
            cursor.execute("SELECT id FROM agencies WHERE ref_code = ?", (ref_code,))
            if not cursor.fetchone():
                break
            ref_code = generate_ref_code()

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO agencies (name, city, address, pib, mb, license_no, contact_person, status, ref_code, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, city, address, pib, mb, license_no, contact_person, status, ref_code, now, now))
        agency_id = cursor.lastrowid
    else:
        # Var olan acente bilgilerini güncelle (şehir/adres/pib/mb/lisans/yetkili kişi boşsa doldur)
        cursor.execute("SELECT city, address, pib, mb, license_no, contact_person FROM agencies WHERE id = ?", (agency_id,))
        curr = cursor.fetchone()
        if curr:
            new_city = city if not curr['city'] else curr['city']
            new_address = address if not curr['address'] else curr['address']
            new_pib = pib if not curr['pib'] else curr['pib']
            new_mb = mb if not curr['mb'] else curr['mb']
            new_license = license_no if not curr['license_no'] else curr['license_no']
            new_contact = contact_person if not curr['contact_person'] else curr['contact_person']
            cursor.execute(
                "UPDATE agencies SET city = ?, address = ?, pib = ?, mb = ?, license_no = ?, contact_person = ?, updated_at = ? WHERE id = ?",
                (new_city, new_address, new_pib, new_mb, new_license, new_contact, datetime.now().isoformat(), agency_id)
            )

    # Web profil adresini ekle
    if profile_url:
        cursor.execute("""
            INSERT OR IGNORE INTO agency_websites (agency_id, url, type)
            VALUES (?, ?, 'profile')
        """, (agency_id, profile_url.strip()))

    conn.commit()
    conn.close()
    return agency_id


def update_agency_rich_info(
    agency_id: int,
    long_name: str = "",
    establishment_date: str = "",
    enterprise_size: str = "",
    employees_json: str = "",
    income_json: str = "",
    db_path: str = DB_PATH
):
    """Acentenin yeni çekilen zengin kurumsal/finansal bilgilerini günceller."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT long_name, establishment_date, enterprise_size, employees_json, income_json FROM agencies WHERE id = ?", (agency_id,))
    curr = cursor.fetchone()
    if curr:
        new_long_name = long_name if long_name and not curr['long_name'] else (curr['long_name'] or long_name)
        new_est_date = establishment_date if establishment_date and not curr['establishment_date'] else (curr['establishment_date'] or establishment_date)
        new_size = enterprise_size if enterprise_size and not curr['enterprise_size'] else (curr['enterprise_size'] or enterprise_size)
        new_emp = employees_json if employees_json and not curr['employees_json'] else (curr['employees_json'] or employees_json)
        new_inc = income_json if income_json and not curr['income_json'] else (curr['income_json'] or income_json)

        cursor.execute("""
            UPDATE agencies 
            SET long_name = ?, establishment_date = ?, enterprise_size = ?, employees_json = ?, income_json = ?, updated_at = ?
            WHERE id = ?
        """, (new_long_name, new_est_date, new_size, new_emp, new_inc, datetime.now().isoformat(), agency_id))
        conn.commit()
    conn.close()


def add_agency_phone(agency_id: int, phone: str, db_path: str = DB_PATH):
    """Acenteye telefon numarası ekler."""
    phone = phone.strip()
    if not phone or phone.upper() in ["N/A", "NONE", "-"]:
        return
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO agency_phones (agency_id, phone)
        VALUES (?, ?)
    """, (agency_id, phone))
    conn.commit()
    conn.close()


def add_agency_email(agency_id: int, email: str, db_path: str = DB_PATH):
    """Acenteye e-posta adresi ekler."""
    email = email.strip().lower()
    if not email or email.upper() in ["N/A", "NONE", "-"]:
        return
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO agency_emails (agency_id, email)
        VALUES (?, ?)
    """, (agency_id, email))
    conn.commit()
    conn.close()


def add_agency_website(agency_id: int, url: str, site_type: str = "website", db_path: str = DB_PATH):
    """Acenteye web adresi ekler."""
    url = url.strip()
    if not url or url.upper() in ["N/A", "NONE", "-"]:
        return
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO agency_websites (agency_id, url, type)
        VALUES (?, ?, ?)
    """, (agency_id, url, site_type))
    conn.commit()
    conn.close()


def add_communication(
    agency_id: int,
    sender: str,
    recipient: str,
    message: str,
    date: str = None,
    channel: str = "NEKRETNINE_FORM",
    status: str = "SENT",
    db_path: str = DB_PATH
) -> int:
    """
    İletişim tarihçesine yeni bir kayıt ekler ve acente statüsünü günceller.
    """
    if not date:
        date = datetime.now().isoformat()

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO communications (agency_id, date, sender, recipient, message, channel, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (agency_id, date, sender, recipient, message, channel, status))
    comm_id = cursor.lastrowid

    # Acente statüsünü güncelle
    cursor.execute("""
        UPDATE agencies SET status = ?, updated_at = ? WHERE id = ?
    """, (status, datetime.now().isoformat(), agency_id))

    conn.commit()
    conn.close()
    return comm_id


def get_agency_details(agency_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Acentenin tüm detaylarını, telefonlarını, e-postalarını, web sitelerini ve iletişim geçmişini döner."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM agencies WHERE id = ?", (agency_id,))
    agency_row = cursor.fetchone()
    if not agency_row:
        conn.close()
        return None

    agency = dict(agency_row)

    cursor.execute("SELECT phone FROM agency_phones WHERE agency_id = ?", (agency_id,))
    agency['phones'] = [row['phone'] for row in cursor.fetchall()]

    cursor.execute("SELECT email, status FROM agency_emails WHERE agency_id = ?", (agency_id,))
    agency['emails'] = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT url, type FROM agency_websites WHERE agency_id = ?", (agency_id,))
    agency['websites'] = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM communications WHERE agency_id = ? ORDER BY date DESC", (agency_id,))
    agency['communications'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return agency


def get_meta(key: str, default: Optional[str] = None, db_path: str = DB_PATH) -> Optional[str]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_meta WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def set_meta(key: str, value: str, db_path: str = DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO system_meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (key, value, now_str))
    conn.commit()
    conn.close()


def sync_emails_from_gmail(db_path: str = DB_PATH) -> Tuple[int, str]:
    """Gmail IMAP üzerinden e-postaları senkronize eder ve veritabanını günceller."""
    import imaplib
    import email
    import ssl
    from email.header import decode_header
    from email.utils import parsedate_to_datetime, parseaddr

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    mail = imaplib.IMAP4_SSL("imap.gmail.com", port=993, ssl_context=ctx)
    pwd = "ijxz xjsk elcx xtmt".replace(" ", "")
    mail.login("atilbilge@gmail.com", pwd)

    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ae.email, ae.agency_id, a.name 
        FROM agency_emails ae 
        JOIN agencies a ON ae.agency_id = a.id
    """)
    email_map = {}
    for r in cursor.fetchall():
        e = r["email"].strip().lower()
        if e:
            email_map[e] = (r["agency_id"], r["name"])

    def decode_mime(header_val):
        if not header_val:
            return ""
        parts = decode_header(header_val)
        decoded = ""
        for content, enc in parts:
            if isinstance(content, bytes):
                decoded += content.decode(enc or "utf-8", errors="ignore")
            else:
                decoded += content
        return decoded

    def get_body(msg):
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdisp = str(part.get("Content-Disposition"))
                if ctype == "text/plain" and "attachment" not in cdisp:
                    return part.get_payload(decode=True).decode("utf-8", errors="ignore")
                elif ctype == "text/html" and "attachment" not in cdisp:
                    return part.get_payload(decode=True).decode("utf-8", errors="ignore")
        else:
            return msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        return ""

    status, mailboxes = mail.list()
    folders = ["INBOX"]
    for mb in mailboxes:
        mb_str = mb.decode()
        if '\\Sent' in mb_str or 'Sent Mail' in mb_str or 'G&APY-nderilmi' in mb_str:
            parts = mb_str.split(' "/" ')
            if len(parts) > 1:
                folders.append(parts[1].strip())
        elif '\\All' in mb_str or 'All Mail' in mb_str or 'T&APw-m Postalar' in mb_str:
            parts = mb_str.split(' "/" ')
            if len(parts) > 1:
                folders.append(parts[1].strip())

    seen_f = set()
    unique_folders = []
    for f in folders:
        cf = f.strip('"')
        if cf not in seen_f:
            seen_f.add(cf)
            unique_folders.append(f)

    new_count = 0
    processed_dedup = set()

    for folder in unique_folders:
        try:
            folder_arg = folder if folder.startswith('"') else f'"{folder}"'
            res, _ = mail.select(folder_arg)
            if res != "OK":
                res, _ = mail.select(folder.strip('"'))
                if res != "OK":
                    continue

            status, data = mail.search(None, "ALL")
            if status != "OK" or not data or not data[0]:
                continue

            nums = data[0].split()
            recent_nums = nums[-150:] if len(nums) > 150 else nums
            if not recent_nums:
                continue

            nums_str = b",".join(recent_nums).decode("utf-8")
            status, fetch_data = mail.fetch(nums_str, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
            if status != "OK" or not fetch_data:
                continue

            msg_headers_map = {}
            for item in fetch_data:
                if isinstance(item, tuple) and len(item) == 2:
                    header_info = item[0].decode("utf-8", errors="ignore")
                    msg_num = header_info.split()[0]
                    hdr_text = item[1].decode("utf-8", errors="ignore")
                    msg_headers_map[msg_num] = hdr_text

            for num_bytes in recent_nums:
                num_str = num_bytes.decode("utf-8")
                if num_str not in msg_headers_map:
                    continue

                hdr_text = msg_headers_map[num_str]
                hdr_msg = email.message_from_string(hdr_text)

                frm = decode_mime(hdr_msg.get("From"))
                to = decode_mime(hdr_msg.get("To"))
                subj = decode_mime(hdr_msg.get("Subject"))
                dt_hdr = hdr_msg.get("Date")

                _, from_addr = parseaddr(frm)
                _, to_addr = parseaddr(to)

                from_addr = from_addr.strip().lower()
                to_addr = to_addr.strip().lower()

                matching_agency = None
                direction = None

                if from_addr in email_map:
                    matching_agency = email_map[from_addr]
                    direction = "RECEIVED"
                elif to_addr in email_map:
                    matching_agency = email_map[to_addr]
                    direction = "SENT"

                if matching_agency:
                    agency_id, agency_name = matching_agency
                    
                    try:
                        dt = parsedate_to_datetime(dt_hdr)
                        iso_date = dt.isoformat()
                    except Exception:
                        iso_date = dt_hdr or ""

                    dedup_key = f"{agency_id}_{direction}_{iso_date[:16]}"
                    if dedup_key in processed_dedup:
                        continue
                    processed_dedup.add(dedup_key)

                    date_prefix = iso_date[:10] if iso_date else ""
                    cursor.execute("""
                        SELECT id FROM communications 
                        WHERE agency_id = ? AND (date = ? OR date LIKE ?) AND (sender = ? OR recipient = ?)
                    """, (agency_id, iso_date, f"{date_prefix}%", frm, to))

                    if not cursor.fetchone():
                        status_full, full_data = mail.fetch(num_bytes, "(RFC822)")
                        if full_data and full_data[0] and isinstance(full_data[0], tuple):
                            full_msg = email.message_from_bytes(full_data[0][1])
                            body = get_body(full_msg).strip()
                            status_str = "RECEIVED" if direction == "RECEIVED" else "SENT"

                            cursor.execute("""
                                INSERT INTO communications (agency_id, sender, recipient, message, channel, status, date)
                                VALUES (?, ?, ?, ?, 'EMAIL', ?, ?)
                            """, (agency_id, frm, to, body, status_str, iso_date))

                            if direction == "RECEIVED":
                                cursor.execute("UPDATE agencies SET status = 'RESPONDED' WHERE id = ?", (agency_id,))

                            new_count += 1

        except Exception as e:
            print(f"Error syncing folder {folder}: {e}")

    now_iso = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO system_meta (key, value, updated_at)
        VALUES ('last_email_sync', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (now_iso, now_iso))

    conn.commit()
    conn.close()
    mail.logout()
    return new_count, now_iso


def create_campaign(
    name: str,
    subject: str,
    body_html: str,
    sender_name: str = "Stanomer Ekibi",
    sender_email: str = "atilbilge@gmail.com",
    target_filter_json: str = "{}",
    lang: str = "SR_LAT",
    db_path: str = DB_PATH
) -> int:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    valid_langs = ["TR", "EN", "RU", "SR_LAT", "SR_CYR"]
    clean_lang = lang.strip().upper() if lang and lang.strip().upper() in valid_langs else "SR_LAT"
    cursor.execute("""
        INSERT INTO campaigns (name, subject, body_html, sender_name, sender_email, target_filter_json, lang, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?)
    """, (name.strip(), subject.strip(), body_html.strip(), sender_name.strip(), sender_email.strip(), target_filter_json, clean_lang, now_str, now_str))
    camp_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return camp_id


def get_campaigns(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
    rows = cursor.fetchall()
    result = []
    for r in rows:
        c = dict(r)
        cursor.execute("SELECT COUNT(DISTINCT agency_id) as sent_count FROM communications WHERE campaign_id = ?", (c['id'],))
        c['sent_count'] = cursor.fetchone()['sent_count']
        result.append(c)
    conn.close()
    return result


def get_campaign(campaign_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    camp = dict(row)
    cursor.execute("SELECT COUNT(DISTINCT agency_id) as sent_count FROM communications WHERE campaign_id = ?", (campaign_id,))
    camp['sent_count'] = cursor.fetchone()['sent_count']
    conn.close()
    return camp


def update_campaign(
    campaign_id: int,
    name: str = None,
    subject: str = None,
    body_html: str = None,
    sender_name: str = None,
    sender_email: str = None,
    target_filter_json: str = None,
    lang: str = None,
    status: str = None,
    db_path: str = DB_PATH
) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name.strip())
    if subject is not None:
        fields.append("subject = ?")
        values.append(subject.strip())
    if body_html is not None:
        fields.append("body_html = ?")
        values.append(body_html.strip())
    if sender_name is not None:
        fields.append("sender_name = ?")
        values.append(sender_name.strip())
    if sender_email is not None:
        fields.append("sender_email = ?")
        values.append(sender_email.strip())
    if target_filter_json is not None:
        fields.append("target_filter_json = ?")
        values.append(target_filter_json if isinstance(target_filter_json, str) else json.dumps(target_filter_json))
    if lang is not None:
        valid_langs = ["TR", "EN", "RU", "SR_LAT", "SR_CYR"]
        clean_lang = lang.strip().upper() if lang and lang.strip().upper() in valid_langs else "SR_LAT"
        fields.append("lang = ?")
        values.append(clean_lang)
    if status is not None:
        fields.append("status = ?")
        values.append(status.strip())

    if not fields:
        conn.close()
        return False

    fields.append("updated_at = ?")
    values.append(datetime.now().isoformat())

    values.append(campaign_id)
    sql = f"UPDATE campaigns SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()
    return True


def delete_campaign(campaign_id: int, db_path: str = DB_PATH) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    return True


def get_campaign_target_agencies(target_filter: Any, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Filtrelere uyan ve e-posta adresi olan hedef acenteleri döner.
    """
    if isinstance(target_filter, str):
        try:
            target_filter = json.loads(target_filter)
        except Exception:
            target_filter = {}

    if not isinstance(target_filter, dict):
        target_filter = {}

    city = target_filter.get("city", "").strip()
    status = target_filter.get("status", "").strip()
    segment = target_filter.get("segment", "").strip()
    source = target_filter.get("source", "").strip()
    activity_code = target_filter.get("activity_code", "").strip()
    q = target_filter.get("q", "").strip()
    
    exclude_today = target_filter.get("exclude_today", True)
    if isinstance(exclude_today, str):
        exclude_today = exclude_today.lower() in ("true", "1", "yes")

    conn = get_connection(db_path)
    cursor = conn.cursor()

    sql = """
        SELECT DISTINCT a.id, a.name, a.segment, a.city, a.address, a.pib, a.mb, a.status, a.ref_code
        FROM agencies a
        JOIN agency_emails e ON a.id = e.agency_id
        LEFT JOIN agency_websites w ON a.id = w.agency_id
        WHERE e.email IS NOT NULL AND e.email != '' AND e.email NOT IN ('n/a', 'N/A', 'none', '-')
        AND LOWER(e.email) NOT IN (SELECT LOWER(email) FROM unsubscribes)
    """
    params = []

    if exclude_today:
        sql += """ AND a.id NOT IN (
            SELECT DISTINCT agency_id FROM communications 
            WHERE (date LIKE '2026-08-14%' OR date LIKE '%2026-08-14%' OR date(date) = date('now')) AND agency_id IS NOT NULL
        )"""

    if city:
        sql += " AND a.city LIKE ?"
        params.append(f"%{city}%")

    if status:
        sql += " AND a.status = ?"
        params.append(status)

    if segment:
        sql += " AND a.segment = ?"
        params.append(segment)

    if source:
        sql += " AND w.url LIKE ?"
        params.append(f"%{source}%")

    if activity_code:
        sql += " AND a.activity_code LIKE ?"
        params.append(f"%{activity_code}%")

    if q:
        sql += " AND (a.name LIKE ? OR a.city LIKE ? OR a.pib LIKE ? OR a.mb LIKE ? OR e.email LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])

    sql += " ORDER BY a.name ASC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    agencies = []

    for r in rows:
        ag_dict = dict(r)
        cursor.execute("""
            SELECT email FROM agency_emails 
            WHERE agency_id = ? 
            AND LOWER(email) NOT IN (SELECT LOWER(email) FROM unsubscribes)
        """, (ag_dict['id'],))
        ag_dict['emails'] = [row['email'] for row in cursor.fetchall() if row['email'] and row['email'].lower() not in ['n/a', 'none', '-']]
        
        if not ag_dict['emails']:
            continue
            
        agencies.append(ag_dict)

    conn.close()
    return agencies


def get_db_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Veritabanı özet istatistiklerini döner."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM agencies;")
    total_agencies = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM agency_phones;")
    total_phones = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM agency_emails;")
    total_emails = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM agency_websites;")
    total_websites = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM communications;")
    total_comms = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM unsubscribes;")
    total_unsubscribes = cursor.fetchone()['total']

    cursor.execute("SELECT status, COUNT(*) as count FROM agencies GROUP BY status;")
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT city, COUNT(*) as count FROM agencies GROUP BY city ORDER BY count DESC LIMIT 10;")
    city_counts = {row['city']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT value FROM system_meta WHERE key = 'last_email_sync';")
    sync_row = cursor.fetchone()
    last_email_sync = sync_row['value'] if sync_row else None

    conn.close()
    return {
        "total_agencies": total_agencies,
        "total_phones": total_phones,
        "total_emails": total_emails,
        "total_websites": total_websites,
        "total_communications": total_comms,
        "total_unsubscribes": total_unsubscribes,
        "status_distribution": status_counts,
        "top_cities": city_counts,
        "last_email_sync": last_email_sync
    }


def add_unsubscribe(email: str, agency_id: Optional[int] = None, reason: Optional[str] = None, db_path: str = DB_PATH) -> bool:
    """E-posta adresini abonelikten çıkanlar listesine ekler."""
    if not email:
        return False
    clean_email = email.strip().lower()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO unsubscribes (email, agency_id, reason, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET created_at = CURRENT_TIMESTAMP
        """, (clean_email, agency_id, reason, datetime.now().isoformat()))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding unsubscribe {clean_email}: {e}")
        return False
    finally:
        conn.close()


def is_unsubscribed(email: str, db_path: str = DB_PATH) -> bool:
    """E-posta adresinin abonelikten çıkıp çıkmadığını kontrol eder."""
    if not email:
        return False
    clean_email = email.strip().lower()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM unsubscribes WHERE LOWER(email) = ?", (clean_email,))
    row = cursor.fetchone()
    conn.close()
    return bool(row)


def get_unsubscribed_emails(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Abonelikten çıkan e-posta adreslerinin listesini döner."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.email, u.agency_id, u.reason, u.created_at, a.name as agency_name 
        FROM unsubscribes u
        LEFT JOIN agencies a ON u.agency_id = a.id
        ORDER BY u.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_unsubscribe(email: str, db_path: str = DB_PATH) -> bool:
    """E-posta adresini abonelikten çıkanlar listesinden siler."""
    if not email:
        return False
    clean_email = email.strip().lower()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM unsubscribes WHERE LOWER(email) = ?", (clean_email,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error removing unsubscribe {clean_email}: {e}")
        return False
    finally:
        conn.close()


def upsert_unsubscribes_bulk(records: List[Dict[str, Any]], source: str = "Supabase Sync", db_path: str = DB_PATH) -> Dict[str, int]:
    """
    Supabase'den gelen unsubscribe kayıtlarını local DB'ye upsert eder.
    records: [{"email": "...", "unsubscribed_at": "..."}, ...]
    Mevcut kayıtların created_at'ını değiştirmez; sadece yeni kayıt ekler.
    """
    inserted = 0
    skipped = 0
    errors = 0
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        for record in records:
            email = (record.get("email") or "").strip().lower()
            if not email:
                skipped += 1
                continue
            created_at = record.get("unsubscribed_at") or datetime.now().isoformat()
            try:
                cursor.execute("""
                    INSERT INTO unsubscribes (email, agency_id, reason, created_at)
                    VALUES (?, NULL, ?, ?)
                    ON CONFLICT(email) DO NOTHING
                """, (email, source, created_at))
                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"Error upserting unsubscribe {email}: {e}")
                errors += 1
        conn.commit()
    finally:
        conn.close()
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    init_db()
    print("acenteler.db başarıyla oluşturuldu/başlatıldı.")
