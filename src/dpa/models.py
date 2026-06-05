"""Pydantic data models for findings, audit reports and scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from dpa.taxonomy import CATEGORY_META, PATTERNS_BY_KEY, VALID_CATEGORIES


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Penalty applied to the 0-100 trust score for a single finding of each severity.
SEVERITY_PENALTY: dict[Severity, int] = {
    Severity.LOW: 4,
    Severity.MEDIUM: 9,
    Severity.HIGH: 18,
    Severity.CRITICAL: 30,
}

SEVERITY_ORDER: dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


class Finding(BaseModel):
    """A single detected dark pattern."""

    pattern_key: str = Field(description="Taxonomy key, e.g. 'confirmshaming'.")
    category: str = Field(description="One of the seven high-level categories.")
    severity: Severity
    title: str = Field(description="Short human-readable name of the issue.")
    description: str = Field(description="What the pattern is and why it is deceptive here.")
    evidence: str = Field(description="Concrete quote or element observed on the page.")
    location: str | None = Field(
        default=None, description="Where on the page (selector, region or step)."
    )
    recommendation: str = Field(description="How to fix or make the design honest.")
    confidence: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Model confidence that this is a real dark pattern."
    )

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_CATEGORIES:
            # Be lenient: map unknown categories to misdirection rather than failing the audit.
            return "misdirection"
        return v

    @field_validator("pattern_key")
    @classmethod
    def _normalise_key(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_").replace("-", "_")

    @property
    def category_label(self) -> str:
        return self.category.replace("_", " ").title()

    @property
    def category_description(self) -> str:
        return CATEGORY_META.get(self.category, "")


class AuditReport(BaseModel):
    """The full result of auditing one page."""

    url: str
    page_title: str | None = None
    engine: str = Field(description="'claude' or 'heuristic'.")
    model: str | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    screenshot_path: str | None = None
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    # --- Derived scoring --------------------------------------------------
    @property
    def score(self) -> int:
        """A 0-100 'design honesty' score; 100 means no dark patterns detected."""
        penalty = 0.0
        for f in self.findings:
            penalty += SEVERITY_PENALTY[f.severity] * max(f.confidence, 0.5)
        return max(0, round(100 - penalty))

    @property
    def grade(self) -> str:
        s = self.score
        if s >= 90:
            return "A"
        if s >= 75:
            return "B"
        if s >= 60:
            return "C"
        if s >= 40:
            return "D"
        return "F"

    @property
    def risk_level(self) -> str:
        s = self.score
        if s >= 90:
            return "minimal"
        if s >= 75:
            return "low"
        if s >= 60:
            return "moderate"
        if s >= 40:
            return "high"
        return "severe"

    @property
    def counts_by_severity(self) -> dict[str, int]:
        out = {s.value: 0 for s in Severity}
        for f in self.findings:
            out[f.severity.value] += 1
        return out

    @property
    def counts_by_category(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.category] = out.get(f.category, 0) + 1
        return out

    def sorted_findings(self) -> list[Finding]:
        """Findings ordered by severity (worst first), then confidence."""
        return sorted(
            self.findings,
            key=lambda f: (SEVERITY_ORDER[f.severity], f.confidence),
            reverse=True,
        )

    def to_summary_dict(self) -> dict:
        return {
            "url": self.url,
            "engine": self.engine,
            "score": self.score,
            "grade": self.grade,
            "risk_level": self.risk_level,
            "total_findings": len(self.findings),
            "by_severity": self.counts_by_severity,
        }


def known_default_severity(pattern_key: str, fallback: Severity = Severity.MEDIUM) -> Severity:
    """Look up the default severity for a taxonomy key."""
    p = PATTERNS_BY_KEY.get(pattern_key)
    if p is None:
        return fallback
    return Severity(p.default_severity)
