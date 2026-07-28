#!/usr/bin/env python3
"""
Stanomer - Toplu E-posta Gönderim Scripti
------------------------------------------
status=NEW ve e-postası olan tüm acentelere tanıtım e-postası gönderir.
Gönderilen her e-posta:
  - DB'deki communications tablosuna kaydedilir
  - Acente statüsü NEW → SENT olarak güncellenir
  - Tekrar gönderilmez (daha önce EMAIL kanalından gönderilmişse atlanır)
  - Bir acente için birden fazla adres varsa tek e-postada To alanına hepsi yazılır

Kullanım:
  python3 send_emails.py          → Gerçek gönderim
  python3 send_emails.py --dry    → Kuru test (e-posta gönderilmez, sadece listeyi gösterir)
  python3 send_emails.py --test   → Sadece atilbilge@gmail.com'a 'Agenoir' adıyla test gönder
"""

import smtplib
import time
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import db

# ─── AYARLAR ──────────────────────────────────────────────────────────────────

GMAIL_ADDRESS      = "atilbilge@gmail.com"
GMAIL_APP_PASSWORD = "ijxz xjsk elcx xtmt"
SENDER_NAME        = "Stanomer Ekibi"
SUBJECT            = "Unapređenje procesa nakon iznajmljivanja za vaše klijente (Besplatno rešenje)"

DELAY_BETWEEN_EMAILS = 3

# ─── HTML ŞABLON ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = (
    '<!DOCTYPE html>'
    '<html lang="sr">'
    '<head>'
    '<meta charset="UTF-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    '<title>Stanomer - AGENCY_NAME_PLACEHOLDER</title>'
    '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,600;0,800;1,800&display=swap" rel="stylesheet">'
    '</head>'
    '<body style="margin: 0; padding: 0; background-color: #eef2f6; font-family: \'Plus Jakarta Sans\', -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif; color: #4b5563;">'
    '<table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed;">'
    '<tr><td align="center" style="padding: 40px 10px;">'
    '<table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); overflow: hidden; max-width: 600px; width: 100%;">'
    '<tr><td align="center" style="padding: 40px 40px 0 40px;">'
    '<img src="https://www.stanomer.online/assets/logo.png" alt="Stanomer Logo" width="150" style="display: block; max-width: 150px; height: auto;">'
    '</td></tr>'
    '<tr><td style="padding: 40px;">'
    '<p style="font-size: 16px; line-height: 1.6; margin-top: 0; margin-bottom: 20px; font-weight: 600; color: #111827;">'
    'Po&#353;tovani tim AGENCY_NAME_PLACEHOLDER,'
    '</p>'
    '<p style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 20px;">'
    'Nakon &#353;to se ugovor o zakupu potpi&#353;e, pra&#263;enje mese&#269;ne kirije i arhiviranje ra&#269;una izme&#273;u stanodavca i zakupca &#269;esto ostaje neformalizovano &#8212; &#353;to ponekad dovodi do nesporazuma ili ka&#353;njenja.'
    '</p>'
    '<p style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 20px;">'
    'Na&#353; digitalni asistent, <a href="https://www.stanomer.online" style="color: #3b82f6; text-decoration: none; font-weight: 800;">Stanomer</a>, re&#353;ava upravo taj problem: automatizuje naplatu kirije i arhiviranje ra&#269;una izme&#273;u stanodavaca i zakupaca, uz potpuno besplatan pristup za vlasnike nekretnina iz va&#353;eg portfolija i njihove zakupce.'
    '</p>'
    '<p style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 15px;">'
    'Preporukom Stanomera va&#353;im klijentima nakon zavr&#353;enog procesa iznajmljivanja, obezbe&#273;ujete im:'
    '</p>'
    '<ul style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 25px; padding-left: 20px; color: #4b5563;">'
    '<li style="margin-bottom: 10px;"><strong style="color: #111827;">Pra&#263;enje bez napora</strong> &#8212; upravljanje kirijom i ra&#269;unima kroz asistenta sa minimali&#353;ti&#269;kim, modernim i preglednim interfejsom.</li>'
    '<li style="margin-bottom: 10px;"><strong style="color: #111827;">Maksimalnu privatnost</strong> &#8212; zahvaljuju&#263;i &quot;privacy-first&quot; arhitekturi (lokalno skladi&#353;tenje), finansijski podaci ostaju isklju&#269;ivo na ure&#273;ajima korisnika, bez skladi&#353;tenja na spoljnim serverima.</li>'
    '<li style="margin-bottom: 10px;"><strong style="color: #111827;">Dugoro&#269;an odnos s klijentima</strong> &#8212; va&#353;a usluga ne prestaje predajom klju&#269;eva, ve&#263; nastavlja da donosi vrednost i nakon zavr&#353;etka zakupa, &#353;to ja&#269;a poverenje i verovatno&#263;u ponovne saradnje.</li>'
    '</ul>'
    '<p style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 25px;">'
    'Platforma je potpuno besplatna za va&#353;e klijente i dostupna odmah na <a href="https://stanomer.online" style="color: #3b82f6; text-decoration: none; font-weight: 800;">stanomer.online</a>.'
    '</p>'
    '<p style="font-size: 15px; line-height: 1.6; margin-top: 0; margin-bottom: 30px;">'
    'Ako &#382;elite da ovu dodatnu vrednost ponudite svom portfoliju, rado &#263;u vam poslati gotov &#353;ablon poruke koji mo&#382;ete proslediti klijentima prilikom predaje klju&#269;eva. Za sva pitanja ili dodatne potrebe za digitalnim re&#353;enjima, slobodno me kontaktirajte u bilo kom trenutku.'
    '</p>'
    # Promo card
    '<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f6f8; border-radius: 20px; margin-bottom: 40px;">'
    '<tr><td align="center" style="padding: 40px 30px;">'
    '<table border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;"><tr>'
    '<td style="background-color: #e0e7ff; color: #3b82f6; font-size: 12px; font-weight: 800; letter-spacing: 0.5px; padding: 6px 16px; border-radius: 20px; text-transform: uppercase;">'
    '<span style="font-size: 10px; margin-right: 4px;">&#9679;</span> DIGITALNA KNJIGA KIRIJA'
    '</td></tr></table>'
    '<h2 style="margin: 0 0 15px 0; font-size: 26px; font-weight: 800; color: #111827; line-height: 1.3;">'
    'Recite <span style="color: #3b82f6; font-style: italic;">zbogom</span> bele&#353;kama<br>o kiriji na papiru!'
    '</h2>'
    '<p style="margin: 0 0 25px 0; font-size: 15px; line-height: 1.6; color: #4b5563;">'
    'Prestanite da tra&#382;ite priznanice na Viber-u ili bele&#353;kama. Stanomer preuzima celokupno pra&#263;enje kirije &#8212; veoma je jednostavan za kori&#353;&#263;enje.'
    '</p>'
    '<table border="0" cellpadding="0" cellspacing="0" width="100%"><tr><td align="center">'
    '<a href="https://stanomer.online" style="display: inline-block; background-color: #000000; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; margin: 5px;">App Store</a>'
    '<a href="https://stanomer.online" style="display: inline-block; background-color: #000000; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; margin: 5px;">Google Play</a>'
    '<a href="https://stanomer.online" style="display: inline-block; background-color: #000000; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; margin: 5px;">Otvori Web Aplikaciju</a>'
    '</td></tr></table>'
    '<p style="margin: 20px 0 0 0; font-size: 12px; color: #9ca3af;">Potpuno besplatno za jednu nekretninu. Nije potrebna kreditna kartica.</p>'
    '</td></tr></table>'
    # Signature
    '<table border="0" cellpadding="0" cellspacing="0" width="100%"><tr>'
    '<td style="font-size: 15px; line-height: 1.5; padding-right: 15px; vertical-align: middle;">'
    '<p style="margin: 0; color: #6b7280;">Srda&#269;an pozdrav,</p>'
    '<p style="margin: 5px 0 0 0; font-weight: 800; font-size: 16px; color: #111827;">At&#305;l Bilge</p>'
    '<p style="margin: 2px 0 0 0; color: #6b7280; font-size: 14px;">Osniva&#269;, Stanomer</p>'
    '</td>'
    '<td style="width: 60px; vertical-align: middle; border-left: 2px solid #e5e7eb; padding-left: 15px;">'
    '<img src="https://www.stanomer.online/assets/logo.png" alt="Stanomer Logo" width="60" style="display: block; max-width: 60px; height: auto;">'
    '</td></tr></table>'
    '</td></tr>'
    '</table>'
    '</td></tr>'
    '</table>'
    '</body></html>'
)


# ─── VERİTABANI SORGULAMA ────────────────────────────────────────────────────

def get_target_agencies():
    """
    status=NEW ve en az bir e-postası olan acenteleri getirir.
    Daha önce EMAIL kanalıyla gönderilmişleri atlar.
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT a.id, a.name, a.city
        FROM agencies a
        JOIN agency_emails e ON a.id = e.agency_id
        WHERE a.status = 'NEW'
          AND a.id NOT IN (
              SELECT DISTINCT agency_id FROM communications WHERE channel = 'EMAIL'
          )
        ORDER BY a.id ASC
    """)
    agencies = [dict(row) for row in cursor.fetchall()]

    for ag in agencies:
        cursor.execute("SELECT email FROM agency_emails WHERE agency_id = ?", (ag['id'],))
        ag['emails'] = [row['email'] for row in cursor.fetchall()]

    conn.close()
    return agencies


# ─── E-POSTA GÖNDERME ────────────────────────────────────────────────────────

def send_email(smtp, to_emails: list, agency_name: str) -> bool:
    """
    Bir acentenin tüm e-postalarını tek mesajda To alanına yazar ve gönderir.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = SUBJECT
        msg["From"]    = f"{SENDER_NAME} <{GMAIL_ADDRESS}>"
        msg["To"]      = ", ".join(to_emails)

        html_body = HTML_TEMPLATE.replace("AGENCY_NAME_PLACEHOLDER", agency_name)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        smtp.sendmail(GMAIL_ADDRESS, to_emails, msg.as_string())
        return html_body  # başarılı: içeriği döndür
    except Exception as e:
        print(f"   ❌ HATA: {to_emails} → {e}")
        return None  # başarısız


# ─── ANA AKIŞ ────────────────────────────────────────────────────────────────

def main():
    dry_run  = "--dry"  in sys.argv
    test_run = "--test" in sys.argv

    if test_run:
        print("🧪 TEST MODU — atilbilge@gmail.com'a 'Agenoir' adıyla test e-postası gönderiliyor...")
        try:
            smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD.replace(" ", ""))
            ok = send_email(smtp, ["atilbilge@gmail.com"], "Agenoir")
            smtp.quit()
            if ok:
                print("✅ Test e-postası başarıyla gönderildi → atilbilge@gmail.com")
            else:
                print("❌ Test e-postası gönderilemedi.")
        except Exception as e:
            print(f"❌ SMTP hatası: {e}")
        return

    if dry_run:
        print("🔍 KURU TEST MODU — e-posta gönderilmeyecek\n")
    else:
        print("📧 GERÇEK GÖNDERIM MODU\n")

    agencies = get_target_agencies()

    if not agencies:
        print("✅ Gönderilecek acente bulunamadı (hepsi zaten gönderilmiş veya e-postası yok).")
        return

    total_emails = sum(len(ag['emails']) for ag in agencies)
    print(f"{'='*60}")
    print(f"Toplam hedef acente : {len(agencies)}")
    print(f"Toplam e-posta      : {total_emails}")
    print(f"{'='*60}\n")

    for ag in agencies:
        print(f"[{ag['id']}] {ag['name']} ({ag['city'] or '?'})")
        for em in ag['emails']:
            print(f"   → {em}")

    print()

    if dry_run:
        print("Kuru test bitti. Gerçek göndermek için: python3 send_emails.py")
        return

    confirm = input(f"\n{len(agencies)} acenteye ({total_emails} e-posta) gerçekten göndermek istiyor musun? [evet/hayır]: ").strip().lower()
    if confirm not in ("evet", "e", "yes", "y"):
        print("İptal edildi.")
        return

    print("\n📡 Gmail SMTP'ye bağlanılıyor...")
    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD.replace(" ", ""))
        print("✅ Bağlantı başarılı.\n")
    except Exception as e:
        print(f"❌ SMTP bağlantı hatası: {e}")
        return

    sent_count   = 0
    failed_count = 0

    for ag in agencies:
        agency_id   = ag['id']
        agency_name = ag['name']
        emails      = ag['emails']

        print(f"[{agency_id}] {agency_name}")
        print(f"   📤 Gönderiliyor → {', '.join(emails)}")

        success = send_email(smtp, emails, agency_name)

        if success is not None:
            print(f"   ✅ Gönderildi.")
            sent_count += 1
            db.add_communication(
                agency_id = agency_id,
                sender    = GMAIL_ADDRESS,
                recipient = ", ".join(emails),
                message   = success,  # tam HTML içeriği
                channel   = "EMAIL",
                status    = "SENT"
            )
        else:
            failed_count += 1

        time.sleep(DELAY_BETWEEN_EMAILS)
        print()

    smtp.quit()

    print(f"{'='*60}")
    print(f"✅ Gönderildi : {sent_count}")
    print(f"❌ Başarısız  : {failed_count}")
    print(f"{'='*60}")
    print("Tüm gönderilenler DB'ye kaydedildi ve statüleri SENT olarak güncellendi.")


if __name__ == "__main__":
    main()
