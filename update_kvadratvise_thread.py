#!/usr/bin/env python3
"""
update_kvadratvise_thread.py
----------------------------
Kvadrat Više Nekretnine acentesinin (ID: 300) veritabanındaki iletişim geçmişini
tam ve detaylı mesaj metinleri ile güncelleyen betik.
"""

import sqlite3
import db

AGENCY_ID = 300

MESSAGES = [
    {
        "date": "2026-07-27T08:20:00",
        "sender": "Atil Bilge ORUM (atilbilge@gmail.com)",
        "recipient": "branislav@kvadratvise.rs",
        "channel": "NEKRETNINE_FORM",
        "status": "SENT",
        "message": """Poštovani tim Kvadrat Više Nekretnine,

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
        "date": "2026-07-27T10:09:00",
        "sender": "Branislav Bogdanov (branislav@kvadratvise.rs)",
        "recipient": "atilbilge@gmail.com",
        "channel": "EMAIL",
        "status": "RECEIVED",
        "message": """Poštovani,

Zanimljiva mi je Vaša ponuda i odgovao bi mi neki popodnevni termin šireg pojašnjenja i prezentacije.

Hvala unapred

Branislav Bogdanov
No 6567
063215104"""
    },
    {
        "date": "2026-07-27T10:49:00",
        "sender": "atilbilge@gmail.com",
        "recipient": "Branislav Bogdanov (branislav@kvadratvise.rs)",
        "channel": "EMAIL",
        "status": "SENT",
        "message": """Poštovani,

Hvala Vam na velikom interesovanju za Stanomer i na želji da saznate više.

Trenutno sam van zemlje i nažalost imam veoma slabu internet konekciju, pa bi video poziv u ovom trenutku bio tehnički otežan.

Zato Vam u prilogu ovog mejla šaljem infografiku koja u 6 jednostavnih koraka slikovito objašnjava naš proces – od digitalnog dogovora do praćenja uplata i prijava kvarova. Takođe, detaljan korak-po-korak pregled možete pogledati na našem sajtu stanomer.online, u odeljku "Kako Stanomer radi?".

Nadam se da će Vam ovi materijali pružiti jasnu sliku o tome kako platforma funkcioniše kao digitalni asistent. Ukoliko nakon pregleda budete imali bilo kakvih dodatnih pitanja, slobodno mi pišite – biće mi zadovoljstvo da Vam odgovorim.

Srdačan pozdrav, Atıl Bilge Osnivač, Stanomer"""
    }
]


def update_kvadratvise():
    conn = db.get_connection()
    cursor = conn.cursor()

    # Old communications sil
    cursor.execute("DELETE FROM communications WHERE agency_id = ?", (AGENCY_ID,))
    print(f"Kvadrat Više Nekretnine (ID: {AGENCY_ID}) eski iletişim kayıtları silindi.")

    # Yeni iletişim kayıtlarını ekle
    for item in MESSAGES:
        cursor.execute("""
            INSERT INTO communications (agency_id, date, sender, recipient, message, channel, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (AGENCY_ID, item["date"], item["sender"], item["recipient"], item["message"], item["channel"], item["status"]))

    # Statüyü RESPONDED yap
    cursor.execute("UPDATE agencies SET status = 'RESPONDED' WHERE id = ?", (AGENCY_ID,))

    conn.commit()
    conn.close()
    print(f"✅ Kvadrat Više Nekretnine için {len(MESSAGES)} adet detaylı e-posta iletişim kaydı başarıyla güncellendi!")

if __name__ == "__main__":
    update_kvadratvise()
