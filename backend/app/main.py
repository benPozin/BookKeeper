"""BookKeeper FastAPI application entrypoint.

Serves the JSON API under /api and the built React frontend (frontend/dist)
for everything else. Binds to 0.0.0.0 so a phone on the same WiFi can reach it.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import (
    ai, auth, automation, dashboard, diagnostics, documents, export, features,
    gmail, jobs, organizer, scan, settings, templates,
)
from .config import FRONTEND_DIST
from .db import init_db, SessionLocal
from .logging_setup import setup_logging

app = FastAPI(title="BookKeeper", version="0.1.0")


# --- Optional PIN gate ---------------------------------------------------------
# Guards every /api route except auth (the login itself) and health. Static
# files and the SPA shell stay open — the UI must load to show the PIN screen;
# all data flows through /api. The token also rides a query param because
# file links and the PDF-preview iframe can't set headers.
@app.middleware("http")
async def _pin_gate(request, call_next):
    import hmac as _hmac

    path = request.url.path
    if path.startswith("/api") and not path.startswith("/api/auth") and path != "/api/health":
        db = SessionLocal()
        try:
            expected = auth.expected_token(db)
        finally:
            db.close()
        if expected is not None:
            supplied = (
                request.headers.get("x-bk-auth")
                or request.query_params.get("auth")
                or ""
            )
            if not _hmac.compare_digest(supplied, expected):
                return JSONResponse({"detail": "PIN required"}, status_code=401)
    return await call_next(request)

# Allow the Vite dev server (localhost:5173) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    setup_logging()
    init_db()
    from .scheduler import init_from_settings
    init_from_settings()
    from .services.ingest import watch as _watch
    _watch.autostart_if_enabled()


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(diagnostics.router)
app.include_router(documents.router)
app.include_router(features.router)
app.include_router(ai.router)
app.include_router(automation.router)
app.include_router(export.router)
app.include_router(gmail.router)
app.include_router(jobs.router)
app.include_router(organizer.router)
app.include_router(scan.router)
app.include_router(settings.router)
app.include_router(templates.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": "BookKeeper", "phase": 0}


# --- Static frontend ---------------------------------------------------------
# If the frontend has been built, serve it. The catch-all returns index.html so
# client-side routing works. During development you can instead run the Vite dev
# server and hit the API cross-origin (CORS above).
if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"error": "not found"}, status_code=404)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"error": "frontend not built"}, status_code=404)

else:
    @app.get("/")
    def no_frontend() -> dict:
        return {
            "status": "ok",
            "note": "Frontend not built yet. Run `npm run build` in frontend/, "
                    "or use the Vite dev server at http://localhost:5173.",
        }
