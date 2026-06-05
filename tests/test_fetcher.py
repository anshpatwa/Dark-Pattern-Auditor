from dpa.fetcher import extract_from_html, page_from_html


def test_extracts_title_and_text(dark_html):
    title, text, elements = extract_from_html(dark_html)
    assert title == "MegaDeals — Checkout"
    assert "Only 2 left in stock" in text
    assert any("button" in e for e in elements)


def test_detects_prechecked_checkbox(dark_html):
    _, _, elements = extract_from_html(dark_html)
    assert any("CHECKED by default" in e for e in elements)


def test_clean_page_checkbox_is_unchecked(clean_html):
    _, _, elements = extract_from_html(clean_html)
    assert any("unchecked" in e for e in elements)
    assert not any("CHECKED by default" in e for e in elements)


def test_page_from_html_has_no_network(dark_html):
    page = page_from_html(dark_html, url="http://demo")
    assert page.fetch_method == "inline"
    assert page.title == "MegaDeals — Checkout"
    assert page.screenshot_bytes is None
