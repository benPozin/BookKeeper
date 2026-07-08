"""Generate realistic sample PDF receipts/statements for dev testing.

Used on the Mac (where the real ScanSnap folder doesn't exist) to exercise the
full extract → match → dedup pipeline. Includes an ambiguous doc (no business
keyword) and an exact duplicate to prove de-duplication.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# (filename, title, body lines) — text is embedded so extraction works without OCR.
SAMPLES = [
    ("51_Lakeside_Dr_Insurance_2024.pdf", "Rental Property Insurance Policy", [
        "Insured Property: 51 Lakeside Dr, Innisfil ON",
        "Policy Period: Jan 1, 2024 - Dec 31, 2024",
        "Annual Premium: $1,284.00", "Coverage: Landlord / rental dwelling"]),
    ("1632_Bayview_Ave_Hydro_2025.pdf", "Hydro One Electricity Statement", [
        "Service Address: 1632 Bayview Ave, Barrie ON",
        "Billing Date: March 2025", "Amount Due: $142.55",
        "Electricity usage for rental unit"]),
    ("1201_Connaught_Dr_Mortgage_2024.pdf", "Annual Mortgage Statement", [
        "Property: 1201 Connaught Dr, Ennismore ON",
        "Statement Year: 2024", "Principal Balance: $312,400.00",
        "Mortgage interest paid: $11,902.18"]),
    ("81_Srigley_St_PropertyTax_2024.pdf", "Municipal Property Tax Notice", [
        "Property: 81 Srigley St, Barrie ON", "Tax assessment notice 2024",
        "Total property tax: $3,410.00"]),
    ("SPAL_Consulting_Invoice_2025.pdf", "SPAL Consulting - Invoice #1108", [
        "From: SPAL Consulting", "Date: 2025-02-20",
        "Software development services - January 2025", "Total: $8,500.00"]),
    ("RealEstate_Commission_2025.pdf", "Real Estate Brokerage Statement", [
        "Real Estate commission payout", "Period: Q1 2025",
        "TREB / CREA member services", "Net commission: $14,200.00"]),
    ("315_Cavell_Internet_2024.pdf", "Internet Service Receipt", [
        "Service Address: 315 Cavell (home office)", "Year: 2024",
        "Monthly internet - business use portion", "Amount: $89.00"]),
    ("Lexus_RX350_Car_Insurance_2024.pdf", "Automobile Insurance", [
        "Vehicle: Lexus RX 350", "Policy year 2024",
        "Auto insurance premium: $1,704.12", "CAA roadside included"]),
    ("misc_receipt.pdf", "Cash Register Receipt", [
        "Store #4471", "Date: 2024-08-03", "Sundry items",
        "Total: $42.10", "Thank you for shopping"]),
]

# An exact duplicate of the first sample to test de-duplication.
DUPLICATE_OF = "51_Lakeside_Dr_Insurance_2024.pdf"
DUPLICATE_AS = "scan_copy_of_lakeside_insurance.pdf"


def _write_pdf(path: Path, title: str, lines: list[str]) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 90
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, title)
    y -= 36
    c.setFont("Helvetica", 11)
    for line in lines:
        c.drawString(72, y, line)
        y -= 22
    c.showPage()
    c.save()


def generate_samples(dest_dir: str | Path) -> dict:
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, title, lines in SAMPLES:
        p = dest / filename
        _write_pdf(p, title, lines)
        written.append(filename)
    # Duplicate: copy the bytes so the hash is identical (dedup test).
    shutil.copy(dest / DUPLICATE_OF, dest / DUPLICATE_AS)
    written.append(DUPLICATE_AS)
    return {"dir": str(dest), "count": len(written), "files": written}
