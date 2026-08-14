#!/usr/bin/env python3
"""
send_nekretnine_portal_campaign.py
-----------------------------------
E-posta adresi olmayan Nekretnine.rs acentelerine "Agencijski Profil (White-Label)"
mesajını güvenli, mükerrer önleyici (idempotent) ve veritabanı kayıtlı olarak iletir.
"""

import sys
import os
import re
import json
import time
from datetime import datetime
import db

LOCATIVE_CITY_MAP = {
    'Beograd': 'Beogradu',
    'Novi Sad': 'Novom Sadu',
    'Niš': 'Nišu',
    'Loznica': 'Loznici',
    'Subotica': 'Subotici',
    'Inđija': 'Inđiji',
    'Zrenjanin': 'Zrenjaninu',
    'Vrnjačka Banja': 'Vrnjačkoj Banji',
    'Srem': 'Sremu',
    'Srem Okrug': 'Sremu',
    'Sremu': 'Sremu',
    'Zlatibor': 'Zlatiboru',
    'Zlatiborski Okrug': 'Zlatiboru',
    'Zlatiboru': 'Zlatiboru',
    'Stara Pazova': 'Staroj Pazovi',
    'Šabac': 'Šapcu',
    'Pančevo': 'Pančevu',
    'Čajetina': 'Čajetini',
    'Ruma': 'Rumi',
    'Požarevac': 'Požarevcu',
    'Leskovac': 'Leskovcu',
    'Kikinda': 'Kikindi',
    'Kragujevac': 'Kragujevcu',
    'Kraljevo': 'Kraljevu',
    'Kruševac': 'Kruševcu',
    'Aleksinac': 'Aleksincu',
    'Bačka Topola': 'Bačkoj Topoli',
    'Divčibare': 'Divčibarama',
    'Prijepolje': 'Prijepolju',
    'Veliko Gradište': 'Velikom Gradištu',
    'Ćuprija': 'Ćupriji',
    'Sombor': 'Somboru',
    'Jagodina': 'Jagodini',
    'Valjevo': 'Valjevu',
    'Čačak': 'Čačku',
    'Užice': 'Užicu',
    'Smederevo': 'Smederevu',
    'Vranje': 'Vranju',
    'Pirot': 'Pirotu',
    'Sremska Mitrovica': 'Sremskoj Mitrovici',
    'Novi Pazar': 'Novom Pazaru',
    'Vršac': 'Vršcu',
    'Bačka Palanka': 'Bačkoj Palanci',
    'Paraćin': 'Paraćinu',
    'Prokuplje': 'Prokuplju',
    'Zaječar': 'Zaječaru',
    'Bor': 'Boru'
}

MESSAGE_TEMPLATE = """Poštovani tim {agency_name},

Ranije smo predstavili Stanomer kao aplikaciju za stanodavce i zakupce. Slušajući povratne informacije agencija u ovom periodu, razvili smo modul specijalno za vas: Agencijski Profil, gde možete upravljati procesima nakon iznajmljivanja (praćenje kirije, koordinacija popravki, upravljanje dokumentacijom) sa jednog panela i pod vašim brendom (White-Label).

Voleli bismo da vam kratko pokažemo kako ovo može pomoći vašem portfoliju u {grad} — da li bi vam odgovarao 15-minutni razgovor?

https://www.stanomer.online/agencies"""


def get_clean_city(r):
    city = (r.get('city') or '').strip()
    long_name = (r.get('long_name') or '').strip()

    if 'BEOGRAD' in city.upper() or 'BEOGRAD' in long_name.upper():
        return 'Beograd'
    if 'NOVI SAD' in city.upper() or 'NOVI SAD' in long_name.upper():
        return 'Novi Sad'
    if 'KRUŠEVAC' in long_name.upper() or 'KRUŠEVAC' in city.upper():
        return 'Kruševac'
    if city in ('sprat: 7', 'sprat: PR', 'broj stana: 8'):
        if 'Beograd' in long_name: return 'Beograd'
        if 'Kruševac' in long_name: return 'Kruševac'
    
    city = re.sub(r'\s*\(.*?\)', '', city).strip()
    return city if city else 'Beograd'


def get_pending_agencies():
    conn = db.get_connection()
    cur = conn.cursor()

    # Query email-less agencies from nekretnine.rs that have NOT received this message
    cur.execute('''
        SELECT a.id, a.name, a.long_name, a.city, a.address, a.status,
               (SELECT GROUP_CONCAT(url) FROM agency_websites WHERE agency_id = a.id) as urls
        FROM agencies a
        JOIN agency_websites w ON a.id = w.agency_id
        WHERE w.url LIKE '%nekretnine.rs%'
        AND a.id NOT IN (
            SELECT DISTINCT agency_id FROM agency_emails 
            WHERE email IS NOT NULL AND email != '' AND LOWER(email) NOT IN ('n/a', 'none', '-', 'null')
        )
        AND a.id NOT IN (
            SELECT DISTINCT agency_id FROM communications 
            WHERE message LIKE '%stanomer.online/agencies%' AND agency_id IS NOT NULL
        )
        GROUP BY a.id
        ORDER BY a.name ASC
    ''')

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def process_sending(dry_run=True):
    pending = get_pending_agencies()
    print(f"=== NEKRETNINE.RS E-POSTASIZ ACENTE GÖNDERİM SÜRECİ ===")
    print(f"Mod: {'DRY RUN (Simülasyon / Test)' if dry_run else 'GERÇEK GÖNDERİM'}")
    print(f"Gönderilecek Toplam Acente Sayısı: {len(pending)}\n")

    if not pending:
        print("✅ Gönderilecek yeni acente bulunamadı! Tüm acentelere mesaj zaten iletilmiş.")
        return

    conn = db.get_connection()
    cur = conn.cursor()

    processed_count = 0
    skipped_count = 0

    for idx, ag in enumerate(pending, start=1):
        ag_id = ag['id']
        ag_name = ag['name']
        clean_city = get_clean_city(ag)
        grad_loc = LOCATIVE_CITY_MAP.get(clean_city, clean_city + 'u')

        processed_body = MESSAGE_TEMPLATE.format(
            agency_name=ag_name,
            grad=grad_loc
        )

        recipient_info = ag['urls'] or ag['address'] or ag['city'] or 'Nekretnine Portal Form'

        # DOUBLE-CHECK IN DB TO GUARANTEE NO DUPLICATES IF RUN MULTIPLE TIMES IN PARALLEL
        cur.execute("""
            SELECT COUNT(*) FROM communications 
            WHERE agency_id = ? AND message LIKE '%stanomer.online/agencies%'
        """, (ag_id,))
        if cur.fetchone()[0] > 0:
            print(f"[{idx}/{len(pending)}] ⏭️ Zaten İletildi (Mükerrer Engellendi): {ag_name} (ID: {ag_id})")
            skipped_count += 1
            continue

        if dry_run:
            print(f"[{idx}/{len(pending)}] 🔍 [DRY-RUN] Gönderilecek: {ag_name} (Şehir: {clean_city} -> u {grad_loc})")
            print(f"    Recipient: {recipient_info}")
            print(f"    Mesaj:\n{processed_body}\n" + "-"*50)
            processed_count += 1
        else:
            now_iso = datetime.now().isoformat()
            cur.execute("""
                INSERT INTO communications (agency_id, date, sender, recipient, message, channel, status)
                VALUES (?, ?, 'Stanomer Ekibi', ?, ?, 'NEKRETNINE_PORTAL', 'SENT')
            """, (ag_id, now_iso, recipient_info, processed_body))

            cur.execute("""
                UPDATE agencies SET status = 'SENT', updated_at = ? WHERE id = ?
            """, (now_iso, ag_id))

            conn.commit()
            processed_count += 1
            print(f"[{idx}/{len(pending)}] ✅ Gönderildi & Veritabanına İşlendi: {ag_name} (ID: {ag_id})")

    conn.close()

    print(f"\n==========================================")
    print(f"İşlem Tamamlandı!")
    print(f"Başarıyla İşlenen: {processed_count}")
    print(f"Mükerrer Engellenen / Atlanan: {skipped_count}")
    print(f"==========================================\n")


if __name__ == "__main__":
    is_real = "--real" in sys.argv
    process_sending(dry_run=not is_real)
