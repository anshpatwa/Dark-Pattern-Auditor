"""High-level orchestration: fetch a page, run an engine, return a report."""

from __future__ import annotations

from pathlib import Path

from dpa.analyzer import get_engine
from dpa.config import Settings
from dpa.config import settings as default_settings
from dpa.fetcher import FetchedPage, fetch_page, page_from_html
from dpa.models import AuditReport


async def audit_url(
    url: str,
    *,
    settings: Settings | None = None,
    use_browser: bool = True,
    capture_screenshot: bool = True,
    screenshot_dir: str | Path | None = None,
) -> AuditReport:
    """Fetch ``url`` and audit it with the configured engine."""
    settings = settings or default_settings
    page = await fetch_page(
        url,
        use_browser=use_browser,
        capture_screenshot=capture_screenshot,
        timeout=settings.dpa_fetch_timeout,
    )
    report = await _analyze(page, settings)

    if screenshot_dir and page.screenshot_bytes:
        report.screenshot_path = _save_screenshot(page, screenshot_dir)
    return report


async def audit_html(
    html: str,
    *,
    url: str = "inline://html",
    settings: Settings | None = None,
) -> AuditReport:
    """Audit raw HTML without any network access (handy for tests and offline use)."""
    settings = settings or default_settings
    page = page_from_html(html, url=url)
    return await _analyze(page, settings)


async def _analyze(page: FetchedPage, settings: Settings) -> AuditReport:
    engine = get_engine(settings)
    return await engine.analyze(page)


def _save_screenshot(page: FetchedPage, screenshot_dir: str | Path) -> str:
    directory = Path(screenshot_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in (page.title or "page"))[:40] or "page"
    path = directory / f"{safe}.png"
    path.write_bytes(page.screenshot_bytes or b"")
    return str(path)
