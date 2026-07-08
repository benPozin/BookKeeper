# BookKeeper

Local web app that prepares a clean, accountant-ready document package across
three businesses (Consulting / SPAL, Rental, Real Estate). It scans Gmail for
business email, reads scanned PDFs from the ScanSnap folder, matches and
de-duplicates documents, fills Excel expense templates, and files everything
into a fixed `6a–6i` folder structure per business and year.

**All 7 phases are built and working:**
1. **Gmail Scan** — OAuth (read-only), walks the `Business/*` label tree, discovers businesses + years, income/expense, searchable history.
2. **Documents / PDF Matching** — reads scanned PDFs, matches each to a business/year with a confidence score, suggests its `6x` bucket, de-duplicates by content hash; low-confidence matches wait for your OK.
3. **New Scan** — phone/desktop upload (images become PDFs) + a live ScanSnap folder watcher that auto-ingests.
4. **Expense Templates** — your 5 real `.xlsx` templates; builds a working copy per year with a "Supporting Docs" sheet of matched evidence (your formulas untouched).
5. **Folder Organizer** — builds the `6a–6i` tree per year, copies matched docs into buckets + places templates; dry-run preview, full audit log.
6. **Daily Automation** — APScheduler daily job (Gmail scan + ingest), run-now, last-run status.
7. **Accountant Export** — zips a year's tree with a manifest, ready to send.

Beyond the original 7 phases, the app now also has: automatic daily database
backups, structured logging + a `/api/diagnostics` health page, a resilient
ScanSnap watcher that auto-starts and survives reboots, a one-doc-at-a-time
**review queue** with inline PDF preview, bulk approve actions, undo, an
"un-file a year" safety valve on the Organizer, live progress bars for scans
and AI review, a real (not sample) activity feed and filed-per-month chart,
a per-year completion checklist, and a QR code for the phone-upload flow. The
UI was redesigned in a warm "ledger" style — cream paper, forest green ink,
gold accents, rubber-stamp statuses.

Added 2026-07-05:
- **Email attachments → Documents.** PDFs and photos attached to matched
  business emails are downloaded automatically (Gmail page button + the daily
  job) and become high-confidence documents — business, year, and
  income/expense come straight from the email's label.
- **Fast, incremental Gmail scans.** Message metadata is fetched in batched,
  rate-limit-aware requests (a full ~1,800-email scan now takes about a
  minute instead of ~8), and after the first scan "Scan now" only asks Gmail
  what changed. "Full rescan" re-walks every label.
- **Vendor / date / amount extraction.** Every ingested document gets a
  best-effort vendor, document date, and headline dollar amount (regex
  heuristics, fully offline). They show on the Documents table, and each
  template's "Supporting Docs (BK)" sheet now lists them with a sanity-check
  subtotal. "Extract amounts" backfills older documents.
- **OCR that works on Windows.** Image-only scans are OCR'd via Tesseract;
  pages are rasterized in-process (pypdfium2), so no extra system tools
  besides the Tesseract binary are needed.
- **Optional PIN.** Set **Settings → App PIN** and everyone on the WiFi must
  enter it (once per device) before seeing anything. Blank = off.
- **AI review is Gemini-only.** The optional AI reviewer uses Google's free
  Gemini tier and now also extracts vendor/date/amount. The Claude/Anthropic
  API is deliberately not supported in this app.
- **In-app Windows setup guide.** The **?** button in the top bar opens the
  step-by-step "Moving to the Windows PC (shimo)" checklist; its Done/To-do
  stamps are live checks against whichever machine the app is running on.
- **Visual export.** The Export page shows the package as a Finder-style file
  tree — every folder and file, what each one is (template / scanned document
  with vendor·date·amount / manifest), and sizes — plus where the zip lands on
  disk. **Reveal in Finder** / **Show zip in Explorer** opens the real folder
  in the OS file manager (macOS `open`, Windows `explorer`).

## Stack
- **Backend:** Python + FastAPI + SQLite (SQLAlchemy)
- **Frontend:** React + Vite
- One process serves the API (`/api/*`) and the built UI. Binds to `0.0.0.0`
  so your phone on the same WiFi can reach it.

## Run it (development)

Two terminals — backend (auto-reload) and the Vite dev server with hot reload.

**Backend**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8765
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api → :8765)
```

Open http://localhost:5173.

## Run it (single URL, production-style)

Build the frontend; the backend then serves it on one port.
```bash
cd frontend && npm install && npm run build
cd ../backend && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8765
```
Open http://localhost:8765. From your phone use `http://<PC-IP>:8765`.

## On the Windows PC (`shimo`) — the real home
- Get the code: install Git for Windows, then
  `git clone https://github.com/benPozin/BookKeeper.git` (private repo).
  Updates later are just `git pull`.
- Copy the `data\` folder from the Mac into the cloned folder — it holds the
  database, Gmail login, and downloaded attachments (deliberately not in git).
- Install Python 3.11+ and Node 20+.
- The default ScanSnap path is preset:
  `C:\Users\shimo\AppData\Roaming\PFU\ScanSnap Home\ScanSnap Home`
  (editable in **Settings**).
- Double-click `scripts\start_bookkeeper.bat` to set up (first run only) and
  launch BookKeeper — it creates the virtual environment, installs
  dependencies, builds the frontend if needed, and opens
  `http://localhost:8765` in your browser. Server output goes to
  `data\logs\server.log`.
- To keep it running automatically at login (and restart it if it ever
  crashes), open PowerShell **as Administrator** and run:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
  ```
  This registers a Task Scheduler entry named `BookKeeper`. Undo with
  `Unregister-ScheduledTask -TaskName BookKeeper`.
- The ScanSnap folder watcher auto-starts with the app (see **New Scan**) — no
  need to click Start watching again after a reboot unless you've explicitly
  stopped it.

## Configuration
All settings live on the **Settings** page and persist to the local SQLite DB
(`data/bookkeeper.db`). Defaults are defined in `backend/app/config.py`.

## Backend tests
```bash
cd backend && source .venv/bin/activate && pytest
```
Covers the matching heuristics, Gmail label parsing, ingest de-duplication,
vendor/date/amount extraction, and Gmail attachment/label helpers.

## Diagnostics
`GET /api/diagnostics` (or just visit `/api/diagnostics` in a browser) reports
whether the watcher is running, paths exist, Gmail/AI are configured, OCR is
installed, the last automation run, recent backups, and a log tail — useful
to screenshot if something looks wrong. Logs live at `data/logs/bookkeeper.log`
and DB backups at `data/backups/`.

## Gmail (Phase 1 — built)

The **Gmail Scan** page scans business email, discovers your businesses and
years, and keeps a searchable history.

- **Mock mode (debug only):** with no credentials present AND **Settings →
  Debug mode = 1**, the app uses built-in sample emails so the whole flow can
  be exercised without a real account. With debug mode off (the default),
  fake data is never created — the page just says "Not connected". The same
  flag gates the "Generate sample data" button on the Documents page.
- **Real mode:** add Google OAuth credentials (below) and the *exact same*
  pipeline scans your real mailbox.

### Connect your real Gmail (one-time)
1. Go to <https://console.cloud.google.com> and create a project.
2. **APIs & Services → Library →** enable the **Gmail API**.
3. **OAuth consent screen:** choose *External*, fill the basics, and add
   `shimon.pozin@gmail.com` as a **Test user**.
4. **Credentials → Create credentials → OAuth client ID →** application type
   **Desktop app**. Download the JSON.
5. Save it as **`data/gmail_credentials.json`** in the project (this exact path
   is shown in the in-app "Show Gmail connection setup" checklist).
6. Restart the app, open **Gmail Scan**, and click **Connect** — a browser
   window opens for Google sign-in/consent. The token is stored in
   `data/gmail_token.json`. Access is **read-only**
   (`gmail.readonly`).

### Label mapping
The three categories map to Gmail labels set on the **Settings** page
(`Business/Consulting`, `Business/Rental`, `Business/Real Estate` by default —
adjust to match your actual labels). For rentals, a sub-label leaf under the
rental label (e.g. `Business/Rental/123 Maple St`) becomes the property's
business, giving you one record per rental.

## Templates (Phase 4) — provided ✓
Your 5 real templates are loaded in `templates/`: `Cars.xlsx`,
`Home Office Expenses FY25.xlsx`, `RealEstateExpenses.xlsx`,
`RealEstateFees.xlsx`, `Rental Expenses FY25.xlsx`. BookKeeper copies them per
year and adds a "Supporting Docs" sheet — it never edits your formulas.

## Notes for running on the real (Windows) host
- In **Settings**, set the **ScanSnap path** back to
  `C:\Users\shimo\AppData\Roaming\PFU\ScanSnap Home\ScanSnap Home`
  (on this dev Mac it was pointed at `data/sample_scans` for testing).
- **OCR**: image-only scans (phone photos) need the Tesseract binary. On
  Windows install it with `winget install UB-Mannheim.TesseractOCR` (or the
  installer from github.com/UB-Mannheim/tesseract) — BookKeeper auto-detects
  the default `C:\Program Files\Tesseract-OCR` location. On macOS:
  `brew install tesseract` (already installed on the dev Mac). PDFs with a
  text layer work without OCR.
- The built package and per-year trees are written under `output/` (gitignored).
  Downloaded email attachments live in `data/email_attachments/`.
- Extra dependencies are in `backend/requirements.txt` (pdfplumber, reportlab,
  openpyxl, APScheduler, watchdog, pytesseract, google-genai).
