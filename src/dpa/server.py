"""FastAPI backend that powers the web dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dpa import __version__
from dpa.config import settings
from dpa.report import to_html, to_json
from dpa.service import audit_html, audit_url
from dpa.taxonomy import categories

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"

app = FastAPI(
    title="Dark Pattern Auditor",
    version=__version__,
    description="AI-powered detection of deceptive UX (dark patterns) on web pages.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    url: str = Field(..., description="The URL to audit.")
    use_browser: bool = True


class AuditHtmlRequest(BaseModel):
    html: str
    url: str = "inline://html"


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "engine": settings.resolved_engine(),
        "has_api_key": settings.has_api_key,
        "model": settings.dpa_model,
        "vision": settings.dpa_use_vision,
    }


@app.get("/api/taxonomy")
async def taxonomy() -> dict:
    return {
        "categories": [
            {
                "key": c.key,
                "name": c.name,
                "description": c.description,
                "patterns": [
                    {"key": p.key, "name": p.name, "default_severity": p.default_severity}
                    for p in c.patterns
                ],
            }
            for c in categories()
        ]
    }


@app.post("/api/audit")
async def api_audit(req: AuditRequest) -> JSONResponse:
    if not (req.url.startswith("http://") or req.url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    try:
        report = await audit_url(req.url, use_browser=req.use_browser, capture_screenshot=req.use_browser)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Audit failed: {exc}") from exc
    return JSONResponse(json.loads(to_json(report)))


@app.post("/api/audit/html")
async def api_audit_html(req: AuditHtmlRequest) -> JSONResponse:
    report = await audit_html(req.html, url=req.url)
    return JSONResponse(json.loads(to_json(report)))


@app.post("/api/audit/report.html", response_class=HTMLResponse)
async def api_audit_html_report(req: AuditRequest) -> HTMLResponse:
    """Return a shareable, standalone HTML report for a URL."""
    report = await audit_url(req.url, use_browser=req.use_browser, capture_screenshot=req.use_browser)
    return HTMLResponse(to_html(report))


# --- Static dashboard -----------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
