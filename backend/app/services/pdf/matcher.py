"""Match a PDF's text + filename to a discovered business and tax year.

Builds distinctive keyword tokens from each business name (street names like
"lakeside"/"bayview", "spal", "cavell" are highly identifying) and scores the
document against them. Returns a best match with a confidence the UI uses to
decide whether to auto-accept or surface for review.
"""

from __future__ import annotations

import re
from collections import Counter

STREET_SUFFIX = {
    "dr", "drive", "st", "street", "ave", "avenue", "rd", "road", "blvd",
    "cres", "crescent", "lane", "ln", "court", "ct", "way", "place", "pl",
}
GENERIC = {"real", "estate", "home", "office", "rental", "business", "consulting"}

# Keyword → 6x folder bucket (informational suggestion; finalized in Phase 5).
BUCKET_KEYWORDS = [
    ("6b", ("lease", "leasebusters")),
    ("6a", ("lexus", "corolla", "407etr", "caa", "vehicle", "car wash")),
    ("6e", ("mortgage", "amortization", "principal balance")),
    ("6d", ("property tax", "municipal tax", "tax assessment", "assessment notice")),
    ("6h", ("t4 ", "t4a", "t1 ", "t5 ", "t-slip", "notice of assessment")),
    ("6i", ("hydro", "electric", "enbridge", "natural gas", "internet",
            "bell ", "rogers", "cellular", "wireless", "water bill", "utility")),
    ("6c", ("insurance", "policy", "coverage", "premium")),
]


def _tokens(name: str) -> list[tuple[str, int]]:
    """Return (token, weight) for a business name. Distinctive words weigh more."""
    out = []
    for t in re.findall(r"[a-z0-9]+", name.lower()):
        if t in STREET_SUFFIX or len(t) < 2:
            continue
        if t in GENERIC:
            weight = 1
        elif t.isalpha() and len(t) >= 4:
            weight = 3  # distinctive street/business name
        else:
            weight = 2  # numbers like "51", "315"
        out.append((t, weight))
    return out


def suggest_bucket(text_l: str, business_type: str) -> str:
    for bucket, kws in BUCKET_KEYWORDS:
        if any(k in text_l for k in kws):
            # Car insurance belongs in 6a, not the rental insurance bucket 6c.
            if bucket == "6c" and any(c in text_l for c in ("lexus", "corolla", "auto ", "vehicle")):
                return "6a"
            return bucket
    if business_type == "real_estate":
        return "6f"
    if business_type == "rental":
        return "6g"
    return ""


def match_document(text: str, filename: str, businesses: list[dict]) -> dict:
    """businesses: [{id, name, type, years:[...]}]. Returns best-match info."""
    hay = f"{filename}\n{text}".lower()

    best = None
    best_score = 0.0
    best_strong = False
    for biz in businesses:
        score = 0.0
        strong = False
        for tok, weight in _tokens(biz["name"]):
            if re.search(rf"\b{re.escape(tok)}\b", hay):
                score += weight
                if weight >= 3:
                    strong = True
        if score > best_score:
            best, best_score, best_strong = biz, score, strong

    # Year: prefer one that filename/text shows AND the business is known to
    # have. Counter.most_common() breaks count ties by insertion order, which
    # is not deterministic in any meaningful sense here — sort explicitly so
    # ties go to the most recent year instead of whichever happened to appear
    # first in the document text.
    years_found = Counter(re.findall(r"\b(20[0-3]\d)\b", f"{filename} {text}"))
    ranked_years = sorted(years_found.items(), key=lambda kv: (-kv[1], -int(kv[0])))
    year = None
    if best and best.get("years"):
        for y, _ in ranked_years:
            if y in best["years"]:
                year = y
                break
    if year is None and ranked_years:
        year = ranked_years[0][0]

    if not best or best_score == 0:
        return {
            "business_id": None, "business_name": None, "year": year,
            "confidence": "none", "reason": "No business keywords matched.",
            "bucket": "",
        }

    if best_strong and best_score >= 3:
        confidence = "high"
    elif best_strong or best_score >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "business_id": best["id"],
        "business_name": best["name"],
        "year": year,
        "confidence": confidence,
        "reason": f"Matched '{best['name']}' (score {best_score:g})"
                  + (f", year {year}" if year else ", year unresolved"),
        "bucket": suggest_bucket(hay, best["type"]),
    }
