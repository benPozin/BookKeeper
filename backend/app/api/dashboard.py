"""Dashboard API: high-level status of every feature, real recent activity,
real filed-per-month counts, and a per-year "is everything done" checklist.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import REPO_ROOT
from ..db import get_session
from ..models import Business, Document, Email, RoutingLog, Setting, Year

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Single source of truth for which features exist and their phase/status.
FEATURES = [
    {"id": "gmail", "name": "Gmail Scan", "phase": 1, "status": "active",
     "summary": "Scan business email daily; discover businesses & years."},
    {"id": "documents", "name": "Documents / PDF Matching", "phase": 2,
     "status": "active",
     "summary": "Read scanned PDFs, match to business/year, de-duplicate."},
    {"id": "scan", "name": "New Scan", "phase": 3, "status": "active",
     "summary": "Ingest from ScanSnap ix1600 and mobile uploads."},
    {"id": "templates", "name": "Expense Templates", "phase": 4,
     "status": "active",
     "summary": "Populate Home Office, Rental, Car & Real Estate Excel sheets."},
    {"id": "organizer", "name": "Folder Organizer", "phase": 5,
     "status": "active",
     "summary": "Build the accountant-ready folder structure by category."},
    {"id": "automation", "name": "Daily Automation", "phase": 6,
     "status": "active",
     "summary": "Scheduled daily scan + ingest + routing."},
    {"id": "export", "name": "Accountant Export", "phase": 7,
     "status": "active",
     "summary": "Bundle a year's folder tree to send to the accountant."},
]


def _output_root(session: Session) -> Path:
    row = session.query(Setting).filter(Setting.key == "output_root").first()
    val = row.value if row and row.value else str(REPO_ROOT / "output")
    return Path(val).expanduser()


def _recent_activity(session: Session, limit: int = 8) -> list[dict]:
    """Real recent events, newest first — RoutingLog entries (files filed
    during an organizer build) plus recently ingested Documents. Document
    events carry vendor/amount/business so the feed can show what a file IS,
    not just its name."""
    events = []
    log_rows = (
        session.query(RoutingLog, Document, Business.name)
        .outerjoin(Document, RoutingLog.document_id == Document.id)
        .outerjoin(Business, Document.business_id == Business.id)
        .order_by(RoutingLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    for log, doc, biz_name in log_rows:
        name = Path(log.to_path).name
        events.append({
            "icon": "organizer",
            "text": f"Filed “{name}”",
            "at": log.timestamp,
            "vendor": (doc.vendor if doc else "") or "",
            "amount": doc.amount if doc else None,
            "business": biz_name or "",
            "verb": "Filed",
            "filename": name,
        })
    doc_rows = (
        session.query(Document, Business.name)
        .outerjoin(Business, Document.business_id == Business.id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .all()
    )
    for doc, biz_name in doc_rows:
        verb = "Matched" if doc.status in ("matched", "filed") else "Ingested"
        events.append({
            "icon": "documents",
            "text": f"{verb} “{doc.filename}”",
            "at": doc.created_at,
            "vendor": doc.vendor or "",
            "amount": doc.amount,
            "business": biz_name or "",
            "verb": verb,
            "filename": doc.filename,
        })
    events.sort(key=lambda e: e["at"] or datetime.min, reverse=True)
    now = datetime.now()
    out = []
    for e in events[:limit]:
        delta = now - e["at"] if e["at"] else timedelta(0)
        if delta.days >= 1:
            when = f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            when = f"{delta.seconds // 3600}h ago"
        elif delta.seconds >= 60:
            when = f"{delta.seconds // 60}m ago"
        else:
            when = "just now"
        item = {k: v for k, v in e.items() if k != "at"}
        item["time"] = when
        out.append(item)
    return out


def _amounts_by_month(session: Session, months: int = 12) -> list[list]:
    """Dollars captured per month (sum of extracted amounts by document date)
    for the last N months, oldest first — powers the dashboard chart.
    [[label, amount, doc_count], ...]"""
    now = datetime.now()
    buckets: list[tuple[str, str]] = []
    y, m = now.year, now.month
    for _ in range(months):
        buckets.append((f"{y:04d}-{m:02d}", datetime(y, m, 1).strftime("%b")))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    buckets.reverse()

    sums = {key: 0.0 for key, _ in buckets}
    counts = {key: 0 for key, _ in buckets}
    rows = (
        session.query(Document.doc_date, Document.amount)
        .filter(Document.amount.isnot(None), Document.doc_date != "")
        .all()
    )
    for doc_date, amount in rows:
        key = doc_date[:7]
        if key in sums:
            sums[key] += amount
            counts[key] += 1
    return [[label, round(sums[key], 2), counts[key]] for key, label in buckets]


def _amount_summary(session: Session) -> dict:
    """Headline money figures: overall and for the most recent tax year."""
    total = sum(
        a for (a,) in session.query(Document.amount).filter(Document.amount.isnot(None))
    )
    latest = (
        session.query(Year.label)
        .join(Document, Document.year_id == Year.id)
        .filter(Document.amount.isnot(None))
        .order_by(Year.label.desc())
        .first()
    )
    latest_label = latest[0] if latest else ""
    year_total = 0.0
    year_docs = 0
    if latest_label:
        rows = (
            session.query(Document.amount)
            .join(Year, Document.year_id == Year.id)
            .filter(Year.label == latest_label, Document.amount.isnot(None))
            .all()
        )
        year_total = sum(a for (a,) in rows)
        year_docs = len(rows)
    return {
        "total": round(total, 2),
        "latest_year": latest_label,
        "latest_year_total": round(year_total, 2),
        "latest_year_docs": year_docs,
    }


@router.get("/summary")
def summary(session: Session = Depends(get_session)) -> dict:
    pending = (
        session.query(Document)
        .filter(Document.status.in_(("needs_review", "unmatched", "extraction_failed")))
        .count()
    )
    return {
        "features": FEATURES,
        "counts": {
            "businesses": session.query(Business).count(),
            "emails": session.query(Email).count(),
            "documents": session.query(Document).count(),
        },
        "needs_attention": pending,
        "activity": _recent_activity(session),
        "chart": _amounts_by_month(session),
        "amounts": _amount_summary(session),
    }


@router.get("/checklist/{year}")
def checklist(year: str, session: Session = Depends(get_session)) -> dict:
    year_ids = [y.id for y in session.query(Year).filter(Year.label == year).all()]
    if year_ids:
        docs_q = session.query(Document).filter(Document.year_id.in_(year_ids))
        emails_count = session.query(Email).filter(Email.year_id.in_(year_ids)).count()
    else:
        docs_q = session.query(Document).filter(Document.id.is_(None))  # empty
        emails_count = 0

    total_docs = docs_q.count()
    pending_docs = docs_q.filter(
        Document.status.in_(("needs_review", "unmatched", "extraction_failed"))
    ).count()
    filed_docs = docs_q.filter(Document.status == "filed").count()

    year_dir = _output_root(session) / year
    organized = year_dir.exists() and filed_docs > 0
    exported = (_output_root(session) / f"BookKeeper_{year}.zip").exists()

    items = [
        {
            "key": "gmail", "label": "Gmail scanned", "done": emails_count > 0,
            "detail": f"{emails_count} emails" if emails_count else "No emails yet",
        },
        {
            "key": "documents", "label": "Documents reviewed",
            "done": total_docs > 0 and pending_docs == 0,
            "detail": (f"{total_docs - pending_docs}/{total_docs} reviewed"
                       if total_docs else "No documents yet"),
        },
        {
            "key": "organizer", "label": "Folders organized", "done": organized,
            "detail": f"{filed_docs} filed" if organized else "Not built yet",
        },
        {
            "key": "export", "label": "Accountant package exported", "done": exported,
            "detail": "Ready to send" if exported else "Not built yet",
        },
    ]
    return {"year": year, "items": items}
