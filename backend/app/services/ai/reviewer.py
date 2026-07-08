"""AI-powered review + categorization of scanned documents (Google Gemini).

Optional and free-tier friendly: with a Gemini API key configured, each
document is classified into the user's actual businesses and folder
categories, returning a tiny overview, business, tax year, category (folder),
income/expense, vendor/date/amount, and confidence. Without a key the app
relies entirely on the local keyword matcher + heuristic field extraction.

The Claude/Anthropic API is intentionally NOT supported in this app
(user decision, 2026-07-05) — do not re-add it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

from sqlalchemy.orm import Session

from ...models import Business, Document, Setting, Year
from ..organizer.builder import BUCKETS  # code -> plain folder name
from ..pdf import core

logger = logging.getLogger(__name__)

# Fail fast rather than hang indefinitely on a stalled network call — a stuck
# request would otherwise block the whole daily automation job.
CLIENT_TIMEOUT_SECONDS = 60

# The Gemini free tier is tiny (observed on this project: 5 requests/minute,
# 20/day for gemini-2.5-flash). Pace below the per-minute cap, and treat the
# two kinds of 429 differently: per-minute → wait and retry; per-day → stop
# the whole run, it will pick up where it left off tomorrow (ai_reviewed flag).
MIN_SECONDS_BETWEEN_CALLS = 13.0
RATE_RETRIES = 2
RATE_RETRY_SLEEP = 40


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "rate limit" in msg.lower()


def _is_daily_quota(e: Exception) -> bool:
    low = str(e).lower()
    return "perday" in low or "per day" in low or "daily" in low

NAME_TO_CODE = {name: code for code, name in BUCKETS.items()}

KEY_ENV_VARS = ["GEMINI_API_KEY", "GOOGLE_API_KEY"]
KEY_SETTING = "gemini_api_key"
DEFAULT_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are a meticulous bookkeeping assistant for a Canadian small-business "
    "owner. You are given one scanned tax document (a receipt, bill, statement, "
    "invoice, or tax slip). Classify it for filing:\n"
    "- Pick the single best-matching business from the provided list, or "
    "'Unknown' if none clearly fits.\n"
    "- Pick the single best folder category from the provided list.\n"
    "- Determine the tax year (4-digit) it belongs to, or 'Unknown'.\n"
    "- Determine whether it represents income or an expense (or 'other').\n"
    "- Extract the vendor/payee name, the document date, and the total dollar "
    "amount when they are visible; use empty string / null when not.\n"
    "- Write a very short overview: one plain sentence, at most 20 words, no "
    "preamble.\n"
    "Base every judgement only on the document content. Be conservative with "
    "confidence: 'high' only when the business and year are unambiguous."
)


def _settings(session: Session) -> dict:
    return {s.key: s.value for s in session.query(Setting).all()}


def get_key(session: Session) -> str:
    """Key from an env var, else the Settings table."""
    for env in KEY_ENV_VARS:
        if os.environ.get(env):
            return os.environ[env]
    return _settings(session).get(KEY_SETTING, "")


def get_model(session: Session) -> str:
    """Explicit ``ai_model`` setting if it is a Gemini model, else the default.

    Guards against a stale non-Gemini model name left in Settings.
    """
    chosen = (_settings(session).get("ai_model") or "").strip()
    if chosen and chosen.lower().startswith("gemini"):
        return chosen
    return DEFAULT_MODEL


def key_source(session: Session) -> str:
    return "env" if any(os.environ.get(e) for e in KEY_ENV_VARS) else "settings"


def is_configured(session: Session) -> bool:
    return bool(get_key(session))


def is_enabled(session: Session) -> bool:
    return _settings(session).get("ai_enabled", "0") == "1" and is_configured(session)


def _businesses(session: Session) -> list[dict]:
    out = []
    for b in session.query(Business).all():
        years = [y[0] for y in session.query(Year.label).filter(Year.business_id == b.id).distinct()]
        out.append({"id": b.id, "name": b.name, "type": b.type, "years": sorted(years)})
    return out


def _context(businesses: list[dict]) -> str:
    biz_lines = "\n".join(
        f"- {b['name']} ({b['type'].replace('_', ' ')}"
        + (f", years {', '.join(b['years'])}" if b['years'] else "") + ")"
        for b in businesses
    ) or "(none discovered yet)"
    cat_lines = "\n".join(f"- {name}" for name in BUCKETS.values())
    return (
        f"Businesses:\n{biz_lines}\n\nFolder categories:\n{cat_lines}\n\n"
        "Classify the document below."
    )


def _json_hint(business_names: list[str]) -> str:
    return (
        "\n\nReturn ONLY a JSON object (no markdown, no prose) with exactly these keys:\n"
        '- "summary": string, one plain sentence, max 20 words\n'
        f'- "business": one of {json.dumps(business_names + ["Unknown"])}\n'
        '- "year": a 4-digit string like "2025", or "Unknown"\n'
        f'- "category": one of {json.dumps(list(BUCKETS.values()) + ["Unknown"])}\n'
        '- "kind": one of ["income", "expense", "other"]\n'
        '- "vendor": the vendor/payee company name, or ""\n'
        '- "doc_date": the document date as "YYYY-MM-DD", or ""\n'
        '- "amount": the total dollar amount as a number, or null\n'
        '- "confidence": one of ["high", "medium", "low"]'
    )


def _make_client(key: str):
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=CLIENT_TIMEOUT_SECONDS * 1000),
    )


def _review_one(client, model: str, text: str, path: Path, businesses: list[dict]) -> dict:
    from google.genai import types

    names = [b["name"] for b in businesses]
    prompt = _context(businesses) + _json_hint(names)
    if text.strip():
        contents = [f"{prompt}\n\nDocument filename: {path.name}\n\n{text[:12000]}"]
    else:
        contents = [
            types.Part.from_bytes(data=path.read_bytes(), mime_type="application/pdf"),
            f"{prompt}\n\nDocument filename: {path.name}",
        ]
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return json.loads(resp.text)


def _summarize(client, model: str, lines: list[str]) -> str:
    from google.genai import types

    resp = client.models.generate_content(
        model=model,
        contents=["Recent documents:\n" + "\n".join(lines[:25])],
        config=types.GenerateContentConfig(
            system_instruction="You summarize a small business owner's recently filed tax documents in 2-3 short sentences. Be concrete and plain. No preamble.",
            temperature=0.2,
        ),
    )
    return (resp.text or "").strip()


def _apply(session: Session, doc: Document, result: dict, businesses: list[dict]) -> None:
    """Map the model's answer back onto the Document row."""
    name_to_id = {b["name"]: b["id"] for b in businesses}
    biz_id = name_to_id.get(result.get("business"))
    bucket = NAME_TO_CODE.get(result.get("category"), "")
    year = result.get("year") if (result.get("year") or "").isdigit() else None

    doc.summary = (result.get("summary") or "").strip()
    doc.confidence = result.get("confidence", "low")
    doc.kind = result.get("kind", "other")
    doc.folder_bucket = bucket or doc.folder_bucket
    doc.ai_reviewed = True
    doc.match_reason = f"AI: {doc.summary}"

    # Extracted fields: the model reads the whole document, so let a concrete
    # answer replace the regex heuristics; keep heuristics when it has none.
    vendor = (result.get("vendor") or "").strip()
    if vendor and vendor.lower() != "unknown":
        doc.vendor = vendor[:160]
    doc_date = (result.get("doc_date") or "").strip()
    if re.fullmatch(r"20\d\d-\d\d-\d\d", doc_date):
        doc.doc_date = doc_date
    if isinstance(result.get("amount"), (int, float)):
        doc.amount = round(float(result["amount"]), 2)

    if biz_id:
        doc.business_id = biz_id
        if year:
            yr = (
                session.query(Year)
                .filter(Year.business_id == biz_id, Year.label == year)
                .first()
            )
            if yr is None:
                yr = Year(business_id=biz_id, label=year)
                session.add(yr)
                session.flush()
            doc.year_id = yr.id
        doc.status = "matched" if doc.confidence == "high" else "needs_review"
    else:
        doc.status = "needs_review"


def review_new(session: Session, limit: int = 50, on_progress=None) -> dict:
    """Review all not-yet-AI-reviewed documents (matched/needs_review/unmatched).

    Commits after each document rather than once at the end, so the job is
    resumable: if the process dies partway through (network hang, forced
    quit, Windows update), only the in-flight document needs redoing next
    time — everything already reviewed is safely persisted and won't be
    re-billed. ``on_progress``, if given, is called as
    ``on_progress(done, total, filename)`` after each document.
    """
    if not is_configured(session):
        return {"error": "No Gemini API key configured.", "reviewed": 0}

    model = get_model(session)
    client = _make_client(get_key(session))
    businesses = _businesses(session)

    docs = (
        session.query(Document)
        .filter(Document.ai_reviewed.is_(False))
        .filter(Document.status.in_(("new", "matched", "needs_review", "unmatched")))
        .limit(limit)
        .all()
    )
    total = len(docs)
    reviewed = errors = 0
    stopped = None
    items = []
    last_call = 0.0
    for i, doc in enumerate(docs):
        if on_progress:
            on_progress(i, total, doc.filename)
        path = Path(doc.original_path)
        if not path.exists():
            continue
        text, _method, _extract_error = core.extract_text(path)

        # Stay under the free tier's requests-per-minute cap.
        wait = MIN_SECONDS_BETWEEN_CALLS - (time.monotonic() - last_call)
        if wait > 0:
            time.sleep(wait)

        try:
            for attempt in range(RATE_RETRIES + 1):
                try:
                    last_call = time.monotonic()
                    result = _review_one(client, model, text, path, businesses)
                    break
                except Exception as e:
                    if (_is_rate_limit(e) and not _is_daily_quota(e)
                            and attempt < RATE_RETRIES):
                        logger.info("Gemini per-minute limit hit — waiting %ss", RATE_RETRY_SLEEP)
                        time.sleep(RATE_RETRY_SLEEP)
                        continue
                    raise
            _apply(session, doc, result, businesses)
            session.commit()
            reviewed += 1
            items.append({"file": doc.filename, "summary": doc.summary,
                          "business": result.get("business"), "category": result.get("category"),
                          "confidence": doc.confidence})
        except Exception as e:
            session.rollback()
            if _is_rate_limit(e) and _is_daily_quota(e):
                # Out of requests for today — nothing left to do but resume
                # tomorrow. Not an error; every reviewed doc is already saved.
                stopped = ("Gemini's free daily quota is used up — "
                           f"{reviewed} reviewed this run; the rest will continue "
                           "on the next run (tomorrow's automation picks up where "
                           "this left off).")
                logger.info("AI review stopped: daily quota exhausted after %d docs", reviewed)
                break
            errors += 1
            logger.exception("AI review failed for %s", doc.filename)
            items.append({"file": doc.filename, "error": str(e)[:200]})
    if on_progress:
        on_progress(total, total, "Done")
    out = {"reviewed": reviewed, "errors": errors, "provider": "gemini", "model": model, "items": items}
    if stopped:
        out["stopped"] = stopped
    return out


def daily_overview(session: Session, days: int = 1) -> dict:
    """A tiny natural-language summary of the most recently reviewed documents."""
    if not is_configured(session):
        return {"error": "No Gemini API key configured."}

    recent = (
        session.query(Document)
        .filter(Document.ai_reviewed.is_(True))
        .order_by(Document.id.desc())
        .limit(25)
        .all()
    )
    if not recent:
        return {"overview": "No reviewed documents yet."}
    lines = [f"- {d.filename}: {d.summary}" for d in recent if d.summary]
    client = _make_client(get_key(session))
    text = _summarize(client, get_model(session), lines)
    return {"overview": text, "count": len(recent)}
