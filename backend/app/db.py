"""SQLAlchemy engine/session setup backed by a local SQLite file."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DB_PATH, ensure_dirs


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


ensure_dirs()

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
    """WAL mode lets readers and writers overlap; busy_timeout avoids
    'database is locked' errors when the watcher, scheduler, and API threads
    all touch the DB at once instead of surfacing as a silent failure."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables, run lightweight column migrations, seed default settings."""
    from . import models  # noqa: F401  (register models on Base.metadata)
    from .services import backup

    backup.backup_now("pre-migration")
    Base.metadata.create_all(engine)
    _migrate_columns()
    models.seed_default_settings(engine)


def _migrate_columns() -> None:
    """Add newly-introduced columns to existing SQLite tables (no data loss)."""
    from sqlalchemy import text

    wanted = {
        "documents": [
            ("summary", "TEXT DEFAULT ''"),
            ("ai_reviewed", "BOOLEAN DEFAULT 0"),
            ("kind", "VARCHAR(16) DEFAULT 'other'"),
            ("vendor", "VARCHAR(160) DEFAULT ''"),
            ("doc_date", "VARCHAR(10) DEFAULT ''"),
            ("amount", "FLOAT"),
        ],
        "emails": [
            ("attachments_fetched", "BOOLEAN DEFAULT 0"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))
            }
            for name, decl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {decl}"))

        # Two ingest paths (e.g. the watcher firing on_created and on_moved for
        # the same file) can race past the "does this hash exist" check before
        # either has committed, leaving duplicate rows. Drop the extras,
        # keeping the oldest, before enforcing uniqueness going forward.
        dupes = conn.execute(text(
            "SELECT content_hash FROM documents WHERE content_hash != '' "
            "GROUP BY content_hash HAVING COUNT(*) > 1"
        )).fetchall()
        for (content_hash,) in dupes:
            ids = [
                row[0] for row in conn.execute(
                    text("SELECT id FROM documents WHERE content_hash = :h ORDER BY id"),
                    {"h": content_hash},
                )
            ]
            for stale_id in ids[1:]:
                conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": stale_id})

        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_content_hash_unique "
            "ON documents(content_hash) WHERE content_hash != ''"
        ))

        # The Claude/Anthropic provider was removed (user decision, 2026-07-05).
        # Drop its leftover settings rows — including any stored API key.
        conn.execute(text(
            "DELETE FROM settings WHERE key IN ('ai_provider', 'anthropic_api_key')"
        ))


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a scoped DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
