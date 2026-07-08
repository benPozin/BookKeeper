"""Placeholder feature endpoints (Phase 0).

Each feature returns structured "what this will do" content plus any items
needed from the user (e.g. the attached Excel templates). These are wired to
real logic in their respective phases.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/features", tags=["features"])

# Detail shown on each feature page while it is not yet wired.
FEATURE_DETAIL = {
    "gmail": {
        "name": "Gmail Scan",
        "phase": 1,
        "status": "coming_soon",
        "bullets": [
            "Connect shimon.pozin@gmail.com via Google OAuth (installed-app flow).",
            "Scan messages under the Business label and its 3 sub-categories: "
            "Consulting (SPAL), Rental (by address), Real Estate (income/expenses).",
            "Discover businesses and years from email content and dates.",
            "Keep a searchable history of every scanned email per category.",
        ],
        "needs_from_user": [
            "Confirm exact Gmail label / sub-label names.",
            "Google Cloud OAuth credentials.json (guided setup provided).",
        ],
    },
    "documents": {
        "name": "Documents / PDF Matching",
        "phase": 2,
        "status": "coming_soon",
        "bullets": [
            "Read PDFs from the configured ScanSnap folder.",
            "Extract text (OCR fallback) to identify business and year.",
            "Match each document to a discovered business/year.",
            "De-duplicate via content hash; surface unmatched docs for review.",
        ],
        "needs_from_user": [],
    },
    "scan": {
        "name": "New Scan",
        "phase": 3,
        "status": "coming_soon",
        "bullets": [
            "Watch the ScanSnap ix1600 output folder and auto-ingest new PDFs.",
            "Mobile upload page reachable from your phone on the same WiFi.",
            "Phone photos converted to PDF and fed into the same pipeline.",
        ],
        "needs_from_user": [],
    },
    "templates": {
        "name": "Expense Templates",
        "phase": 4,
        "status": "coming_soon",
        "bullets": [
            "Populate Home Office Expenses (6g, Real Estate).",
            "Populate Rental Expenses — one tab per rental business.",
            "Populate Car Expenses (6a), RealEstateExpenses & RealEstateFees (6f).",
        ],
        "needs_from_user": [
            "ATTACHED: Home Office Expenses template (.xlsx).",
            "ATTACHED: Rental Expenses template (.xlsx, one tab per rental).",
            "ATTACHED: Car Expenses template (.xlsx).",
            "ATTACHED: RealEstateExpenses template (.xlsx).",
            "ATTACHED: RealEstateFees template (.xlsx).",
        ],
    },
    "organizer": {
        "name": "Folder Organizer",
        "phase": 5,
        "status": "coming_soon",
        "bullets": [
            "Build the 6a–6i folder structure per business/year.",
            "Route matched documents into the right bucket + Supporting Docs.",
            "Dry-run preview before any files move; full audit log.",
        ],
        "needs_from_user": [],
    },
    "automation": {
        "name": "Daily Automation",
        "phase": 6,
        "status": "coming_soon",
        "bullets": [
            "Scheduled daily Gmail scan + PDF ingest + routing.",
            "Windows Task Scheduler / run-at-login keeps the service up.",
            "Last-run status and errors surfaced on the dashboard.",
        ],
        "needs_from_user": [],
    },
    "export": {
        "name": "Accountant Export",
        "phase": 7,
        "status": "coming_soon",
        "bullets": [
            "Bundle a selected business/year folder tree into a zip.",
            "Include a manifest/checklist of what's present and what's missing.",
            "Ready to send to the accountant at year/fiscal-year end.",
        ],
        "needs_from_user": [],
    },
}

# The accountant-ready output structure the organizer targets (for display).
FOLDER_STRUCTURE = [
    {"code": "6a", "name": "Car Expenses", "note": "Car insurance docs + Car Expenses template"},
    {"code": "6b", "name": "Car Lease", "note": "Latest lease documents per car"},
    {"code": "6c", "name": "Insurance", "note": "All rental business insurance documents"},
    {"code": "6d", "name": "Property Tax", "note": "Property tax documents"},
    {"code": "6e", "name": "Mortgages", "note": "Mortgage documents for the year"},
    {"code": "6f", "name": "Real Estate", "note": "Supporting Docs + RealEstateExpenses.xlsx + RealEstateFees.xlsx"},
    {"code": "6g", "name": "Rental Expenses", "note": "Supporting Docs + Home Office Expenses.xlsx + Rental Expenses.xlsx"},
    {"code": "6h", "name": "T-Forms", "note": "T1, T4, etc."},
    {"code": "6i", "name": "Utilities", "note": "Gas / Hydro / Internet / Cellular"},
]


@router.get("/{feature_id}")
def feature_detail(feature_id: str) -> dict:
    detail = FEATURE_DETAIL.get(feature_id)
    if detail is None:
        return {"error": "unknown feature", "feature_id": feature_id}
    return detail


@router.get("/organizer/folder-structure")
def folder_structure() -> dict:
    return {"structure": FOLDER_STRUCTURE}
