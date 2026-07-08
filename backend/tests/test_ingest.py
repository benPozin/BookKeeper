from pathlib import Path

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (register models on Base.metadata)
from app.db import Base
from app.services.pdf import ingest


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


def _make_pdf(path: Path, text: str) -> None:
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, text)
    c.save()


def test_ingest_dedupes_identical_content_by_hash(tmp_path, session):
    pdf1 = tmp_path / "receipt.pdf"
    _make_pdf(pdf1, "51 Lakeside Dr insurance 2024")

    r1 = ingest.ingest_path(session, pdf1, source="scansnap", businesses=[])
    session.commit()
    assert r1["status"] != "duplicate"

    # A byte-identical copy under a different filename must still be caught.
    pdf2 = tmp_path / "receipt_copy.pdf"
    pdf2.write_bytes(pdf1.read_bytes())
    r2 = ingest.ingest_path(session, pdf2, source="scansnap", businesses=[])
    assert r2["status"] == "duplicate"
    assert r2["of_id"] == r1["id"]


def test_ingest_matches_business_by_keyword(tmp_path, session):
    pdf = tmp_path / "51_lakeside_insurance.pdf"
    _make_pdf(pdf, "51 Lakeside Dr insurance policy 2024")
    businesses = [{"id": 1, "name": "51 Lakeside Dr", "type": "rental", "years": ["2024"]}]

    r = ingest.ingest_path(session, pdf, source="scansnap", businesses=businesses)
    assert r["status"] in ("matched", "needs_review")
    assert r["confidence"] in ("high", "medium")


def test_ingest_unreadable_file_is_flagged_extraction_failed(tmp_path, session):
    # Not a real PDF — pdfplumber will raise trying to parse the header.
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"not a real pdf file")

    r = ingest.ingest_path(session, bad, source="scansnap", businesses=[])
    assert r["status"] == "extraction_failed"
