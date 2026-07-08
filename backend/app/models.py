"""ORM models for BookKeeper.

These cover the full data model from the plan even though Phase 0 only
exercises ``Setting``. Later phases populate Business/Year/Email/Document/
RoutingLog as Gmail, PDF matching, and the organizer come online.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from .config import DEFAULT_SETTINGS
from .db import Base


class Setting(Base):
    """Key/value app settings. Overrides the code defaults in config.py."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Business(Base):
    """A line of business discovered from Gmail (or added manually)."""

    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # consulting | rental | real_estate
    type: Mapped[str] = mapped_column(String(32))
    # e.g. "SPAL" or a rental property address
    external_key: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    emails: Mapped[list["Email"]] = relationship(back_populates="business")
    documents: Mapped[list["Document"]] = relationship(back_populates="business")


class Year(Base):
    """A reporting year (calendar or corporate fiscal) for a business."""

    __tablename__ = "years"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[Optional[int]] = mapped_column(ForeignKey("businesses.id"))
    label: Mapped[str] = mapped_column(String(32))  # e.g. "2025" or "FY2025"
    start_date: Mapped[str] = mapped_column(String(10), default="")  # YYYY-MM-DD
    end_date: Mapped[str] = mapped_column(String(10), default="")


class Email(Base):
    """An audit record of a scanned business email."""

    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    gmail_msg_id: Mapped[str] = mapped_column(String(64), unique=True)
    business_id: Mapped[Optional[int]] = mapped_column(ForeignKey("businesses.id"))
    year_id: Mapped[Optional[int]] = mapped_column(ForeignKey("years.id"))
    category: Mapped[str] = mapped_column(String(32), default="")
    subject: Mapped[str] = mapped_column(Text, default="")
    sender: Mapped[str] = mapped_column(String(255), default="")
    date: Mapped[str] = mapped_column(String(32), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    has_attachments: Mapped[bool] = mapped_column(default=False)
    # Set once this email's attachments were downloaded into the document
    # pipeline (or it was confirmed to have no ingestable attachments).
    attachments_fetched: Mapped[bool] = mapped_column(default=False)
    raw_label: Mapped[str] = mapped_column(String(255), default="")
    # income | expense | other — derived from the Gmail sub-label (Income20XX/Expenses20XX)
    kind: Mapped[str] = mapped_column(String(16), default="other")

    business: Mapped[Optional["Business"]] = relationship(back_populates="emails")


class Document(Base):
    """A scanned/ingested document and where it was routed."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[Optional[int]] = mapped_column(ForeignKey("businesses.id"))
    year_id: Mapped[Optional[int]] = mapped_column(ForeignKey("years.id"))
    source: Mapped[str] = mapped_column(String(16), default="")  # scansnap|mobile|email
    filename: Mapped[str] = mapped_column(String(512), default="")
    original_path: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    routed_path: Mapped[str] = mapped_column(Text, default="")
    folder_bucket: Mapped[str] = mapped_column(String(8), default="")  # 6a..6i
    # high | medium | low | none — confidence of the business/year match
    confidence: Mapped[str] = mapped_column(String(8), default="none")
    match_reason: Mapped[str] = mapped_column(Text, default="")
    # AI review (optional, Gemini): a very short overview + reviewed flag
    summary: Mapped[str] = mapped_column(Text, default="")
    ai_reviewed: Mapped[bool] = mapped_column(default=False)
    # income | expense | other — from the source email label or AI review
    kind: Mapped[str] = mapped_column(String(16), default="other")
    # Extracted fields (heuristic regex over the text; AI may refine them)
    vendor: Mapped[str] = mapped_column(String(160), default="")
    doc_date: Mapped[str] = mapped_column(String(10), default="")  # YYYY-MM-DD
    amount: Mapped[Optional[float]] = mapped_column(default=None)
    # new | matched | needs_review | unmatched | filed
    status: Mapped[str] = mapped_column(String(32), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    business: Mapped[Optional["Business"]] = relationship(back_populates="documents")


class RoutingLog(Base):
    """Audit trail of every file move the organizer performs."""

    __tablename__ = "routing_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"))
    from_path: Mapped[str] = mapped_column(Text, default="")
    to_path: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(String(32), default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def seed_default_settings(engine: Engine) -> None:
    """Insert any missing default settings without overwriting user values."""
    with Session(engine) as session:
        existing = {s.key for s in session.query(Setting).all()}
        for key, value in DEFAULT_SETTINGS.items():
            if key not in existing:
                session.add(Setting(key=key, value=value))
        session.commit()
