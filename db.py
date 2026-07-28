#!/usr/bin/env python3
"""
acenteler.db Veritabanı Modülü
------------------------------
Acenteler, iletişim bilgileri, iletişim tarihçesi ve referans sistemi için SQLite veritabanı işlemlerini yürütür.
"""

import sqlite3
import os
import re
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

    # İndeksler
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_name ON agencies(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_city ON agencies(city);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_status ON agencies(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_ref_code ON agencies(ref_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_url ON agency_websites(url);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_communications_agency_id ON communications(agency_id);")

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
    """Gmail IMAP üzerinden son e-postaları senkronize eder ve veritabanını günceller."""
    import imaplib
    import email
    from email.header import decode_header
    from email.utils import parsedate_to_datetime

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
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
        email_map[r["email"].lower()] = (r["agency_id"], r["name"])

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

    new_count = 0

    # 1. INBOX
    mail.select("INBOX")
    status, data = mail.search(None, "ALL")
    nums = data[0].split()[-30:] if (data and data[0]) else []
    for num in nums:
        status, msg_data = mail.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        frm = decode_mime(msg.get("From"))
        to = decode_mime(msg.get("To"))
        subj = decode_mime(msg.get("Subject"))
        dt_hdr = msg.get("Date")
        if not dt_hdr:
            continue
        dt = parsedate_to_datetime(dt_hdr)
        iso_date = dt.isoformat()

        from_addr = ""
        if "<" in frm and ">" in frm:
            from_addr = frm.split("<")[1].split(">")[0].strip().lower()
        else:
            from_addr = frm.strip().lower()

        if from_addr in email_map:
            agency_id, agency_name = email_map[from_addr]
            body = get_body(msg).strip()

            cursor.execute("SELECT id FROM communications WHERE agency_id = ? AND date = ?", (agency_id, iso_date))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO communications (agency_id, sender, recipient, message, channel, status, date)
                    VALUES (?, ?, ?, ?, 'EMAIL', 'RESPONDED', ?)
                """, (agency_id, frm, to, body, iso_date))
                cursor.execute("UPDATE agencies SET status = 'RESPONDED' WHERE id = ?", (agency_id,))
                new_count += 1

    # 2. SENT MAIL
    mail.select('"[Gmail]/G&APY-nderilmi&AV8- Postalar"')
    status, data = mail.search(None, "ALL")
    nums = data[0].split()[-30:] if (data and data[0]) else []
    for num in nums:
        status, msg_data = mail.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        frm = decode_mime(msg.get("From"))
        to = decode_mime(msg.get("To"))
        subj = decode_mime(msg.get("Subject"))
        dt_hdr = msg.get("Date")
        if not dt_hdr:
            continue
        dt = parsedate_to_datetime(dt_hdr)
        iso_date = dt.isoformat()

        to_addr = ""
        if "<" in to and ">" in to:
            to_addr = to.split("<")[1].split(">")[0].strip().lower()
        else:
            to_addr = to.strip().lower()

        if to_addr in email_map and subj.lower().startswith("re:"):
            agency_id, agency_name = email_map[to_addr]
            body = get_body(msg).strip()

            cursor.execute("SELECT id FROM communications WHERE agency_id = ? AND date = ?", (agency_id, iso_date))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO communications (agency_id, sender, recipient, message, channel, status, date)
                    VALUES (?, ?, ?, ?, 'EMAIL', 'SENT', ?)
                """, (agency_id, frm, to, body, iso_date))
                new_count += 1

    now_iso = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO system_meta (key, value, updated_at)
        VALUES ('last_email_sync', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (now_iso, now_iso))

    conn.commit()
    conn.close()
    return new_count, now_iso


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
        "status_distribution": status_counts,
        "top_cities": city_counts,
        "last_email_sync": last_email_sync
    }


if __name__ == "__main__":
    init_db()
    print("acenteler.db başarıyla oluşturuldu/başlatıldı.")
