#!/usr/bin/env python3
"""
update_dil_thread.py
--------------------
DIL NEKRETNINE acentesinin (ID: 133) veritabanındaki iletişim geçmişini
tam ve detaylı mesaj metinleri ile güncelleyen betik.
"""

import sqlite3
import db

AGENCY_ID = 133

MESSAGES = [
    {
        "date": "2026-07-26T10:59:00",
        "sender": "Atil Bilge ORUM (atilbilge@gmail.com)",
        "recipient": "dil.nekretnine@gmail.com",
        "channel": "NEKRETNINE_FORM",
        "status": "SENT",
        "message": """Poštovani tim DIL NEKRETNINE,

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
        "date": "2026-07-26T12:02:00",
        "sender": "dil.nekretnine@gmail.com",
        "recipient": "atilbilge@gmail.com",
        "channel": "EMAIL",
        "status": "RECEIVED",
        "message": """Da li nešto plaćaju mesečno i da li to znači kada du zakupodavci na odmoru ili nisu prisutni , vi vodite računa o tome?"""
    },
    {
        "date": "2026-07-26T12:27:00",
        "sender": "atilbilge@gmail.com",
        "recipient": "dil.nekretnine@gmail.com",
        "channel": "EMAIL",
        "status": "SENT",
        "message": """Poštovani,

Hvala na brzom odgovoru i odličnim pitanjima.

Evo kratkih pojašnjenja:

1. Da li nešto plaćaju mesečno? Ne, korišćenje Stanomera je potpuno besplatno. Nema nikakvih skrivenih ni mesečnih troškova za stanodavce i zakupce.

2. Da li mi vodimo računa o tome kada su na odmoru? Mi nismo agencija za fizičko upravljanje nekretninama i ne preuzimamo operativne obaveze na terenu. Stanomer je softverska aplikacija (digitalni alat) koji oni sami koriste na svojim telefonima.

Međutim, aplikacija je savršena upravo za te situacije kada je stanodavac na odmoru ili u inostranstvu! Umesto da se zovu ili razmenjuju poruke, zakupac jednostavno u aplikaciju unese da je platio kiriju i komunalije (uz sliku uplatnice/računa). Stanodavac, gde god da se nalazi, može u par klikova da otvori aplikaciju i uveri se da je sve izmireno i uredno arhivirano, bez stresa i potrebe za fizičkim prisustvom.

Detaljan pregled o tome kako platforma tačno funkcioniše u praksi možete pronaći na našem sajtu stanomer.online, u odeljku "Kako Stanomer radi?".

Srdačan pozdrav, 

Atıl Bilge Örüm"""
    },
    {
        "date": "2026-07-27T16:57:00",
        "sender": "atilbilge@gmail.com",
        "recipient": "dil.nekretnine@gmail.com",
        "channel": "EMAIL",
        "status": "SENT",
        "message": """Poštovani,

U nastavku naše jučerašnje prepiske, želeo bih da Vam prosledim još jedan koristan materijal u vezi sa platformom Stanomer.

Na našem sajtu smo ažurirali sekciju sa ilustracijama koje sada još preciznije i jasnije objašnjavaju ceo proces i način funkcionisanja našeg digitalnog asistenta.

Detaljan pregled možete pogledati direktno na ovom linku: https://stanomer.com/#kako-stanomer-radi

Nadam se da će Vam ovo dodatno približiti kako sistem funkcioniše u praksi. Za sva dodatna pitanja, stojim Vam na raspolaganju.

Srdačan pozdrav,

Atıl Bilge Osnivač, Stanomer"""
    }
]


def update_dil():
    conn = db.get_connection()
    cursor = conn.cursor()

    # Old communications sil
    cursor.execute("DELETE FROM communications WHERE agency_id = ?", (AGENCY_ID,))
    print(f"DIL NEKRETNINE (ID: {AGENCY_ID}) eski iletişim kayıtları silindi.")

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
    print(f"✅ DIL NEKRETNINE için {len(MESSAGES)} adet detaylı e-posta iletişim kaydı başarıyla güncellendi!")

if __name__ == "__main__":
    update_dil()
