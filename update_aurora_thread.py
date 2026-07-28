#!/usr/bin/env python3
"""
update_aurora_thread.py
-----------------------
AURORA 369 (ID: 360) acentesinin veritabanındaki detaylarını ve tüm iletişim geçmişini
gerçek mesaj metinleri, saatleri ve web siteleri ile güncelleyen betik.
"""

import sqlite3
import db

AGENCY_ID = 360

MESSAGES = [
    {
        "date": "2026-07-24T18:14:26",
        "sender": "Atil Bilge ORUM (atilbilge@gmail.com)",
        "recipient": "office@aurora369nekretnine.rs",
        "channel": "NEKRETNINE_FORM",
        "status": "SENT",
        "message": """Poštovani tim AURORA 369,

Nakon što se ugovor o zakupu potpiše, praćenje mesečne kirije i arhiviranje računa između stanodavca i zakupca često ostaje neformalizovano, što ponekad dovodi do nesporazuma ili kašnjenja.

Naš digitalni asistent, Stanomer, rešava upravo taj problem: automatizuje naplatu kirije i arhiviranje računa između stanodavaca i zakupaca, uz potpuno besplatan pristup za vlasnike nekretnina iz vašeg portfolija i njihove zakupce.

Preporukom Stanomera vašim klijentima nakon završenog procesa iznajmljivanja, obezbeđujete im:

Praćenje bez napora: upravljanje kirijom i računima kroz asistenta sa minimalističkim, modernim i preglednim interfejsom.

Maksimalnu privatnost: zahvaljujući "privacy-first" arhitekturi (lokalno skladištenje), finansijski podaci ostaju isključivo na uređajima korisnika, bez skladištenja na spoljnim serverima.

Pozivamo vas da pogledate kratku prezentaciju (1-min video / slajdovi) na sledećem linku:
https://stanomer.com/stanomer-preporuke.pdf

Rado ćemo odgovoriti na sva vaša pitanja i pružiti više informacija.

Srdačan pozdrav,
Atil Bilge ORUM
Stanomer tim"""
    },
    {
        "date": "2026-07-25T21:09:00",
        "sender": "Ana Hadžić - CEO Aurora 369 nekretnine (office@aurora369nekretnine.rs)",
        "recipient": "atilbilge@gmail.com",
        "channel": "EMAIL",
        "status": "RECEIVED",
        "message": """Postovani, zanimljivo mi deluje Vasa platforma
Da li ima opciju da jedan stanodqvac prati vise nekretnina? 
Ukratko molim pojasnjenje pa ako mi se ukaze potreba, preporucicu naravno
Hvala


Srdačan pozdrav,


Ana Hadžić,
CEO
Aurora 369 nekretnine
Ive Lole Ribara 65, 22406 Irig
https://www.aurora369nekretnine.rs/
https://www.rumanekretnine.rs/
+381 61 300 99 59"""
    },
    {
        "date": "2026-07-26T00:45:00",
        "sender": "atilbilge@gmail.com",
        "recipient": "Ana Hadžić (office@aurora369nekretnine.rs)",
        "channel": "EMAIL",
        "status": "SENT",
        "message": """Poštovana Ana,
Hvala Vam na interesovanju za našu platformu.
Odgovor na Vaše pitanje je da – Stanomer apsolutno podržava praćenje više nekretnina preko jednog naloga. Evo kako to funkcioniše u praksi:

Upravljanje više nekretnina (Use Case: Stanodavac sa više stanova):
Jedinstven nalog: Stanodavac preko samo jednog naloga dodaje i upravlja sa više nekretnina, pri čemu svaka ima svoju potpuno odvojenu evidenciju i istoriju.

Kako funkcioniše proces između stanodavca i stanara:
Povezivanje preko QR koda: Stanodavac registruje nekretninu u sistemu i deli QR kod sa stanarom. Kada stanar skenira kod, prihvata poziv i pridružuje se platformi.
Obostrana saglasnost za promene: Bilo kakve eventualne izmene na samoj nekretnini ili u ugovoru stupaju na snagu isključivo kada ih obe strane odobre.
Transparentno praćenje plaćanja: Uplate se takođe prate i evidentiraju uz obostranu potvrdu, čime se obezbeđuje maksimalna transparentnost.
Troškovi održavanja: Pored kirije i arhiviranja računa za komunalije, sistem omogućava i jednostavno praćenje svih troškova održavanja stana.

Na ovaj način, proces je potpuno zaštićen za obe strane, dok su podaci za svaku nekretninu savršeno organizovani na jednom mestu.

Takođe, slobodno možete posetiti našu veb stranicu stanomer.online kako biste se detaljnije upoznali sa platformom. Bilo bi mi zadovoljstvo da Vam ukratko demonstriram platformu uživo ili pošaljem dodatne materijale, ukoliko smatrate da bi to bilo korisno Vašim klijentima.

Srdačan pozdrav,

Atıl Bilge Örüm"""
    },
    {
        "date": "2026-07-27T15:54:00",
        "sender": "atilbilge@gmail.com",
        "recipient": "office@aurora369nekretnine.rs",
        "channel": "EMAIL",
        "status": "SENT",
        "message": """Poštovani,

U nastavku naše jučerašnje prepiske, želeo bih da Vam prosledim još jedan koristan materijal u vezi sa platformom Stanomer.

Na našem sajtu smo ažurirali sekciju sa ilustracijama koje sada još preciznije i jasnije objašnjavaju ceo proces i način funkcionisanja našeg digitalnog asistenta.

Detaljan pregled možete pogledati direktno na ovom linku: https://stanomer.com/#kako-stanomer-radi

Nadam se da će Vam ovo dodatno približiti kako sistem funkcioniše u praksi. Za sva dodatna pitanja, stojim Vam na raspolaganju.

Srdačan pozdrav,

Atıl Bilge Osnivač, Stanomer"""
    },
    {
        "date": "2026-07-27T20:02:00",
        "sender": "Ana Hadžić - CEO Aurora 369 nekretnine (office@aurora369nekretnine.rs)",
        "recipient": "atilbilge@gmail.com",
        "channel": "EMAIL",
        "status": "RECEIVED",
        "message": """Hvala puno



Srdačan pozdrav,


Ana Hadžić,
CEO
Aurora 369 nekretnine
Ive Lole Ribara 65, 22406 Irig
https://www.aurora369nekretnine.rs/
https://www.rumanekretnine.rs/
+381 61 300 99 59"""
    }
]


def update_aurora():
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

    # Web sitelerini ekle
    cursor.execute("""
        INSERT OR IGNORE INTO agency_websites (agency_id, url, type)
        VALUES (?, 'https://www.aurora369nekretnine.rs/', 'website')
    """, (AGENCY_ID,))
    cursor.execute("""
        INSERT OR IGNORE INTO agency_websites (agency_id, url, type)
        VALUES (?, 'https://www.rumanekretnine.rs/', 'website')
    """, (AGENCY_ID,))

    # Statüyü RESPONDED yap
    cursor.execute("UPDATE agencies SET status = 'RESPONDED' WHERE id = ?", (AGENCY_ID,))

    conn.commit()
    conn.close()
    print(f"✅ AURORA 369 için {len(MESSAGES)} adet detaylı e-posta iletişim kaydı başarıyla güncellendi!")

if __name__ == "__main__":
    update_aurora()
