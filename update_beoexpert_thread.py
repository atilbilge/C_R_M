#!/usr/bin/env python3
"""
update_beoexpert_thread.py
--------------------------
BEOEXPERT acentesinin (ID: 186) veritabanındaki iletişim geçmişini
tam ve detaylı mesaj metinleri ile güncelleyen betik.
"""

import sqlite3
import db

AGENCY_ID = 186

MESSAGES = [
    {
        "date": "2026-07-27T07:15:51",
        "sender": "Atil Bilge ORUM (atilbilge@gmail.com)",
        "recipient": "beoexpert@yahoo.com",
        "channel": "NEKRETNINE_FORM",
        "status": "SENT",
        "message": """Poštovani tim BEOEXPERT,

Nakon što se ugovor o zakupu potpiše, praćenje mesečne kirije i arhiviranje računa između stanodavca i zakupca često ostaje neformalizovano, što ponekad dovodi do nesporazuma ili kašnjenja.

Naš digitalni asistent, Stanomer, rešava upravo taj problem: automatizuje naplatu kirije i arhiviranje računa između stanodavaca i zakupaca, uz potpuno besplatan pristup za vlasnike nekretnina iz vašeg portfolija i njihove zakupce.

Preporukom Stanomera vašim klijentima nakon završenog procesa iznajmljivanja, obezbeđujete im:

Praćenje bez napora: upravljanje kirijom i računima kroz asistenta sa minimalističkim, modernim i preglednim interfejsom.

Maksimalnu privatnost: zahvaljujući "privacy-first" arhitekturi (lokalno skladištenje), finansijski podaci ostaju isključivo na uređajima korisnika, bez skladištenja na spoljnim serverima.

Dugoročan odnos s klijentima: vaša usluga ne prestaje predajom ključeva, već nastavlja da donosi vrednost i nakon završetka zakupa, što jača poverenje i verovatnoću ponovne saradnje.

Platforma je potpuno besplatna za vaše klijente i dostupna odmah na stanomer.online.

Ako želite da ovu dodatnu vrednost ponudite svom portfoliju, rado ću vam poslati gotov šablon poruke koji možete proslediti klijentima za par sekundi prilikom predaje ključeva, ili, ako vam više odgovara, možemo zakazati kratak poziv od 10-15 minuta da vam pokažem kako platforma funkcioniše u praksi.

Srdačan pozdrav,
Atıl Bilge
Osnivač, Stanomer"""
    },
    {
        "date": "2026-07-27T15:55:00",
        "sender": "Vladimir Pavlović - Beoexpert (beoexpert@yahoo.com)",
        "recipient": "atilbilge@gmail.com",
        "channel": "EMAIL",
        "status": "RECEIVED",
        "message": """Poštovani,

Hvala na ponudi.
Prosledite nam Stanomer.

Srdačan pozdrav

Vladimir Pavlović
060 300 81 31"""
    },
    {
        "date": "2026-07-27T16:47:00",
        "sender": "atilbilge@gmail.com",
        "recipient": "Vladimir Pavlović - Beoexpert (beoexpert@yahoo.com)",
        "channel": "EMAIL",
        "status": "SENT",
        "message": """Poštovani Vladimire,

Hvala Vam na brzom odgovoru i poverenju.

U nastavku Vam šaljem kratak šablon poruke. Ovaj tekst možete jednostavno kopirati i proslediti Vašim klijentima (stanodavcima i zakupcima putem Vibera, WhatsApp-a ili e-maila) nakon potpisivanja ugovora ili prilikom predaje ključeva.

[Šablon za prosleđivanje klijentima]

"Poštovani,

Kako bismo Vam maksimalno olakšali predstojeći period zakupa, preporučujemo Vam korišćenje besplatnog digitalnog asistenta – Stanomer.

Ova platforma Vam omogućava da lako, transparentno i bez stresa pratite plaćanje kirije i računa. Sve funkcioniše putem obostranog odobravanja, a zahvaljujući visokim standardima privatnosti (lokalno skladištenje), vaši podaci ostaju sačuvani isključivo na vašim uređajima.

Stanomer je dostupan na svim uređajima (Web, iOS i Android). Platformi možete pristupiti odmah i potpuno besplatno na adresi: https://stanomer.online"

Srdačan pozdrav,
Atıl Bilge Örüm"""
    }
]


def update_beoexpert():
    conn = db.get_connection()
    cursor = conn.cursor()

    # Old communications sil
    cursor.execute("DELETE FROM communications WHERE agency_id = ?", (AGENCY_ID,))

    # Yeni iletişim kayıtlarını ekle
    for item in MESSAGES:
        cursor.execute("""
            INSERT INTO communications (agency_id, date, sender, recipient, message, channel, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (AGENCY_ID, item["date"], item["sender"], item["recipient"], item["message"], item["channel"], item["status"]))

    # Vladimir Pavlović telefon numarasını ekle
    cursor.execute("""
        INSERT OR IGNORE INTO agency_phones (agency_id, phone)
        VALUES (?, ?)
    """, (AGENCY_ID, "060 300 81 31"))

    # Statüyü RESPONDED yap
    cursor.execute("UPDATE agencies SET status = 'RESPONDED' WHERE id = ?", (AGENCY_ID,))

    conn.commit()
    conn.close()
    print(f"✅ BEOEXPERT için {len(MESSAGES)} adet detaylı e-posta iletişim kaydı başarıyla güncellendi!")

if __name__ == "__main__":
    update_beoexpert()
