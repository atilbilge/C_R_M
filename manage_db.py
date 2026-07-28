#!/usr/bin/env python3
"""
manage_db.py
------------
acenteler.db veritabanını sorgulamak, iletişim geçmişini görüntülemek,
yeni iletişim kaydı eklemek ve istatistikleri incelemek için komut satırı yönetim aracı.
"""

import sys
import os
import argparse
import json
from datetime import datetime

import db

def print_stats():
    stats = db.get_db_stats()
    print("\n================ VERİTABANI İSTATİSTİKLERİ ================")
    print(f"Toplam Acente Sayısı       : {stats['total_agencies']}")
    print(f"Toplam Telefon Sayısı      : {stats['total_phones']}")
    print(f"Toplam E-posta Sayısı      : {stats['total_emails']}")
    print(f"Toplam İnternet/Profil     : {stats['total_websites']}")
    print(f"Toplam İletişim Kaydı      : {stats['total_communications']}")
    print("----------------------------------------------------------")
    print("Statü Dağılımı:")
    for status, count in stats['status_distribution'].items():
        print(f"  - {status:<15}: {count}")
    print("----------------------------------------------------------")
    print("En Çok Acente Bulunan Şehirler:")
    for city, count in stats['top_cities'].items():
        city_display = city if city else "Bilinmiyor"
        print(f"  - {city_display:<20}: {count}")
    print("==========================================================\n")


def search_agencies(query: str):
    conn = db.get_connection()
    cursor = conn.cursor()

    q = f"%{query.strip()}%"
    cursor.execute("""
        SELECT DISTINCT a.id, a.name, a.city, a.address, a.pib, a.mb, a.status, a.ref_code
        FROM agencies a
        LEFT JOIN agency_phones p ON a.id = p.agency_id
        LEFT JOIN agency_emails e ON a.id = e.agency_id
        WHERE LOWER(a.name) LIKE LOWER(?)
           OR LOWER(a.city) LIKE LOWER(?)
           OR LOWER(a.address) LIKE LOWER(?)
           OR a.pib LIKE ?
           OR a.mb LIKE ?
           OR LOWER(p.phone) LIKE LOWER(?)
           OR LOWER(e.email) LIKE LOWER(?)
        LIMIT 50;
    """, (q, q, q, q, q, q, q))

    rows = cursor.fetchall()
    conn.close()

    print(f"\n🔍 '{query}' için bulunan acenteler (Toplam {len(rows)} sonuç):")
    print("-" * 80)
    for r in rows:
        details = db.get_agency_details(r['id'])
        phones = ", ".join(details['phones']) if details['phones'] else "Yok"
        emails = ", ".join(details['emails']) if details['emails'] else "Yok"
        comms_count = len(details['communications'])
        pib_str = f" | PIB: {r['pib']}" if r['pib'] else ""
        mb_str = f" | MB: {r['mb']}" if r['mb'] else ""

        print(f"ID: {r['id']:<4} | {r['name']} ({r['city'] or 'Şehir Belirtilmemiş'})")
        print(f"     Statü: {r['status']} | Ref Kodu: {r['ref_code']}{pib_str}{mb_str} | İletişim: {comms_count}")
        print(f"     Adres: {r['address']}")
        print(f"     Tel: {phones} | E-posta: {emails}")
        print("-" * 80)


def show_history(agency_id: int):
    details = db.get_agency_details(agency_id)
    if not details:
        print(f"❌ ID {agency_id} ile acente bulunamadı.")
        return

    print(f"\n📋 ACENTE BİLGİLERİ VE İLETİŞİM GEÇMİŞİ")
    print("=" * 80)
    print(f"Acente Adı  : {details['name']}")
    print(f"Şehir / Adres: {details['city']} / {details['address']}")
    print(f"PIB / MB    : {details.get('pib') or '-'} / {details.get('mb') or '-'}")
    print(f"Statü       : {details['status']}")
    print(f"Referans Kd : {details['ref_code']}")
    print(f"Telefonlar  : {', '.join(details['phones'])}")
    print(f"E-Postalar  : {', '.join(details['emails'])}")
    print(f"Web/Profiller:")
    for w in details['websites']:
        print(f"  - [{w['type']}] {w['url']}")

    comms = details['communications']
    print(f"\n💬 İLETIŞİM TARİHÇESİ (Toplam {len(comms)} Kayıt):")
    print("-" * 80)
    if not comms:
        print("  Henüz kaydedilmiş bir iletişim bulunmuyor.")
    else:
        for i, c in enumerate(comms, 1):
            print(f"[{i}] Tarih: {c['date']} | Statü: {c['status']} | Kanal: {c['channel']}")
            print(f"    Gönderen (From) : {c['sender']}")
            print(f"    Alıcı (To)      : {c['recipient']}")
            print(f"    Mesaj Metni     :\n{c['message']}")
            print("-" * 80)


def add_comm_cmd(agency_id: int, sender: str, recipient: str, message: str, status: str, channel: str):
    details = db.get_agency_details(agency_id)
    if not details:
        print(f"❌ ID {agency_id} ile acente bulunamadı.")
        return

    comm_id = db.add_communication(
        agency_id=agency_id,
        sender=sender,
        recipient=recipient or details['name'],
        message=message,
        channel=channel,
        status=status
    )
    print(f"✅ İletişim kaydı başarıyla eklendi! (Kayıt ID: {comm_id}, Acente: {details['name']})")


def export_json(output_file: str):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM agencies ORDER BY id;")
    agency_ids = [row['id'] for row in cursor.fetchall()]
    conn.close()

    agencies_data = []
    for aid in agency_ids:
        details = db.get_agency_details(aid)
        agencies_data.append(details)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(agencies_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Toplam {len(agencies_data)} acentenin detaylı verisi '{output_file}' dosyasına aktarıldı.")


def main():
    parser = argparse.ArgumentParser(description="Acenteler DB & İletişim Yönetim Aracı")
    parser.add_argument("--stats", action="store_true", help="Veritabanı istatistiklerini görüntüler")
    parser.add_argument("--search", type=str, help="İsim, şehir, telefon veya e-postaya göre acente arar")
    parser.add_argument("--history", type=int, help="Belirtilen acente ID'sine ait iletişim geçmişini gösterir")
    parser.add_argument("--export-json", type=str, help="Tüm veritabanını iletişim geçmişi ile JSON dosyasına aktarır")
    
    # Yeni iletişim kaydı eklemek için
    parser.add_argument("--add-comm", action="store_true", help="Yeni bir iletişim kaydı ekler")
    parser.add_argument("--agency-id", type=int, help="Acente ID")
    parser.add_argument("--sender", type=str, default="Atil Bilge ORUM", help="Gönderen kişi/eposta")
    parser.add_argument("--recipient", type=str, help="Alıcı acente/kullanıcı")
    parser.add_argument("--message", type=str, help="İletişim mesajı metni")
    parser.add_argument("--status", type=str, default="SENT", help="İletişim statüsü (SENT, DELIVERED, RECEIVED vb.)")
    parser.add_argument("--channel", type=str, default="NEKRETNINE_FORM", help="İletişim kanalı (NEKRETNINE_FORM, EMAIL, PHONE vb.)")

    args = parser.parse_args()

    if args.stats:
        print_stats()
    elif args.search:
        search_agencies(args.search)
    elif args.history:
        show_history(args.history)
    elif args.export_json:
        export_json(args.export_json)
    elif args.add_comm:
        if not args.agency_id or not args.message:
            print("❌ --add-comm için --agency-id ve --message parametreleri zorunludur.")
            sys.exit(1)
        add_comm_cmd(
            agency_id=args.agency_id,
            sender=args.sender,
            recipient=args.recipient,
            message=args.message,
            status=args.status,
            channel=args.channel
        )
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
