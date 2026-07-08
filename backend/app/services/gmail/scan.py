"""Scan business email → normalize → discover businesses/years → persist.

Real mode walks the Gmail label TREE (labels are flat strings joined by "/"):
for each active category prefix (Consulting, Rental, Real Estate, Home) it
finds every year-tagged sub-label in range and pulls its messages. Business,
tax year, and income/expense kind are read straight from the label path, e.g.

    Business/Rental/51 Lakeside Dr/Income2024
            ^category        ^business      ^kind+year

Mock mode produces the same normalized records so discovery/persistence is
identical in both modes.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ...models import Business, Document, Email, Setting, Year
from . import client
from .mock import mock_scan

# category -> (settings key holding its parent label, business type, default name)
CATEGORIES = {
    "consulting": ("gmail_label_consulting", "consulting", "SPAL"),
    "rental": ("gmail_label_rental", "rental", "Rental"),
    "real_estate": ("gmail_label_real_estate", "real_estate", "Real Estate"),
    "home_office": ("gmail_label_home", "home_office", "315 Cavell"),
}
# Real Estate has no per-entity segment — it's a single business.
FIXED_BUSINESS = {"real_estate": "Real Estate"}

# Skip archived / misc groups even though they live elsewhere in the tree.
EXCLUDE_TOKENS = ("zarchived", "zother")

# Matches Income2024 / Expenses2024 / Expense2013 / "Expenses 2011" / Explense2015 typo.
YEAR_RE = re.compile(r"(expenses?|income|explense)\s*(20\d\d)", re.I)

MAX_PER_LABEL = 2000


# --- settings helpers -------------------------------------------------------
def _settings(session: Session) -> dict:
    return {s.key: s.value for s in session.query(Setting).all()}


def _set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    session.commit()


def year_label(date_str: str, fy_mode: str, fy_end: str) -> str:
    """Calendar year ('2024') or fiscal year ('FY2024') from an email date."""
    try:
        y, m, d = (int(x) for x in date_str.split("-"))
    except Exception:
        logger.warning("year_label: unparseable date %r", date_str)
        return "unknown"
    if fy_mode != "fiscal":
        return str(y)
    try:
        fm, fd = (int(x) for x in fy_end.split("-"))
    except Exception:
        logger.warning("year_label: unparseable fiscal_year_end %r, falling back to calendar year", fy_end)
        return str(y)
    return f"FY{y}" if (m, d) <= (fm, fd) else f"FY{y + 1}"


def parse_label(category: str, full_label: str, prefix: str) -> dict:
    """Derive business name, tax year, and kind from a full label path."""
    rest = full_label[len(prefix):].lstrip("/")
    segs = [s for s in rest.split("/") if s]

    year = None
    kind = "other"
    for seg in segs:
        m = YEAR_RE.search(seg)
        if m:
            kind = "income" if m.group(1).lower() == "income" else "expense"
            year = int(m.group(2))
            break

    _key, _btype, default_name = CATEGORIES[category]
    if category in FIXED_BUSINESS:
        business = FIXED_BUSINESS[category]
    elif segs and not YEAR_RE.search(segs[0]):
        business = segs[0]
    else:
        business = default_name

    return {"business": business, "year": year, "kind": kind}


# --- real-mode fetching -----------------------------------------------------
def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _list_ids(service, label_id: str, query: str | None = None) -> list[str]:
    ids: list[str] = []
    page = None
    while True:
        kw = {"userId": "me", "labelIds": [label_id], "maxResults": 500}
        if query:
            kw["q"] = query
        if page:
            kw["pageToken"] = page
        resp = service.users().messages().list(**kw).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        page = resp.get("nextPageToken")
        if not page or len(ids) >= MAX_PER_LABEL:
            break
    return ids


# Gmail rejects big batches with 429 "Too many concurrent requests for user"
# (each batch item counts as a concurrent request). 25 stays comfortably
# under the limit; anything throttled anyway is retried with backoff below.
BATCH_SIZE = 25
MAX_BATCH_ATTEMPTS = 6
RETRYABLE_STATUSES = {403, 429, 500, 502, 503}


def _batch_get(service, ids: list[str], fmt: str = "metadata") -> dict[str, dict]:
    """Fetch many messages with batched HTTP requests instead of one round
    trip per message — this is what turns a multi-minute full scan into
    seconds. Rate-limited items are retried with exponential backoff; only
    items that keep failing are skipped (and logged)."""
    out: dict[str, dict] = {}
    retryable: list[str] = []

    def _cb(request_id, response, exception):
        if exception is None:
            out[request_id] = response
            return
        status = getattr(getattr(exception, "resp", None), "status", None)
        if status is not None and int(status) in RETRYABLE_STATUSES:
            retryable.append(request_id)
        else:
            logger.warning("batched message get failed for %s: %s", request_id, exception)

    pending = list(ids)
    for attempt in range(MAX_BATCH_ATTEMPTS):
        if not pending:
            break
        if attempt:
            time.sleep(min(2 ** attempt, 30))
        retryable.clear()
        for i in range(0, len(pending), BATCH_SIZE):
            batch = service.new_batch_http_request(callback=_cb)
            for mid in pending[i:i + BATCH_SIZE]:
                kw = {"userId": "me", "id": mid, "format": fmt}
                if fmt == "metadata":
                    kw["metadataHeaders"] = ["Subject", "From"]
                batch.add(service.users().messages().get(**kw), request_id=mid)
            batch.execute()
        pending = list(retryable)
    if pending:
        logger.warning(
            "giving up on %d of %d messages after %d attempts (rate limited)",
            len(pending), len(ids), MAX_BATCH_ATTEMPTS,
        )
    return out


def _work_labels(labels: list[dict], cfg: dict) -> list[tuple[str, str, str, dict]]:
    """(category, label_id, label_name, parsed info) for every in-range,
    year-tagged business label."""
    y_start = int(cfg.get("scan_year_start", "2022") or 2022)
    y_end = int(cfg.get("scan_year_end", "2026") or 2026)
    work: list[tuple[str, str, str, dict]] = []
    for cat, (label_key, _type, _default) in CATEGORIES.items():
        prefix = cfg.get(label_key, "")
        if not prefix:
            continue
        for lab in labels:
            name = lab["name"]
            low = name.lower()
            if any(tok in low for tok in EXCLUDE_TOKENS):
                continue
            if not (name == prefix or name.startswith(prefix + "/")):
                continue
            info = parse_label(cat, name, prefix)
            if info["year"] is None or not (y_start <= info["year"] <= y_end):
                continue
            work.append((cat, lab["id"], name, info))
    return work


def _record(mid: str, msg: dict, cat: str, label_name: str, info: dict) -> dict:
    headers = (msg.get("payload") or {}).get("headers", [])
    internal = int(msg.get("internalDate", "0")) / 1000
    date = datetime.fromtimestamp(internal, tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "gmail_msg_id": mid,
        "category": cat,
        "business_name": info["business"],
        "year_label": str(info["year"]) if info["year"] else None,
        "kind": info["kind"],
        "subject": _header(headers, "Subject"),
        "sender": _header(headers, "From"),
        "date": date,
        "snippet": msg.get("snippet", ""),
        "has_attachments": False,  # caller fills in
        "raw_label": label_name,
    }


def _real_scan(session: Session, service=None) -> list[dict]:
    """Full scan: walk every in-range business label and pull its messages."""
    if service is None:
        service = client.build_service()
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    cfg = _settings(session)
    work = _work_labels(labels, cfg)

    # List ids per label first, then fetch all metadata in one batched pass.
    per_label: list[tuple[str, str, dict, list[str], set[str]]] = []
    all_ids: list[str] = []
    seen: set[str] = set()
    for cat, label_id, name, info in work:
        att_ids = set(_list_ids(service, label_id, query="has:attachment"))
        ids = [m for m in _list_ids(service, label_id) if m not in seen]
        seen.update(ids)
        per_label.append((cat, name, info, ids, att_ids))
        all_ids += ids

    msgs = _batch_get(service, all_ids)
    records: list[dict] = []
    for cat, name, info, ids, att_ids in per_label:
        for mid in ids:
            msg = msgs.get(mid)
            if msg is None:
                continue
            rec = _record(mid, msg, cat, name, info)
            rec["has_attachments"] = mid in att_ids
            records.append(rec)
    return records


def payload_has_attachment(payload: dict) -> bool:
    """True when any (nested) MIME part carries a filename."""
    for part in payload.get("parts") or []:
        if part.get("filename"):
            return True
        if payload_has_attachment(part):
            return True
    return False


def _incremental_scan(session: Session, service, start_history_id: str) -> list[dict] | None:
    """Records for messages added or newly labeled since the last scan.

    Returns None when Gmail no longer holds that history (typically after
    ~a week of inactivity) — the caller then falls back to a full scan.
    ``labelAdded`` matters as much as ``messageAdded`` here: dragging an old
    email into a Business label is exactly how documents enter the system.
    """
    from googleapiclient.errors import HttpError

    msg_ids: set[str] = set()
    page = None
    try:
        while True:
            kw = {
                "userId": "me", "startHistoryId": start_history_id,
                "historyTypes": ["messageAdded", "labelAdded"], "maxResults": 500,
            }
            if page:
                kw["pageToken"] = page
            resp = service.users().history().list(**kw).execute()
            for h in resp.get("history", []):
                for item in h.get("messagesAdded", []):
                    msg_ids.add(item["message"]["id"])
                for item in h.get("labelsAdded", []):
                    msg_ids.add(item["message"]["id"])
            page = resp.get("nextPageToken")
            if not page:
                break
    except HttpError as e:
        if getattr(e, "resp", None) is not None and int(e.resp.status) == 404:
            return None  # history window expired — need a full scan
        raise

    if not msg_ids:
        return []

    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    cfg = _settings(session)
    by_label_id = {
        label_id: (cat, name, info)
        for cat, label_id, name, info in _work_labels(labels, cfg)
    }

    # format="full" so the MIME tree tells us about attachments — the
    # incremental set is small (a day or two of email), so this stays cheap.
    records: list[dict] = []
    msgs = _batch_get(service, sorted(msg_ids), fmt="full")
    for mid, msg in msgs.items():
        hit = next(
            (by_label_id[lid] for lid in msg.get("labelIds", []) if lid in by_label_id),
            None,
        )
        if hit is None:
            continue  # not (or no longer) under a business label
        cat, name, info = hit
        rec = _record(mid, msg, cat, name, info)
        rec["has_attachments"] = payload_has_attachment(msg.get("payload") or {})
        records.append(rec)
    return records


# --- discovery + persistence ------------------------------------------------
def _get_or_create_business(session: Session, name: str, btype: str) -> Business:
    biz = (
        session.query(Business)
        .filter(Business.name == name, Business.type == btype)
        .first()
    )
    if biz is None:
        biz = Business(name=name, type=btype, external_key=name)
        session.add(biz)
        session.flush()
    return biz


def _get_or_create_year(session: Session, business_id: int, label: str) -> Year:
    yr = (
        session.query(Year)
        .filter(Year.business_id == business_id, Year.label == label)
        .first()
    )
    if yr is None:
        yr = Year(business_id=business_id, label=label)
        session.add(yr)
        session.flush()
    return yr


def merge_business(session: Session, src_id: int, dst_id: int) -> dict:
    """Fold business ``src_id`` into ``dst_id``: remap emails/documents/years.

    Uses bulk core UPDATEs (not ORM attribute writes) and expires the session
    before deleting the source, so deleting the parent does NOT null out the
    children's foreign keys via the relationship cascade.
    """
    src = session.get(Business, src_id)
    dst = session.get(Business, dst_id)
    if src is None or dst is None:
        raise ValueError("source or destination business not found")
    src_name, dst_name = src.name, dst.name

    def dst_year_id(year_id):
        if not year_id:
            return None
        label = session.get(Year, year_id).label
        return _get_or_create_year(session, dst_id, label).id

    email_updates = [
        (em.id, dst_year_id(em.year_id))
        for em in session.query(Email).filter(Email.business_id == src_id).all()
    ]
    doc_updates = [
        (d.id, dst_year_id(d.year_id))
        for d in session.query(Document).filter(Document.business_id == src_id).all()
    ]
    session.flush()  # persist any newly-created destination years

    for eid, yid in email_updates:
        session.query(Email).filter(Email.id == eid).update(
            {Email.business_id: dst_id, Email.year_id: yid}, synchronize_session=False
        )
    for did, yid in doc_updates:
        session.query(Document).filter(Document.id == did).update(
            {Document.business_id: dst_id, Document.year_id: yid},
            synchronize_session=False,
        )
    session.flush()
    session.expire_all()  # drop stale in-memory rows still pointing at src

    session.query(Year).filter(Year.business_id == src_id).delete(
        synchronize_session=False
    )
    session.delete(session.get(Business, src_id))
    session.commit()
    return {"merged": src_name, "into": dst_name, "emails_moved": len(email_updates)}


def reassign_orphan_emails(session: Session) -> dict:
    """Re-link any emails whose business_id is NULL, re-deriving from raw_label."""
    cfg = _settings(session)
    fixed = 0
    orphans = session.query(Email).filter(Email.business_id.is_(None)).all()
    for em in orphans:
        cat = em.category
        if cat not in CATEGORIES:
            continue
        prefix = cfg.get(CATEGORIES[cat][0], "")
        info = parse_label(cat, em.raw_label, prefix)
        biz = _get_or_create_business(session, info["business"], CATEGORIES[cat][1])
        label = str(info["year"]) if info["year"] else (em.date.split("-")[0] if em.date else "unknown")
        em.business_id = biz.id
        em.year_id = _get_or_create_year(session, biz.id, label).id
        fixed += 1
    session.commit()
    return {"reassigned": fixed}


def run_scan(session: Session, full: bool = False) -> dict:
    """Execute a scan in the current mode and persist results idempotently.

    Real mode is incremental by default: after any scan we remember the
    mailbox's historyId, and the next scan only asks Gmail "what changed
    since then". ``full=True`` (or an expired/missing historyId) walks every
    label like the original scan did.
    """
    m = client.mode()
    incremental = False
    new_history_id = None
    if m == "real" and client.is_connected():
        service = client.build_service()
        # Snapshot the mailbox position BEFORE scanning: anything arriving
        # mid-scan lands after this id and is picked up next time (the
        # gmail_msg_id dedup below makes the overlap harmless).
        try:
            new_history_id = (
                service.users().getProfile(userId="me").execute().get("historyId")
            )
        except Exception:
            logger.exception("Could not read mailbox historyId")

        records = None
        stored = _settings(session).get("gmail_last_history_id", "")
        if not full and stored:
            records = _incremental_scan(session, service, stored)
            if records is None:
                logger.info("Gmail history %s expired — running a full scan", stored)
            else:
                incremental = True
        if records is None:
            records = _real_scan(session, service)
    else:
        # Mock scans invent emails — never let them touch the real books
        # unless debug mode is explicitly on.
        from ...debug import is_debug

        if not is_debug(session):
            return {
                "error": "Gmail is not connected on this machine — connect it "
                         "on the Gmail page. (Mock sample data is available "
                         "only in debug mode.)",
                "mode": "mock", "scanned": 0, "new_emails": 0,
                "existing_emails": 0,
                "total_emails": session.query(Email).count(),
                "businesses": [], "years": [],
            }
        m = "mock"
        records = mock_scan()

    cfg = _settings(session)
    fy_mode = cfg.get("fiscal_year_mode", "calendar")
    fy_end = cfg.get("fiscal_year_end", "12-31")

    new_count = existing_count = 0
    for rec in records:
        cat = rec["category"]
        btype = CATEGORIES[cat][1]
        name = rec.get("business_name") or rec.get("business_hint") or CATEGORIES[cat][2]
        biz = _get_or_create_business(session, name, btype)
        label = rec.get("year_label") or year_label(rec.get("date", ""), fy_mode, fy_end)
        yr = _get_or_create_year(session, biz.id, label)

        existing = (
            session.query(Email).filter(Email.gmail_msg_id == rec["gmail_msg_id"]).first()
        )
        if existing:
            existing_count += 1
            continue
        session.add(Email(
            gmail_msg_id=rec["gmail_msg_id"],
            business_id=biz.id,
            year_id=yr.id,
            category=cat,
            subject=rec.get("subject", ""),
            sender=rec.get("sender", ""),
            date=rec.get("date", ""),
            snippet=rec.get("snippet", ""),
            has_attachments=bool(rec.get("has_attachments")),
            raw_label=rec.get("raw_label", ""),
            kind=rec.get("kind", "other"),
        ))
        new_count += 1

    session.commit()
    if new_history_id:
        _set_setting(session, "gmail_last_history_id", str(new_history_id))

    businesses = session.query(Business).all()
    return {
        "mode": m,
        "incremental": incremental,
        "scanned": len(records),
        "new_emails": new_count,
        "existing_emails": existing_count,
        "total_emails": session.query(Email).count(),
        "businesses": [
            {"id": b.id, "name": b.name, "type": b.type} for b in businesses
        ],
        "years": sorted({y.label for y in session.query(Year).all()}),
    }
