import pytest

from dpa.analyzer import HeuristicEngine, get_engine
from dpa.config import Settings
from dpa.service import audit_html


@pytest.mark.asyncio
async def test_dark_page_flags_multiple_patterns(dark_html, heuristic_settings):
    report = await audit_html(dark_html, url="http://demo", settings=heuristic_settings)
    keys = {f.pattern_key for f in report.findings}

    # The fixture deliberately contains several distinct dark patterns.
    assert "preselection" in keys
    assert "confirmshaming" in keys
    assert "low_stock_message" in keys
    assert len(report.findings) >= 4
    assert report.score < 100
    assert report.grade in {"C", "D", "F"}
    assert report.engine == "heuristic"


@pytest.mark.asyncio
async def test_clean_page_is_mostly_clean(clean_html, heuristic_settings):
    report = await audit_html(clean_html, url="http://demo", settings=heuristic_settings)
    # An honest page should score well and not trip the high-harm rules.
    assert report.score >= 75
    assert "preselection" not in {f.pattern_key for f in report.findings}


@pytest.mark.asyncio
async def test_each_finding_carries_evidence(dark_html, heuristic_settings):
    report = await audit_html(dark_html, settings=heuristic_settings)
    for f in report.findings:
        assert f.evidence.strip()
        assert f.recommendation.strip()
        assert 0.0 <= f.confidence <= 1.0


def test_get_engine_falls_back_to_heuristic_without_key():
    engine = get_engine(Settings(dpa_engine="auto", anthropic_api_key=""))
    assert isinstance(engine, HeuristicEngine)
