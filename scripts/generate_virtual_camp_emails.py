import csv
import os
import re
from datetime import datetime
from textwrap import wrap


INPUT_CSV = r"c:\Users\mxlil\Downloads\Targets - 26 - Emails(1).csv"
EVENT_URL = "http://shorturl.at/Xy5N0"
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "virtual_camp_emails_personalized.csv")
OUTPUT_PDF = os.path.join(OUTPUT_DIR, "virtual_camp_emails_personalized.pdf")


def clean_text(value: str) -> str:
    if value is None:
        return ""
    return str(value).strip().strip("|").strip()


def clean_email(raw_email: str) -> str:
    email = clean_text(raw_email)
    email = email.replace("Email:", "").replace("email:", "").strip()
    email = email.replace(" my email", "").replace("My email", "").strip()
    return email


def looks_like_email(value: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value))


def build_subject(first_name: str, year: str) -> str:
    if first_name and year:
        return f"{first_name}, April Virtual Camp for Class of {year} closes soon"
    if first_name:
        return f"{first_name}, April Virtual Camp registration closes soon"
    return "April Virtual Camp registration closes soon"


def build_intro(first_name: str, year: str, position: str) -> str:
    name = first_name if first_name else "there"
    details = []
    if year:
        details.append(f"Class of {year}")
    if position:
        details.append(position.upper())

    if details:
        profile_line = f"I wanted to personally reach out because as a {', '.join(details)} athlete, this is a great chance to get evaluated and seen without traveling."
    else:
        profile_line = "I wanted to personally reach out because this is a great chance to get evaluated and seen without traveling."

    return f"Hi {name},\n\n{profile_line}"


def build_email_body(first_name: str, year: str, position: str) -> str:
    intro = build_intro(first_name, year, position)
    return (
        f"{intro}\n\n"
        "Field IQ Virtual Camps are built for athletes who want real evaluation, real feedback, and real exposure without needing to travel.\n\n"
        "This camp also helps strengthen your profile in our national database, where your evaluation has the potential to be seen by 1,300+ college coaches across 120+ programs.\n\n"
        "Here is what you will get:\n"
        "- Position-specific drill breakdown\n"
        "- Film evaluation with detailed feedback\n"
        "- Measurables review (40, shuttle, vertical, etc.)\n"
        "- Honest coaching insight on how to improve now\n"
        "- Real exposure to college programs through our network\n\n"
        "April Camp registration is closing soon.\n"
        "This is the smart way to save time and save money while still getting serious recruiting visibility.\n\n"
        "This is not a one-time event. We are building a long-term relationship and are here to help with your recruiting needs at every step.\n\n"
        f"Lock in your spot now: {EVENT_URL}\n\n"
        "Max Lilly\n"
        "@MaxLilly01"
    )


def write_pdf(rows):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(OUTPUT_PDF, pagesize=LETTER)
    width, height = LETTER
    margin_x = 50
    y = height - 50
    line_height = 14

    def draw_wrapped(text: str, indent: int = 0):
        nonlocal y
        max_chars = 95 - int(indent * 0.8)
        for raw_line in text.split("\n"):
            wrapped = wrap(raw_line, width=max_chars) if raw_line else [""]
            for line in wrapped:
                if y < 60:
                    c.showPage()
                    y = height - 50
                c.drawString(margin_x + indent, y, line)
                y -= line_height

    for i, row in enumerate(rows, start=1):
        header = f"Prospect {i}: {row['first']} {row['last']}".strip()
        if header.endswith(":"):
            header = f"Prospect {i}"
        c.setFont("Helvetica-Bold", 12)
        draw_wrapped(header)
        c.setFont("Helvetica", 10)
        draw_wrapped(f"To: {row['email']}")
        draw_wrapped(f"Subject: {row['subject']}")
        draw_wrapped("")
        draw_wrapped(row["email_body"])
        draw_wrapped("")
        draw_wrapped("-" * 85)
        y -= 6

    c.save()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generated_rows = []
    with open(INPUT_CSV, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            first = clean_text(r.get("First", ""))
            last = clean_text(r.get("Last", ""))
            year = clean_text(r.get("Year", ""))
            position = clean_text(r.get("Position", ""))
            email = clean_email(r.get("Email", ""))

            if not email:
                continue

            subject = build_subject(first, year)
            body = build_email_body(first, year, position)
            generated_rows.append(
                {
                    "first": first,
                    "last": last,
                    "year": year,
                    "position": position,
                    "email": email,
                    "email_valid": "yes" if looks_like_email(email) else "no",
                    "subject": subject,
                    "email_body": body,
                }
            )

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as out_f:
        fieldnames = [
            "first",
            "last",
            "year",
            "position",
            "email",
            "email_valid",
            "subject",
            "email_body",
        ]
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(generated_rows)

    write_pdf(generated_rows)

    print(f"Generated {len(generated_rows)} personalized emails.")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"PDF: {OUTPUT_PDF}")
    print(f"Created at: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
