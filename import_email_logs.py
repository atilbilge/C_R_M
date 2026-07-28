#!/usr/bin/env python3
"""
import_email_logs.py
--------------------
"Stanomer" etiketiyle gelen e-posta iletişim geçmişini acenteler.db veritabanına aktaran betik.
"""

import sqlite3
import os
from datetime import datetime
import db

RAW_DATA = """
27.07.26	office@aurora369nekretnine.rs	atilbilge@gmail.com	Aurora 369	Teşekkür mesajı.	[link removed]
27.07.26	atilbilge@gmail.com	office@aurora369nekretnine.rs	Aurora 369	Güncel rehber ve link iletimi.	[link removed]
27.07.26	atilbilge@gmail.com	dilnekretnine@gmail.com	DIL Nekretnine	Güncel rehber ve link iletimi.	[link removed]
27.07.26	atilbilge@gmail.com	beoexpert@yahoo.com	Beoexpert	Müşteri için hazır şablon gönderimi.	[link removed]
27.07.26	beoexpert@yahoo.com	atilbilge@gmail.com	Beoexpert	Stanomer hakkında bilgi talebi.	[link removed]
27.07.26	atilbilge@gmail.com	branislav@kvadratvise.rs	Kvadrat Više	Rehber ve infografik gönderimi.	[link removed]
27.07.26	branislav@kvadratvise.rs	atilbilge@gmail.com	Kvadrat Više	Platform için detaylı açıklama talebi.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	Fra Ore Test	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	NIKS Development	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	PARITAS NEKRETNINE	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	MNM INVEST GROUP	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	GEOTAUR	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	CONSULTING PLUS	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	MINT	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	SKALINA	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	SCP	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	BUILD.ING	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	SRDIĆ MARKOVIĆ	Otomatik: İletim onayı.	[link removed]
27.07.26	noreply@nekretnine.rs	atilbilge@gmail.com	DENČIĆ	Otomatik: İletim onayı.	[link removed]
26.07.26	atilbilge@gmail.com	dilnekretnine@gmail.com	DIL Nekretnine	Ücretsiz kullanım ve uzaktan yönetim açıklaması.	[link removed]
26.07.26	dilnekretnine@gmail.com	atilbilge@gmail.com	DIL Nekretnine	Ücretlendirme ve uzaktan yönetim sorusu.	[link removed]
26.07.26	atilbilge@gmail.com	office@aurora369nekretnine.rs	Aurora 369	Çoklu mülk yönetimi ve QR kod açıklaması.	[link removed]
25.07.26	atilbilge@gmail.com	office@solis-nekretnine.rs	Solis	Tanıtım ve işbirliği teklifi.	[link removed]
25.07.26	office@solis-nekretnine.rs	atilbilge@gmail.com	Solis	Otomatik yanıt.	[link removed]
25.07.26	office@aurora369nekretnine.rs	atilbilge@gmail.com	Aurora 369	Çoklu mülk takibi sorusu.	[link removed]
16.06.26	no_reply@email.apple.com	atilbilge@gmail.com	iOS Uygulama	App Store inceleme onay bildirimi.	[link removed]
""".strip()


def parse_date(date_str: str) -> str:
    """27.07.26 formatını 2026-07-27 T... formatına çevirir."""
    try:
        parts = date_str.split('.')
        day, month, year = int(parts[0]), int(parts[1]), int("20" + parts[2])
        dt = datetime(year, month, day, 12, 0, 0)
        return dt.isoformat()
    except Exception:
        return datetime.now().isoformat()


def main():
    db.init_db()
    lines = RAW_DATA.split('\n')
    print(f"Toplam {len(lines)} e-posta iletişim kaydı işlenecek...")

    added_comms = 0
    updated_agencies = 0

    for line in lines:
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 5:
            continue

        date_str = parts[0].strip()
        sender = parts[1].strip()
        recipient = parts[2].strip()
        institution = parts[3].strip()
        summary = parts[4].strip()

        iso_date = parse_date(date_str)

        # Acente eşleştirme veya oluşturma
        agency_id = db.add_or_get_agency(name=institution)

        # E-Posta adreslerini kaydet
        if sender and sender not in ["atilbilge@gmail.com", "noreply@nekretnine.rs", "no_reply@email.apple.com"]:
            db.add_agency_email(agency_id, sender)
        if recipient and recipient not in ["atilbilge@gmail.com", "noreply@nekretnine.rs", "no_reply@email.apple.com"]:
            db.add_agency_email(agency_id, recipient)

        # Kanal & Statü belirleme
        if sender == "noreply@nekretnine.rs":
            channel = "NEKRETNINE_FORM"
            comm_status = "CONFIRMED"
            agency_status = "SENT"
        elif sender == "no_reply@email.apple.com":
            channel = "SYSTEM"
            comm_status = "SYSTEM_NOTIFICATION"
            agency_status = "SYSTEM"
        elif sender == "atilbilge@gmail.com":
            channel = "EMAIL"
            comm_status = "SENT"
            agency_status = "CONTACTED"
        else:
            # Acenteden yanıt gelmiş
            channel = "EMAIL"
            comm_status = "RECEIVED"
            agency_status = "RESPONDED"  # Yanıt veren acente!

        # İletişim geçmişine ekle
        db.add_communication(
            agency_id=agency_id,
            sender=sender,
            recipient=recipient,
            message=summary,
            date=iso_date,
            channel=channel,
            status=comm_status
        )
        added_comms += 1

        # Acente statüsünü güncelle (Eğer acenteden gelen yanıt varsa veya CONTACTED ise)
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE agencies SET status = ? WHERE id = ?", (agency_status, agency_id))
        conn.commit()
        conn.close()

    print(f"\n✅ Başarıyla {added_comms} e-posta iletişim kaydı acenteler.db veritabanına aktarıldı!")


if __name__ == "__main__":
    main()
