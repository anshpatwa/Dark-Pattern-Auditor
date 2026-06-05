"""Shared fixtures: force the heuristic engine so tests need no API key or network."""

from pathlib import Path

import pytest

from dpa.config import Settings

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def heuristic_settings() -> Settings:
    return Settings(dpa_engine="heuristic", anthropic_api_key="")


@pytest.fixture
def dark_html() -> str:
    return (EXAMPLES / "sample_dark_page.html").read_text(encoding="utf-8")


@pytest.fixture
def clean_html() -> str:
    return (EXAMPLES / "clean_page.html").read_text(encoding="utf-8")
