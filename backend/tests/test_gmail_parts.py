"""Gmail payload helpers: attachment-part discovery and work-label mapping."""

from app.services.gmail.attachments import ALLOWED_EXTS, iter_attachment_parts
from app.services.gmail.scan import _work_labels, payload_has_attachment

NESTED_PAYLOAD = {
    "mimeType": "multipart/mixed",
    "parts": [
        {"mimeType": "multipart/alternative", "filename": "", "parts": [
            {"mimeType": "text/plain", "filename": ""},
            {"mimeType": "text/html", "filename": ""},
        ]},
        {"mimeType": "application/pdf", "filename": "invoice.pdf",
         "body": {"attachmentId": "att-1"}},
        {"mimeType": "image/jpeg", "filename": "receipt.jpg",
         "body": {"data": "aGk="}},
    ],
}


def test_iter_attachment_parts_walks_nesting():
    names = [p["filename"] for p in iter_attachment_parts(NESTED_PAYLOAD)]
    assert names == ["invoice.pdf", "receipt.jpg"]


def test_payload_has_attachment():
    assert payload_has_attachment(NESTED_PAYLOAD)
    assert not payload_has_attachment({"parts": [{"filename": "", "parts": []}]})
    assert not payload_has_attachment({})


def test_allowed_extensions_cover_pdf_and_photos():
    assert ".pdf" in ALLOWED_EXTS
    assert ".jpg" in ALLOWED_EXTS
    assert ".heic" in ALLOWED_EXTS


def test_work_labels_filters_years_and_exclusions():
    labels = [
        {"id": "L1", "name": "Business/Rental/51 Lakeside Dr/Income2024"},
        {"id": "L2", "name": "Business/Rental/51 Lakeside Dr/Expenses2024"},
        {"id": "L3", "name": "Business/Rental/zArchived/Expenses2024"},
        {"id": "L4", "name": "Business/Rental/81 Srigley St/Expenses1999"},
        {"id": "L5", "name": "Business/Rental"},  # no year tag
        {"id": "L6", "name": "Personal/Expenses2024"},  # outside the prefix
    ]
    cfg = {
        "gmail_label_rental": "Business/Rental",
        "scan_year_start": "2022",
        "scan_year_end": "2026",
    }
    work = _work_labels(labels, cfg)
    ids = [label_id for _cat, label_id, _name, _info in work]
    assert ids == ["L1", "L2"]
    info = work[0][3]
    assert info["business"] == "51 Lakeside Dr"
    assert info["year"] == 2024
    assert info["kind"] == "income"
