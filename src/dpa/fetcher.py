"""Page fetching: Playwright full-browser render with an httpx/BeautifulSoup fallback."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from dpa.config import settings

_WHITESPACE = re.compile(r"\n\s*\n\s*\n+")


@dataclass
class FetchedPage:
    """A normalised snapshot of a fetched page."""

    url: str
    final_url: str = ""
    title: str | None = None
    text: str = ""
    html: str = ""
    interactive_elements: list[str] = field(default_factory=list)
    screenshot_bytes: bytes | None = None
    screenshot_media_type: str = "image/png"
    fetch_method: str = "httpx"
    notes: list[str] = field(default_factory=list)

    def truncated_text(self, max_chars: int) -> str:
        if len(self.text) <= max_chars:
            return self.text
        return self.text[:max_chars] + "\n…[truncated]…"


# --------------------------------------------------------------------------
# HTML parsing shared by both fetch paths
# --------------------------------------------------------------------------

def _clean_text(raw: str) -> str:
    return _WHITESPACE.sub("\n\n", raw).strip()


def extract_from_html(html: str) -> tuple[str | None, str, list[str]]:
    """Return (title, visible_text, interactive_elements) from raw HTML."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    text = _clean_text(soup.get_text("\n"))

    elements: list[str] = []
    for btn in soup.find_all(["button", "a"]):
        label = btn.get_text(" ", strip=True)
        if label:
            kind = "button" if btn.name == "button" else "link"
            elements.append(f"{kind}: {label[:120]}")

    for inp in soup.find_all("input"):
        itype = (inp.get("type") or "text").lower()
        checked = inp.has_attr("checked")
        name = inp.get("name") or inp.get("id") or ""
        label = inp.get("aria-label") or inp.get("placeholder") or name
        if itype in {"checkbox", "radio"}:
            elements.append(
                f"{itype} ({'CHECKED by default' if checked else 'unchecked'}): {label[:120]}"
            )
        elif itype in {"submit", "button"}:
            elements.append(f"button: {inp.get('value') or label}")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped = [e for e in elements if not (e in seen or seen.add(e))]
    return title, text, deduped


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------

def page_from_html(html: str, url: str = "inline://html") -> FetchedPage:
    """Build a FetchedPage from raw HTML without any network access."""
    title, text, elements = extract_from_html(html)
    return FetchedPage(
        url=url,
        final_url=url,
        title=title,
        text=text,
        html=html,
        interactive_elements=elements,
        fetch_method="inline",
        notes=["Audited from supplied HTML (no network fetch)."],
    )


async def fetch_page(
    url: str,
    *,
    use_browser: bool = True,
    capture_screenshot: bool = True,
    timeout: int | None = None,
) -> FetchedPage:
    """Fetch a page, preferring Playwright; fall back to httpx on any failure."""
    timeout = timeout or settings.dpa_fetch_timeout

    if use_browser:
        try:
            return await _fetch_with_playwright(
                url, capture_screenshot=capture_screenshot, timeout=timeout
            )
        except Exception as exc:  # noqa: BLE001 - we intentionally degrade gracefully
            note = f"Browser render unavailable ({type(exc).__name__}: {exc}); fell back to static fetch."
            page = await _fetch_with_httpx(url, timeout=timeout)
            page.notes.insert(0, note)
            return page

    return await _fetch_with_httpx(url, timeout=timeout)


async def _fetch_with_playwright(
    url: str, *, capture_screenshot: bool, timeout: int
) -> FetchedPage:
    from playwright.async_api import async_playwright  # imported lazily

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1366, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 DarkPatternAuditor/0.1"
                ),
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            # Give late client-side widgets (timers, popups) a moment to appear.
            await page.wait_for_timeout(1200)

            html = await page.content()
            final_url = page.url
            title = await page.title()

            interactive = await page.evaluate(_INTERACTIVE_JS)

            screenshot_bytes = None
            if capture_screenshot:
                screenshot_bytes = await page.screenshot(full_page=True, type="png")

            # Use the parsed visible text for consistency with the static path.
            _, text, parsed_elements = extract_from_html(html)
            elements = interactive or parsed_elements

            return FetchedPage(
                url=url,
                final_url=final_url,
                title=title or None,
                text=text,
                html=html,
                interactive_elements=elements,
                screenshot_bytes=screenshot_bytes,
                fetch_method="playwright",
                notes=["Rendered with a headless Chromium browser."],
            )
        finally:
            await browser.close()


async def _fetch_with_httpx(url: str, *, timeout: int) -> FetchedPage:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 DarkPatternAuditor/0.1"
        )
    }
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=timeout, headers=headers
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    title, text, elements = extract_from_html(html)
    return FetchedPage(
        url=url,
        final_url=str(resp.url),
        title=title,
        text=text,
        html=html,
        interactive_elements=elements,
        fetch_method="httpx",
        notes=["Static fetch (no JavaScript executed)."],
    )


def fetch_page_sync(url: str, **kwargs) -> FetchedPage:
    """Synchronous convenience wrapper around :func:`fetch_page`."""
    return asyncio.run(fetch_page(url, **kwargs))


# JS run inside the rendered page to collect interactive controls and their state.
_INTERACTIVE_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const push = (s) => { if (s && !seen.has(s)) { seen.add(s); out.push(s); } };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const st = window.getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
  };
  document.querySelectorAll('button, a, [role=button]').forEach((el) => {
    if (!visible(el)) return;
    const label = (el.innerText || el.textContent || '').trim();
    if (label) push((el.tagName === 'A' ? 'link: ' : 'button: ') + label.slice(0, 120));
  });
  document.querySelectorAll('input').forEach((el) => {
    const type = (el.type || 'text').toLowerCase();
    const label = (el.getAttribute('aria-label') || el.placeholder || el.name || el.id || '').trim();
    if (type === 'checkbox' || type === 'radio') {
      push(type + ' (' + (el.checked ? 'CHECKED by default' : 'unchecked') + '): ' + label.slice(0, 120));
    } else if (type === 'submit' || type === 'button') {
      push('button: ' + (el.value || label).slice(0, 120));
    }
  });
  return out.slice(0, 150);
}
"""
