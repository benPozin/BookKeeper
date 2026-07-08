"""Deterministic sample emails used when no Gmail credentials are present.

Shaped exactly like the normalized records ``scan.py`` produces from the real
Gmail API, so downstream discovery/history code is identical in both modes.
Covers all 3 categories, multiple years, and two distinct rental properties
(to exercise the "one tab per rental business" requirement).
"""

from __future__ import annotations

# Each record: a normalized email. `business_hint` lets mock data name the
# specific business (e.g. a rental property); real mode derives it from labels.
MOCK_EMAILS = [
    # --- Consulting (SPAL) ---
    {"gmail_msg_id": "mock-c-2024-01", "category": "consulting",
     "business_hint": "SPAL", "subject": "SPAL Consulting — Invoice #1042 paid",
     "sender": "ar@clientco.com", "date": "2024-03-12", "has_attachments": True,
     "snippet": "Payment received for consulting services rendered in Feb 2024."},
    {"gmail_msg_id": "mock-c-2024-02", "category": "consulting",
     "business_hint": "SPAL", "subject": "SPAL — Software subscription receipt",
     "sender": "billing@devtools.com", "date": "2024-06-02", "has_attachments": True,
     "snippet": "Your annual subscription receipt is attached."},
    {"gmail_msg_id": "mock-c-2025-01", "category": "consulting",
     "business_hint": "SPAL", "subject": "SPAL Consulting — Invoice #1108",
     "sender": "ar@clientco.com", "date": "2025-02-20", "has_attachments": True,
     "snippet": "Invoice for January 2025 engagement."},

    # --- Rental: property A (123 Maple St) ---
    {"gmail_msg_id": "mock-r-a-2024-01", "category": "rental",
     "business_hint": "123 Maple St", "subject": "123 Maple St — Insurance renewal",
     "sender": "policies@insureco.com", "date": "2024-01-15", "has_attachments": True,
     "snippet": "Your rental property insurance policy has renewed."},
    {"gmail_msg_id": "mock-r-a-2024-02", "category": "rental",
     "business_hint": "123 Maple St", "subject": "123 Maple St — Property tax notice",
     "sender": "tax@citygov.ca", "date": "2024-07-08", "has_attachments": True,
     "snippet": "Annual municipal property tax statement enclosed."},
    {"gmail_msg_id": "mock-r-a-2025-01", "category": "rental",
     "business_hint": "123 Maple St", "subject": "123 Maple St — Hydro bill March",
     "sender": "billing@hydro.ca", "date": "2025-03-30", "has_attachments": True,
     "snippet": "Your electricity statement is ready."},

    # --- Rental: property B (456 Oak Ave) ---
    {"gmail_msg_id": "mock-r-b-2024-01", "category": "rental",
     "business_hint": "456 Oak Ave", "subject": "456 Oak Ave — Mortgage statement",
     "sender": "statements@bigbank.ca", "date": "2024-12-01", "has_attachments": True,
     "snippet": "Annual mortgage interest statement for your records."},
    {"gmail_msg_id": "mock-r-b-2025-01", "category": "rental",
     "business_hint": "456 Oak Ave", "subject": "456 Oak Ave — Internet receipt",
     "sender": "receipts@isp.ca", "date": "2025-01-10", "has_attachments": True,
     "snippet": "Thanks for your payment — receipt attached."},

    # --- Real Estate (income/expenses) ---
    {"gmail_msg_id": "mock-re-2024-01", "category": "real_estate",
     "business_hint": "Real Estate", "subject": "Real Estate — Closing fees statement",
     "sender": "escrow@title.ca", "date": "2024-09-18", "has_attachments": True,
     "snippet": "Statement of fees for the property closing."},
    {"gmail_msg_id": "mock-re-2025-01", "category": "real_estate",
     "business_hint": "Real Estate", "subject": "Real Estate — Commission income",
     "sender": "deals@brokerage.ca", "date": "2025-04-05", "has_attachments": False,
     "snippet": "Commission payout summary for Q1 2025."},

    # --- A 2023 item to prove multi-year discovery ---
    {"gmail_msg_id": "mock-r-a-2023-01", "category": "rental",
     "business_hint": "123 Maple St", "subject": "123 Maple St — Gas bill Dec 2023",
     "sender": "billing@gasco.ca", "date": "2023-12-22", "has_attachments": True,
     "snippet": "Your natural gas statement is ready."},
]


def mock_scan() -> list[dict]:
    """Return a copy of the deterministic mock email set, tagged raw_label."""
    out = []
    for e in MOCK_EMAILS:
        rec = dict(e)
        rec["sender_name"] = rec["sender"].split("@")[0]
        rec["raw_label"] = f"Business/{rec['category']}"
        out.append(rec)
    return out
