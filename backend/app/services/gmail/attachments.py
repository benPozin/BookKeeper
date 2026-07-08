"""Download PDF/image attachments from scanned business emails into Documents.

Emails under the Business labels are already matched to a business, tax year,
and income/expense kind — their attachments are exactly the invoices and
receipts BookKeeper exists to collect, so no keyword matching is needed:
each saved attachment becomes a high-confidence Document tied to its email.
Images are converted to PDF (same normalization as phone uploads), duplicates
are dropped by content hash, and processing is committed per email so an
interrupted run resumes where it left off.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import DATA_DIR
from ...models import Business, Document, Email
from ..ingest.upload import IMAGE_EXTS, save_upload
from ..pdf import core, extract, matcher
from . import client

logger = logging.getLogger(__name__)

# Where downloaded attachments land (NOT the ScanSnap folder — the folder
# watcher must not re-ingest these through the keyword-matcher path).
ATTACH_DIR = DATA_DIR / "email_attachments"

ALLOWED_EXTS = {".pdf"} | IMAGE_EXTS


def iter_attachment_parts(payload: dict):
    """Yield every (nested) MIME part that carries a filename."""
    for part in payload.get("parts") or []:
        if part.get("filename"):
            yield part
        yield from iter_attachment_parts(part)


def _part_bytes(service, msg_id: str, part: dict) -> bytes | None:
    body = part.get("body") or {}
    if body.get("data"):
        return base64.urlsafe_b64decode(body["data"])
    if body.get("attachmentId"):
        att = (
            service.users().messages().attachments()
            .get(userId="me", messageId=msg_id, id=body["attachmentId"])
            .execute()
        )
        if att.get("data"):
            return base64.urlsafe_b64decode(att["data"])
    return None


def pending_count(session: Session) -> int:
    return (
        session.query(Email)
        .filter(Email.has_attachments.is_(True), Email.attachments_fetched.is_(False))
        .count()
    )


def fetch_new(session: Session, limit: int = 200, on_progress=None) -> dict:
    """Download attachments for every not-yet-fetched email with attachments."""
    if not (client.mode() == "real" and client.is_connected()):
        return {"error": "Gmail not connected.", "saved": 0}

    service = client.build_service()
    emails = (
        session.query(Email)
        .filter(Email.has_attachments.is_(True), Email.attachments_fetched.is_(False))
        .order_by(Email.id)
        .limit(limit)
        .all()
    )

    total = len(emails)
    saved = duplicates = skipped_parts = errors = 0
    items: list[dict] = []
    for i, email in enumerate(emails):
        if on_progress:
            on_progress(i, total, email.subject or email.gmail_msg_id)
        try:
            msg = (
                service.users().messages()
                .get(userId="me", id=email.gmail_msg_id, format="full")
                .execute()
            )
            for part in iter_attachment_parts(msg.get("payload") or {}):
                filename = part["filename"]
                if Path(filename).suffix.lower() not in ALLOWED_EXTS:
                    skipped_parts += 1
                    continue
                data = _part_bytes(service, email.gmail_msg_id, part)
                if not data:
                    skipped_parts += 1
                    continue
                result = _ingest_attachment(session, email, filename, data)
                if result == "saved":
                    saved += 1
                    items.append({"email": email.subject, "file": filename})
                else:
                    duplicates += 1
            # Mark done even when nothing was ingestable, so the email isn't
            # re-downloaded on every run.
            email.attachments_fetched = True
            session.commit()
        except Exception as e:
            session.rollback()
            errors += 1
            logger.exception("Attachment fetch failed for email %s", email.gmail_msg_id)
            items.append({"email": email.subject, "error": str(e)[:200]})
    if on_progress:
        on_progress(total, total, "Done")
    return {
        "emails_processed": total, "saved": saved, "duplicates": duplicates,
        "skipped_parts": skipped_parts, "errors": errors, "items": items[:100],
    }


def _ingest_attachment(session: Session, email: Email, filename: str, data: bytes) -> str:
    """Save one attachment and create its Document. Returns 'saved' or 'duplicate'."""
    path = save_upload(data, filename, str(ATTACH_DIR))  # images become PDFs
    content_hash = core.file_hash(path)
    existing = (
        session.query(Document).filter(Document.content_hash == content_hash).first()
    )
    if existing:
        path.unlink(missing_ok=True)
        return "duplicate"

    text, method, _err = core.extract_text(path)
    fields = extract.extract_fields(text, path.name)
    biz = session.get(Business, email.business_id) if email.business_id else None
    bucket = matcher.suggest_bucket(
        f"{path.name}\n{text}".lower(), biz.type if biz else ""
    ) if (text or path.name) else ""

    doc = Document(
        business_id=email.business_id,
        year_id=email.year_id,
        source="email",
        filename=path.name,
        original_path=str(path),
        content_hash=content_hash,
        folder_bucket=bucket,
        # The Gmail label already pins business/year — that IS the match.
        confidence="high" if email.business_id else "none",
        match_reason=(
            f"Attachment of '{(email.subject or '')[:80]}' "
            f"({email.date}) under {email.raw_label}"
            + (f" [{method}]" if method != "text" else "")
        ),
        status="matched" if email.business_id else "needs_review",
        kind=email.kind or "other",
        vendor=fields["vendor"],
        doc_date=fields["doc_date"] or email.date or "",
        amount=fields["amount"],
    )
    session.add(doc)
    try:
        # Commit per attachment: a rollback on a later part of the same email
        # (e.g. losing a duplicate-hash race with the folder watcher) must not
        # discard the documents already created for its earlier parts.
        session.commit()
    except IntegrityError:
        session.rollback()
        path.unlink(missing_ok=True)
        return "duplicate"
    return "saved"
