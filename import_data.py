#!/usr/bin/env python3
"""
import_data.py
--------------
Root dizinindeki tüm *_acenteler.csv ve sent_messages_log.json dosyalarını okuyarak
acenteler.db SQLite veritabanına aktaran betik.
"""

import os
import glob
import csv
import json
import re
from datetime import datetime

import db

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Mesaj Gönderen İletişim Bilgileri & Şablonu
SENDER_INFO = "Atil Bilge ORUM (atilbilge@gmail.com)"

DEFAULT_MESSAGE_TEMPLATE = """Poštovani tim {agency_name},

Nakon što se ugovor o zakupu potpiše, praćenje mesečne kirije i arhiviranje računa između stanodavca i zakupca često ostaje neformalizovano, što ponekad dovodi do nesporazuma ili kašnjenja.

Naš digitalni asistent, Stanomer, rešava upravo taj problem: automatizuje naplatu kirije i arhiviranje računa između stanodavców i zakupaca, uz potpuno besplatan pristup za vlasnike nekretnina iz vašeg portfolija i njihove zakupce.

Preporukom Stanomera vašim klijentima nakon završenog procesa iznajmljivanja, obezbeđujete im:

Praćenje bez napora: upravljanje kirijom i računima kroz asistenta sa minimalističkim, modernim i preglednim interfejsom.

Maksimalnu privatnost: zahvaljujući "privacy-first" arhitekturi (lokalno skladištenje), finansijski podaci ostaju isključivo na uređajima korisnika, bez skladištenja na spoljnim serverima.

Pozivamo vas da pogledate kratku prezentaciju (1-min video / slajdovi) na sledećem linku:
https://stanomer.com/stanomer-preporuke.pdf

Rado ćemo odgovoriti na sva vaša pitanja i pružiti više informacija.

Srdačan pozdrav,
Atil Bilge ORUM
Stanomer tim"""


def parse_city_from_filename(filename: str) -> str:
    """Dosya adından şehir/bölge adını türetir."""
    base = os.path.basename(filename).replace("_acenteler.csv", "").replace(".csv", "")
    words = base.split("-")
    city = " ".join(word.capitalize() for word in words)
    return city


def extract_city_from_address(address: str) -> str:
    """Adres metninin sonundaki - Şehir kısmını ayıklar."""
    if "-" in address:
        parts = address.rsplit("-", 1)
        city_candidate = parts[1].strip()
        if city_candidate and len(city_candidate) < 40 and not city_candidate.isdigit():
            return city_candidate
    return ""


def clean_phone_numbers(phone_str: str) -> list:
    """Virgülle ayrılmış veya karmaşık telefon numaralarını temizleyip liste döner."""
    if not phone_str or phone_str.upper() in ["N/A", "NONE", "-"]:
        return []
    # Virgül veya kesme işareti ile ayır
    phones = [p.strip() for p in re.split(r'[,;/]', phone_str) if p.strip()]
    return phones


def clean_emails(email_str: str) -> list:
    """Virgülle ayrılmış e-postaları temizler."""
    if not email_str or email_str.upper() in ["N/A", "NONE", "-"]:
        return []
    emails = [e.strip() for e in re.split(r'[,;/]', email_str) if e.strip() and "@" in e]
    return emails


def import_csv_files():
    """Root dizinindeki tüm *_acenteler.csv dosyalarını içe aktarır."""
    csv_files = glob.glob(os.path.join(ROOT_DIR, "*_acenteler.csv"))
    print(f"Toplam {len(csv_files)} CSV dosyası bulundu.")

    imported_count = 0
    phone_count = 0
    email_count = 0

    for csv_file in csv_files:
        filename = os.path.basename(csv_file)
        inferred_city = parse_city_from_filename(filename)

        with open(csv_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Acente Adı", "").strip()
                if not name:
                    continue

                address = row.get("Adres", "").strip()
                phone_raw = row.get("Telefon Numarası", "").strip()
                email_raw = row.get("E-posta Adresi", "").strip()
                profile_url = row.get("Profil Linki", "").strip()

                # Şehir belirleme logic'i
                city = extract_city_from_address(address)
                if not city and inferred_city.lower() != "nekretnine":
                    city = inferred_city

                # Acenteyi ekle veya getir
                agency_id = db.add_or_get_agency(
                    name=name,
                    city=city,
                    address=address,
                    profile_url=profile_url
                )

                # Telefonları ekle
                phones = clean_phone_numbers(phone_raw)
                for p in phones:
                    db.add_agency_phone(agency_id, p)
                    phone_count += 1

                # E-postaları ekle
                emails = clean_emails(email_raw)
                for e in emails:
                    db.add_agency_email(agency_id, e)
                    email_count += 1

                imported_count += 1

    print(f"CSV İçe Aktarım Tamamlandı: {imported_count} acente kaydı işlendi, {phone_count} telefon, {email_count} e-posta kaydı eklendi.")


def import_sent_messages_log():
    """sent_messages_log.json kütüğünü okuyarak iletişim tarihçesine ekler."""
    json_path = os.path.join(ROOT_DIR, "sent_messages_log.json")
    if not os.path.exists(json_path):
        print("sent_messages_log.json bulunamadı, atlanıyor.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        log_data = json.load(f)

    print(f"sent_messages_log.json içerisinde {len(log_data)} gönderim kaydı bulundu.")

    imported_comms = 0
    for profile_url, item in log_data.items():
        agency_name = item.get("agency_name", "").strip()
        sent_at = item.get("sent_at")
        status = item.get("status", "SENT")

        if not agency_name and not profile_url:
            continue

        # Acente id bul veya oluştur
        agency_id = db.add_or_get_agency(
            name=agency_name or "Bilinmeyen Acente",
            profile_url=profile_url,
            status=status
        )

        message_content = DEFAULT_MESSAGE_TEMPLATE.format(agency_name=agency_name or "Acente")

        # İletişim tarihçesine ekle
        db.add_communication(
            agency_id=agency_id,
            sender=SENDER_INFO,
            recipient=agency_name or profile_url,
            message=message_content,
            date=sent_at,
            channel="NEKRETNINE_FORM",
            status=status
        )
        imported_comms += 1

    print(f"İletişim Geçmişi Aktarımı Tamamlandı: {imported_comms} gönderilen mesaj kaydedildi.")


def main():
    print("--- ACENTELER VERİTABANI OLUŞTURMA & VERİ AKTARIMI ---")
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
        print("Eski acenteler.db silindi, temiz veritabanı oluşturuluyor...")
    db.init_db()
    import_csv_files()
    import_sent_messages_log()

    stats = db.get_db_stats()
    print("\n--- VERİTABANI İSTATİSTİKLERİ ---")
    print(f"Toplam Acente Sayısı       : {stats['total_agencies']}")
    print(f"Toplam Telefon Sayısı      : {stats['total_phones']}")
    print(f"Toplam E-posta Sayısı      : {stats['total_emails']}")
    print(f"Toplam Web / Profil Adresi : {stats['total_websites']}")
    print(f"Toplam İletişim Geçmişi    : {stats['total_communications']}")
    print(f"Statü Dağılımı             : {stats['status_distribution']}")
    print("-------------------------------------------------")


if __name__ == "__main__":
    main()
