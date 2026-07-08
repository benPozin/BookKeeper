"""Heuristic extraction of vendor / date / amount from a document's text.

Pure regex + keyword scoring over the text pdfplumber/OCR produced — no
network, no AI. Deliberately conservative: a blank answer is better than a
confidently wrong dollar figure landing in a tax package. The optional Gemini
review may later overwrite these fields with what it reads.
"""

from __future__ import annotations

import re

# --- amount -------------------------------------------------------------------
# Money like $1,234.56 / 1234.56 (two decimals required when there's no $).
MONEY_RE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)|(?<![\d.])(\d{1,3}(?:,\d{3})*\.\d{2})(?![\d.])")

# Ranked: the earlier the keyword, the more likely its line holds the figure
# that matters. "total" alone is last — it also matches "subtotal" noise.
AMOUNT_KEYWORDS = [
    "amount due", "total due", "balance due", "grand total", "total amount",
    "amount paid", "payment due", "invoice total", "amount owing", "total owing",
    "balance forward", "new charges", "total", "amount", "balance",
]

MAX_PLAUSIBLE = 1_000_000  # bigger figures are account numbers, not bills


def _amounts_on(line: str) -> list[float]:
    out = []
    for m in MONEY_RE.finditer(line):
        raw = (m.group(1) or m.group(2)).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        if 0 < val < MAX_PLAUSIBLE:
            out.append(val)
    return out


def extract_amount(text: str) -> float | None:
    """The document's headline dollar figure, or None."""
    lines = text.splitlines()
    best: tuple[int, float] | None = None  # (keyword rank, amount)
    for line in lines:
        # "subtotal" would otherwise match the "total" keyword and beat the
        # real total (same rank, first line wins) — drop the word entirely.
        low = line.lower().replace("subtotal", "")
        for rank, kw in enumerate(AMOUNT_KEYWORDS):
            if kw in low:
                vals = _amounts_on(line)
                if vals and (best is None or rank < best[0]):
                    best = (rank, max(vals))
                break
    if best:
        return round(best[1], 2)
    # No keyword line — fall back to the largest $-prefixed figure anywhere.
    dollar_vals = []
    for m in re.finditer(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text):
        try:
            val = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 0 < val < MAX_PLAUSIBLE:
            dollar_vals.append(val)
    return round(max(dollar_vals), 2) if dollar_vals else None


# --- date ---------------------------------------------------------------------
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
)}

DATE_PATTERNS = [
    # 2025-03-14 / 2025/03/14
    (re.compile(r"\b(20[0-3]\d)[-/](\d{1,2})[-/](\d{1,2})\b"), "ymd"),
    # 03/14/2025 (NA order; swapped when the first number can't be a month)
    (re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](20[0-3]\d)\b"), "mdy"),
    # March 14, 2025 / Mar 14 2025
    (re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(20[0-3]\d)\b"), "mon_d_y"),
    # 14 March 2025
    (re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(20[0-3]\d)\b"), "d_mon_y"),
]

DATE_KEYWORDS = [
    "statement date", "invoice date", "date issued", "issue date", "billing date",
    "bill date", "receipt date", "transaction date", "payment date", "date of issue",
    "due date", "date",
]


def _parse_date(m: re.Match, kind: str) -> str | None:
    try:
        if kind == "ymd":
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        elif kind == "mdy":
            mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if mo > 12 and d <= 12:  # actually DD/MM/YYYY
                mo, d = d, mo
        elif kind == "mon_d_y":
            mo = MONTHS.get(m.group(1)[:3].lower())
            d, y = int(m.group(2)), int(m.group(3))
        else:  # d_mon_y
            mo = MONTHS.get(m.group(2)[:3].lower())
            d, y = int(m.group(1)), int(m.group(3))
        if not mo or not (1 <= mo <= 12) or not (1 <= d <= 31):
            return None
        return f"{y:04d}-{mo:02d}-{d:02d}"
    except (ValueError, TypeError):
        return None


def _dates_on(line: str) -> list[str]:
    out = []
    for pat, kind in DATE_PATTERNS:
        for m in pat.finditer(line):
            parsed = _parse_date(m, kind)
            if parsed:
                out.append(parsed)
    return out


def extract_date(text: str, filename: str = "") -> str:
    """The document's own date as YYYY-MM-DD, or ''."""
    best: tuple[int, str] | None = None
    for line in text.splitlines():
        low = line.lower()
        for rank, kw in enumerate(DATE_KEYWORDS):
            if kw in low:
                dates = _dates_on(line)
                if dates and (best is None or rank < best[0]):
                    best = (rank, dates[0])
                break
    if best:
        return best[1]
    for hay in (text, filename):
        for line in hay.splitlines():
            dates = _dates_on(line)
            if dates:
                return dates[0]
    return ""


# --- vendor -------------------------------------------------------------------
# token (searched case-insensitively) -> canonical display name
KNOWN_VENDORS = [
    ("enbridge", "Enbridge Gas"),
    ("toronto hydro", "Toronto Hydro"),
    ("hydro one", "Hydro One"),
    ("alectra", "Alectra Utilities"),
    ("rogers", "Rogers"),
    ("bell canada", "Bell Canada"),
    ("bell mobility", "Bell Mobility"),
    ("telus", "Telus"),
    ("fido", "Fido"),
    ("teksavvy", "TekSavvy"),
    ("407 etr", "407 ETR"),
    ("407etr", "407 ETR"),
    ("caa", "CAA"),
    ("leasebusters", "Leasebusters"),
    ("lexus financial", "Lexus Financial Services"),
    ("lexus", "Lexus"),
    ("toyota", "Toyota"),
    ("intact insurance", "Intact Insurance"),
    ("intact", "Intact Insurance"),
    ("aviva", "Aviva"),
    ("wawanesa", "Wawanesa"),
    ("td insurance", "TD Insurance"),
    ("canada revenue agency", "Canada Revenue Agency"),
    ("revenue agency", "Canada Revenue Agency"),
    ("cra", "Canada Revenue Agency"),
    ("city of toronto", "City of Toronto"),
    ("reliance", "Reliance Home Comfort"),
    ("canadian tire", "Canadian Tire"),
    ("home depot", "Home Depot"),
    ("costco", "Costco"),
    ("staples", "Staples"),
    ("amazon", "Amazon"),
]

GENERIC_LINE = re.compile(
    r"^(invoice|receipt|statement|bill|account|tax invoice|official receipt|"
    r"page \d|date|total|amount|balance|customer|attention|attn)\b",
    re.I,
)


def extract_vendor(text: str, filename: str = "") -> str:
    hay = f"{text}\n{filename}".lower()
    for token, canonical in KNOWN_VENDORS:
        if re.search(rf"\b{re.escape(token)}\b", hay):
            return canonical

    # Fall back to the first plausible line at the top of the document — most
    # invoices/receipts open with the issuer's name.
    for line in text.splitlines()[:12]:
        line = line.strip()
        if not (3 <= len(line) <= 60):
            continue
        letters = sum(c.isalpha() for c in line)
        if letters < max(3, len(line) // 3):
            continue
        if GENERIC_LINE.match(line) or _dates_on(line) or _amounts_on(line):
            continue
        # PDFs often merge the issuer line with the next label, e.g.
        # "Anthropic, PBC Bill to" — drop trailing form labels.
        line = re.sub(r"\s*(bill(ed)? to|invoice to|sold to|ship to|attn)\s*:?\s*$",
                      "", line, flags=re.I).strip(" ,·-—")
        if len(line) >= 3:
            return line[:160]
    return ""


def extract_fields(text: str, filename: str = "") -> dict:
    """{'vendor', 'doc_date', 'amount'} — best-effort, blanks where unsure."""
    if not text or not text.strip():
        return {"vendor": "", "doc_date": "", "amount": None}
    return {
        "vendor": extract_vendor(text, filename),
        "doc_date": extract_date(text, filename),
        "amount": extract_amount(text),
    }
