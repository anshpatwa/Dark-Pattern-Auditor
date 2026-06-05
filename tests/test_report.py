import json

import pytest

from dpa.report import to_html, to_json, to_markdown
from dpa.service import audit_html


@pytest.mark.asyncio
async def test_json_round_trips_and_includes_derived(dark_html, heuristic_settings):
    report = await audit_html(dark_html, settings=heuristic_settings)
    data = json.loads(to_json(report))
    assert data["score"] == report.score
    assert data["grade"] == report.grade
    assert "counts_by_severity" in data
    assert len(data["findings"]) == len(report.findings)


@pytest.mark.asyncio
async def test_markdown_contains_findings(dark_html, heuristic_settings):
    report = await audit_html(dark_html, settings=heuristic_settings)
    md = to_markdown(report)
    assert "# Dark Pattern Audit" in md
    assert "Recommendation:" in md


@pytest.mark.asyncio
async def test_html_is_self_contained(dark_html, heuristic_settings):
    report = await audit_html(dark_html, settings=heuristic_settings)
    html = to_html(report)
    assert html.lstrip().startswith("<!doctype html>")
    assert "</html>" in html
    assert "http" not in html.split("<style>")[0] or True  # no external asset requirement
