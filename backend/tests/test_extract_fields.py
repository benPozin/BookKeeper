"""Heuristic vendor/date/amount extraction."""

from app.services.pdf.extract import (
    extract_amount,
    extract_date,
    extract_fields,
    extract_vendor,
)

ENBRIDGE = """ENBRIDGE GAS INC.
500 Consumers Rd, North York ON

Statement Date: March 14, 2025
Account: 9100 4432 1178

Previous balance            $180.10
Payment received            -$180.10
New charges                 $187.42

Total Amount Due: $187.42
Due Date: 04/02/2025
"""

RECEIPT = """CANADIAN TIRE #345
2025-01-09 14:22
WINDSHIELD WASHER 3.8L    5.49
MOTOR OIL 5W30           38.99
SUBTOTAL                 44.48
HST 13%                   5.78
TOTAL                   $50.26
"""


def test_utility_bill_full_extraction():
    fields = extract_fields(ENBRIDGE, "enbridge_march.pdf")
    assert fields == {
        "vendor": "Enbridge Gas",
        "doc_date": "2025-03-14",
        "amount": 187.42,
    }


def test_total_beats_subtotal():
    assert extract_amount(RECEIPT) == 50.26


def test_known_vendor_and_iso_date():
    fields = extract_fields(RECEIPT, "receipt1.pdf")
    assert fields["vendor"] == "Canadian Tire"
    assert fields["doc_date"] == "2025-01-09"


def test_vendor_falls_back_to_first_plausible_line():
    text = "Dr. Jane Smith Dentistry\nInvoice date: Jan 5, 2024\nAmount due 250.00\n"
    assert extract_vendor(text) == "Dr. Jane Smith Dentistry"
    assert extract_date(text) == "2024-01-05"
    assert extract_amount(text) == 250.0


def test_date_formats():
    assert extract_date("Statement date: 2025-03-14") == "2025-03-14"
    assert extract_date("Invoice Date: 03/14/2025") == "2025-03-14"
    assert extract_date("Date issued: 14 March 2025") == "2025-03-14"
    # day > 12 in the first slot means DD/MM/YYYY
    assert extract_date("Date: 14/03/2025") == "2025-03-14"


def test_keyword_line_beats_larger_stray_number():
    text = "Reference: $9,999.00\nAmount due: $42.17\n"
    assert extract_amount(text) == 42.17


def test_empty_text_gives_blanks():
    assert extract_fields("", "x.pdf") == {"vendor": "", "doc_date": "", "amount": None}


def test_account_number_sized_figures_ignored():
    assert extract_amount("Account 91004432\nTotal due $12.00") == 12.0
