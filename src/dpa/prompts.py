"""System prompt and structured-output tool schema for the Claude engine."""

from __future__ import annotations

from dpa.taxonomy import VALID_CATEGORIES, VALID_PATTERN_KEYS, taxonomy_prompt_block

SYSTEM_PROMPT = f"""You are an expert UX-ethics auditor specialising in "dark patterns" \
(also called deceptive design patterns): interface or copy choices that manipulate users \
into decisions they would not otherwise make.

You will be given the visible text of a web page, its key interactive elements, and \
(when available) a screenshot. Identify concrete, evidence-backed dark patterns.

Use ONLY the following taxonomy. Each finding must map to one `pattern_key` and its \
`category`:

{taxonomy_prompt_block()}

Rules:
- Report a finding only when there is specific evidence on THIS page. Quote the exact text \
or describe the exact element in `evidence`. Never invent content that is not present.
- If the page is clean, return an empty findings list. Do not manufacture issues.
- Assign `severity` based on real user harm (financial > privacy > annoyance), starting \
from the pattern's default severity and adjusting for context.
- `confidence` reflects how certain you are it is genuinely manipulative (0.0-1.0). Use \
lower confidence for borderline persuasion that may be legitimate.
- Be fair: ordinary marketing, genuine discounts and real low-stock notices are NOT dark \
patterns unless they are fabricated, coercive or hidden.
- Write `recommendation` as a concrete, actionable fix.

Return your results by calling the `report_dark_patterns` tool exactly once."""


REPORT_TOOL = {
    "name": "report_dark_patterns",
    "description": "Report the dark patterns found on the audited page, with evidence.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-4 sentence overall assessment of the page's design honesty.",
            },
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pattern_key": {
                            "type": "string",
                            "enum": list(VALID_PATTERN_KEYS),
                            "description": "Taxonomy key for the detected pattern.",
                        },
                        "category": {
                            "type": "string",
                            "enum": list(VALID_CATEGORIES),
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                        },
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "evidence": {
                            "type": "string",
                            "description": "Exact quote or element observed on the page.",
                        },
                        "location": {
                            "type": "string",
                            "description": "Where on the page it appears (optional).",
                        },
                        "recommendation": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "required": [
                        "pattern_key",
                        "category",
                        "severity",
                        "title",
                        "description",
                        "evidence",
                        "recommendation",
                        "confidence",
                    ],
                },
            },
        },
        "required": ["summary", "findings"],
    },
}


def page_text_block(
    *,
    url: str,
    page_title: str | None,
    text: str,
    interactive_elements: list[str],
) -> str:
    """The plain-text description of the page, shared by all AI engines."""
    elements_block = "\n".join(f"- {e}" for e in interactive_elements[:120]) or "(none extracted)"
    return (
        f"URL: {url}\n"
        f"Page title: {page_title or '(unknown)'}\n\n"
        f"=== Interactive elements (buttons, links, form controls) ===\n"
        f"{elements_block}\n\n"
        f"=== Visible page text ===\n"
        f"{text}"
    )


def build_user_content(
    *,
    url: str,
    page_title: str | None,
    text: str,
    interactive_elements: list[str],
    screenshot_b64: str | None,
    screenshot_media_type: str = "image/png",
) -> list[dict]:
    """Assemble the multimodal user message for Claude."""
    text_block = page_text_block(
        url=url, page_title=page_title, text=text, interactive_elements=interactive_elements
    )

    content: list[dict] = []
    if screenshot_b64:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": screenshot_media_type,
                    "data": screenshot_b64,
                },
            }
        )
    content.append({"type": "text", "text": text_block})
    return content
