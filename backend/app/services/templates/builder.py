"""Build working copies of the user's real Excel templates for a given year.

The templates contain the user's own formulas and structure, so we DO NOT edit
their sheets. Instead each working copy gets one extra sheet —
"Supporting Docs (BK)" — listing the matched documents BookKeeper found for that
template's category and year, giving the accountant the template plus its
evidence trail in one file.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from ...config import TEMPLATES_DIR
from ...models import Business, Document, Year

# Registry: maps each real template to its folder bucket and which documents
# count as its supporting evidence (by business type and/or folder bucket).
TEMPLATES = [
    {"key": "cars", "file": "Cars.xlsx", "label": "Car Expenses",
     "bucket": "6a", "types": [], "buckets": ["6a", "6b"]},
    {"key": "home_office", "file": "Home Office Expenses FY25.xlsx",
     "label": "Home Office Expenses", "bucket": "6g", "types": ["home_office"], "buckets": []},
    {"key": "rental", "file": "Rental Expenses FY25.xlsx", "label": "Rental Expenses",
     "bucket": "6g", "types": ["rental"], "buckets": []},
    {"key": "re_expenses", "file": "RealEstateExpenses.xlsx", "label": "Real Estate Expenses",
     "bucket": "6f", "types": ["real_estate"], "buckets": []},
    {"key": "re_fees", "file": "RealEstateFees.xlsx", "label": "Real Estate Fees",
     "bucket": "6f", "types": ["real_estate"], "buckets": []},
]

SUPPORTING_SHEET = "Supporting Docs (BK)"


def list_templates() -> list[dict]:
    """Templates with availability + sheet/structure info for the UI."""
    out = []
    for t in TEMPLATES:
        path = TEMPLATES_DIR / t["file"]
        info = {**t, "available": path.exists(), "sheets": []}
        if path.exists():
            try:
                import openpyxl

                wb = openpyxl.load_workbook(path, read_only=True)
                info["sheets"] = wb.sheetnames
                wb.close()
            except Exception:
                pass
        out.append(info)
    return out


def _matching_docs(session: Session, tmpl: dict, year: str) -> list[Document]:
    q = (
        session.query(Document)
        .join(Year, Document.year_id == Year.id, isouter=True)
        .filter(Year.label == year)
        .filter(Document.status.in_(("matched", "filed")))
    )
    docs = q.all()
    out = []
    for d in docs:
        biz = session.get(Business, d.business_id) if d.business_id else None
        type_ok = tmpl["types"] and biz and biz.type in tmpl["types"]
        bucket_ok = tmpl["buckets"] and d.folder_bucket in tmpl["buckets"]
        if type_ok or bucket_ok:
            out.append(d)
    return out


def build_for_year(session: Session, year: str, out_dir: str | Path) -> dict:
    """Copy every available template for `year`, appending its supporting docs."""
    import openpyxl

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []

    for tmpl in TEMPLATES:
        src = TEMPLATES_DIR / tmpl["file"]
        if not src.exists():
            manifest.append({"template": tmpl["label"], "status": "missing_template"})
            continue

        dest = out / f"{tmpl['file'].replace('.xlsx', '')} - {year}.xlsx"
        shutil.copy(src, dest)

        docs = _matching_docs(session, tmpl, year)
        wb = openpyxl.load_workbook(dest)
        if SUPPORTING_SHEET in wb.sheetnames:
            del wb[SUPPORTING_SHEET]
        ws = wb.create_sheet(SUPPORTING_SHEET)
        ws.append(["BookKeeper supporting documents", f"Year {year}", tmpl["label"]])
        ws.append([])
        ws.append(["File", "Business", "Vendor", "Date", "Amount", "Bucket",
                   "Source", "Confidence"])
        total = 0.0
        with_amount = 0
        for d in docs:
            biz = session.get(Business, d.business_id) if d.business_id else None
            ws.append([d.filename, biz.name if biz else "", d.vendor, d.doc_date,
                       d.amount, d.folder_bucket, d.source, d.confidence])
            ws.cell(row=ws.max_row, column=5).number_format = "#,##0.00"
            if d.amount:
                total += d.amount
                with_amount += 1
        if docs:
            ws.append([])
            # A sanity-check subtotal, not a filing figure: extracted amounts
            # are best-effort and some documents may not have one at all.
            ws.append(["", "", "",
                       f"Extracted total ({with_amount} of {len(docs)} docs)",
                       round(total, 2)])
            ws.cell(row=ws.max_row, column=5).number_format = "#,##0.00"
        wb.save(dest)
        wb.close()

        manifest.append({
            "template": tmpl["label"], "file": dest.name, "bucket": tmpl["bucket"],
            "supporting_docs": len(docs), "status": "built",
        })

    return {"year": year, "out_dir": str(out), "templates": manifest}
