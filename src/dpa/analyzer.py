"""Analysis engines that turn a fetched page into an :class:`AuditReport`.

Two engines share one interface:

* :class:`ClaudeEngine` — sends page text + screenshot to Claude and parses a
  structured tool call. Requires an ``ANTHROPIC_API_KEY``.
* :class:`HeuristicEngine` — a deterministic, dependency-free rule scanner. It needs
  no API key, so the project runs and demos offline, and it doubles as a fast
  pre-filter / ground-truth fixture for tests.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass

from pydantic import BaseModel

from dpa.config import Settings
from dpa.config import settings as default_settings
from dpa.fetcher import FetchedPage
from dpa.models import AuditReport, Finding, Severity, known_default_severity
from dpa.prompts import REPORT_TOOL, SYSTEM_PROMPT, build_user_content, page_text_block


class AnalysisError(RuntimeError):
    """Raised when an engine cannot produce a report."""


# ==========================================================================
# Heuristic engine
# ==========================================================================

@dataclass
class _Rule:
    pattern_key: str
    category: str
    pattern: re.Pattern[str]
    title: str
    description: str
    recommendation: str
    confidence: float = 0.6
    severity: Severity | None = None  # None -> taxonomy default


def _rx(*words: str) -> re.Pattern[str]:
    return re.compile("|".join(words), re.IGNORECASE)


_RULES: list[_Rule] = [
    _Rule(
        "countdown_timer", "urgency",
        _rx(r"\b\d{1,2}:\d{2}(:\d{2})?\b.{0,40}(left|remain|ends|expires)",
            r"(offer|deal|sale)\s+ends\s+in", r"countdown", r"hurry[,!]"),
        "Possible fake urgency / countdown timer",
        "The page uses a countdown or 'hurry' messaging that pressures an immediate decision.",
        "Remove artificial countdowns, or only show a timer tied to a real, verifiable deadline.",
        0.6,
    ),
    _Rule(
        "limited_time_message", "urgency",
        _rx(r"today only", r"limited[- ]time", r"last chance", r"ends tonight",
            r"while supplies last", r"act now", r"don'?t miss out", r"hurry up"),
        "Limited-time urgency messaging",
        "Deadline language is used to rush the user without a stated, verifiable expiry.",
        "Only assert deadlines that are real; state the exact end date/time.",
        0.55,
    ),
    _Rule(
        "confirmshaming", "misdirection",
        _rx(r"no,? (thanks|i)\b.{0,60}(save|money|discount|deal|don'?t|prefer|full price)",
            r"i don'?t (want|like) to save", r"no,? i (hate|don'?t)"),
        "Confirmshaming opt-out",
        "The decline option is worded to guilt or shame the user for opting out.",
        "Use neutral opt-out copy such as 'No thanks' without judgement.",
        0.7,
    ),
    _Rule(
        "low_stock_message", "scarcity",
        _rx(r"only\s+\d+\s+(left|remaining|in stock)", r"almost (gone|sold out)",
            r"selling fast", r"low (in )?stock", r"only a few left"),
        "Low-stock scarcity message",
        "A claim of limited inventory is used to pressure the purchase.",
        "Show real-time stock only when accurate; avoid static 'only N left' claims.",
        0.5,
    ),
    _Rule(
        "high_demand_message", "scarcity",
        _rx(r"\d+\s+people\s+are\s+(viewing|looking)", r"in high demand",
            r"\d+\s+others?\s+(are )?looking", r"popular right now"),
        "High-demand social pressure",
        "An unverifiable 'others are viewing' claim implies the item may sell out.",
        "Remove fabricated viewer counts or back them with real, auditable data.",
        0.5,
    ),
    _Rule(
        "fake_activity", "social_proof",
        _rx(r"just (bought|purchased|ordered|signed up)",
            r"someone (in|from)\s+\w+.{0,30}(bought|purchased)",
            r"\d+\s+(minutes?|seconds?)\s+ago.{0,30}(bought|purchased)"),
        "Activity-notification social proof",
        "Pop-ups claim recent purchases by others that cannot be verified.",
        "Only show real, consented activity; clearly label illustrative examples.",
        0.55,
    ),
    _Rule(
        "forced_enrollment", "forced_action",
        _rx(r"sign\s*up to (continue|view|read|see)", r"create an account to (continue|view|read)",
            r"register to (continue|view|read|unlock)", r"log in to continue"),
        "Forced account creation",
        "Completing the task is gated behind mandatory sign-up.",
        "Allow guest completion, or clearly justify why an account is required.",
        0.55,
    ),
    _Rule(
        "hidden_subscription", "sneaking",
        _rx(r"free trial.{0,80}(auto|automatically|then|after).{0,40}(renew|charged|billed)",
            r"automatically renews?", r"will be billed", r"cancel anytime.{0,40}billed"),
        "Possible hidden / auto-renewing subscription",
        "A trial or purchase appears to convert into recurring charges.",
        "Disclose the recurring price, billing date and cancellation steps up front.",
        0.55,
    ),
    _Rule(
        "hard_to_cancel", "obstruction",
        _rx(r"call (us )?to cancel", r"to cancel,? (please )?(call|contact|phone)",
            r"cancel by phone", r"cannot be cancelled online"),
        "Hard-to-cancel flow",
        "Cancellation requires friction (a call/email) that sign-up did not.",
        "Offer one-click online cancellation matching the ease of sign-up.",
        0.65,
    ),
    _Rule(
        "obstruction_nagging", "obstruction",
        _rx(r"(enable|allow|turn on)\s+notifications", r"add to home screen",
            r"subscribe to (our )?newsletter"),
        "Repeated nagging prompts",
        "Interruptive prompts repeatedly push an unrelated action.",
        "Ask once, remember the user's choice, and provide an easy permanent dismiss.",
        0.4,
    ),
    _Rule(
        "trick_wording", "misdirection",
        _rx(r"do not .{0,20}not", r"uncheck .{0,30}(if you don'?t|to not)",
            r"opt out to (continue|receive)"),
        "Confusing trick wording",
        "Double negatives or inverted logic obscure what the choice actually does.",
        "Phrase consent in plain, single-negative language with the safe default off.",
        0.5,
    ),
]


def _evidence_snippet(text: str, match: re.Match[str], width: int = 90) -> str:
    start = max(0, match.start() - width)
    end = min(len(text), match.end() + width)
    snippet = text[start:end].replace("\n", " ").strip()
    return f"…{snippet}…" if start > 0 or end < len(text) else snippet


class HeuristicEngine:
    """Rule-based detector. No API key required."""

    name = "heuristic"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or default_settings

    async def analyze(self, page: FetchedPage) -> AuditReport:
        haystack = page.text + "\n" + "\n".join(page.interactive_elements)
        findings: list[Finding] = []
        seen_keys: set[str] = set()

        for rule in _RULES:
            m = rule.pattern.search(haystack)
            if not m or rule.pattern_key in seen_keys:
                continue
            seen_keys.add(rule.pattern_key)
            sev = rule.severity or known_default_severity(rule.pattern_key)
            findings.append(
                Finding(
                    pattern_key=rule.pattern_key,
                    category=rule.category,
                    severity=sev,
                    title=rule.title,
                    description=rule.description,
                    evidence=_evidence_snippet(haystack, m),
                    recommendation=rule.recommendation,
                    confidence=rule.confidence,
                )
            )

        # Pre-checked opt-in boxes -> preselection (separate scan over elements).
        for el in page.interactive_elements:
            if "CHECKED by default" in el and "preselection" not in seen_keys:
                seen_keys.add("preselection")
                findings.append(
                    Finding(
                        pattern_key="preselection",
                        category="forced_action",
                        severity=Severity.HIGH,
                        title="Pre-checked opt-in",
                        description="A consent or add-on box is checked by default, opting the user in without an explicit choice.",
                        evidence=el,
                        location="form control",
                        recommendation="Leave consent and paid add-on boxes unchecked by default (opt-in, not opt-out).",
                        confidence=0.7,
                    )
                )
                break

        summary = self._summary(findings)
        report = AuditReport(
            url=page.final_url or page.url,
            page_title=page.title,
            engine=self.name,
            model=None,
            summary=summary,
            findings=findings,
            notes=[*page.notes, "Heuristic engine: pattern-matching rules, no AI key used."],
        )
        return report

    @staticmethod
    def _summary(findings: list[Finding]) -> str:
        if not findings:
            return "No dark patterns detected by the heuristic rules. The page appears clean on the signals checked."
        cats = sorted({f.category_label for f in findings})
        return (
            f"Heuristic scan flagged {len(findings)} potential dark pattern(s) "
            f"across: {', '.join(cats)}. Review the evidence below; an AI audit "
            f"(with an API key) will catch subtler, context-dependent cases."
        )


# ==========================================================================
# Claude engine
# ==========================================================================

class ClaudeEngine:
    """AI engine backed by Anthropic Claude with structured tool output + vision."""

    name = "claude"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or default_settings
        if not self.settings.has_api_key:
            raise AnalysisError("ANTHROPIC_API_KEY is not set; cannot use the Claude engine.")

    async def analyze(self, page: FetchedPage) -> AuditReport:
        from anthropic import AsyncAnthropic  # imported lazily so offline mode needs no SDK

        screenshot_b64 = None
        if self.settings.dpa_use_vision and page.screenshot_bytes:
            screenshot_b64 = base64.b64encode(page.screenshot_bytes).decode("ascii")

        content = build_user_content(
            url=page.final_url or page.url,
            page_title=page.title,
            text=page.truncated_text(self.settings.dpa_max_text_chars),
            interactive_elements=page.interactive_elements,
            screenshot_b64=screenshot_b64,
            screenshot_media_type=page.screenshot_media_type,
        )

        client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        try:
            resp = await client.messages.create(
                model=self.settings.dpa_model,
                max_tokens=3000,
                # Cache the large taxonomy system prompt across audits to cut cost/latency.
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=[REPORT_TOOL],
                tool_choice={"type": "tool", "name": "report_dark_patterns"},
                messages=[{"role": "user", "content": content}],
            )
        except Exception as exc:  # noqa: BLE001
            raise AnalysisError(f"Claude request failed: {exc}") from exc

        payload = self._extract_tool_payload(resp)
        findings = self._parse_findings(payload.get("findings", []))

        notes = [*page.notes, f"AI engine: Claude ({self.settings.dpa_model})."]
        if screenshot_b64:
            notes.append("Screenshot included for vision analysis.")

        return AuditReport(
            url=page.final_url or page.url,
            page_title=page.title,
            engine=self.name,
            model=self.settings.dpa_model,
            summary=payload.get("summary", "").strip(),
            findings=findings,
            notes=notes,
        )

    @staticmethod
    def _extract_tool_payload(resp) -> dict:
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "report_dark_patterns":
                return dict(block.input)
        raise AnalysisError("Claude did not return a structured tool call.")

    @staticmethod
    def _parse_findings(raw: list[dict]) -> list[Finding]:
        findings: list[Finding] = []
        for item in raw:
            try:
                findings.append(Finding(**item))
            except Exception:  # noqa: BLE001 - skip malformed items, keep the rest
                continue
        return findings


# ==========================================================================
# Gemini engine (free alternative)
# ==========================================================================

class _GFinding(BaseModel):
    """Flat schema handed to Gemini for structured output (mapped to Finding after)."""

    pattern_key: str
    category: str
    severity: str
    title: str
    description: str
    evidence: str
    recommendation: str
    confidence: float
    location: str = ""


class _GResult(BaseModel):
    summary: str
    findings: list[_GFinding] = []


class GeminiEngine:
    """AI engine backed by Google Gemini (free tier) with structured output + vision."""

    name = "gemini"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or default_settings
        if not self.settings.has_gemini_key:
            raise AnalysisError("GEMINI_API_KEY is not set; cannot use the Gemini engine.")

    async def analyze(self, page: FetchedPage) -> AuditReport:
        from google import genai  # imported lazily so offline mode needs no SDK
        from google.genai import types

        text_block = page_text_block(
            url=page.final_url or page.url,
            page_title=page.title,
            text=page.truncated_text(self.settings.dpa_max_text_chars),
            interactive_elements=page.interactive_elements,
        )

        parts: list = []
        used_vision = False
        if self.settings.dpa_use_vision and page.screenshot_bytes:
            parts.append(
                types.Part.from_bytes(
                    data=page.screenshot_bytes, mime_type=page.screenshot_media_type
                )
            )
            used_vision = True
        parts.append(types.Part.from_text(text=text_block))

        client = genai.Client(api_key=self.settings.gemini_api_key)
        try:
            resp = await client.aio.models.generate_content(
                model=self.settings.gemini_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=_GResult,
                    temperature=0.2,
                    max_output_tokens=3000,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise AnalysisError(f"Gemini request failed: {exc}") from exc

        payload = self._extract_payload(resp)
        findings = self._parse_findings(payload.get("findings", []))

        notes = [*page.notes, f"AI engine: Google Gemini ({self.settings.gemini_model})."]
        if used_vision:
            notes.append("Screenshot included for vision analysis.")

        return AuditReport(
            url=page.final_url or page.url,
            page_title=page.title,
            engine=self.name,
            model=self.settings.gemini_model,
            summary=str(payload.get("summary", "")).strip(),
            findings=findings,
            notes=notes,
        )

    @staticmethod
    def _extract_payload(resp) -> dict:
        raw = getattr(resp, "text", None)
        if not raw:
            raise AnalysisError("Gemini returned an empty response.")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Gemini did not return valid JSON: {exc}") from exc

    @staticmethod
    def _parse_findings(raw: list[dict]) -> list[Finding]:
        findings: list[Finding] = []
        for item in raw:
            try:
                data = dict(item)
                data["location"] = data.get("location") or None
                findings.append(Finding(**data))
            except Exception:  # noqa: BLE001 - skip malformed items, keep the rest
                continue
        return findings


# ==========================================================================
# Factory
# ==========================================================================

def get_engine(settings: Settings | None = None):
    """Return the configured engine instance, honouring ``DPA_ENGINE``."""
    settings = settings or default_settings
    choice = settings.resolved_engine()
    if choice == "claude":
        return ClaudeEngine(settings)
    if choice == "gemini":
        return GeminiEngine(settings)
    return HeuristicEngine(settings)
