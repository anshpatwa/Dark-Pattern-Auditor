"""Render an :class:`AuditReport` to JSON, Markdown or a standalone HTML file."""

from __future__ import annotations

import json

from dpa.models import AuditReport, Finding

_SEVERITY_EMOJI = {"low": "🟡", "medium": "🟠", "high": "🔴", "critical": "⛔"}


def to_json(report: AuditReport, *, indent: int = 2) -> str:
    data = report.model_dump(mode="json")
    data["score"] = report.score
    data["grade"] = report.grade
    data["risk_level"] = report.risk_level
    data["counts_by_severity"] = report.counts_by_severity
    data["counts_by_category"] = report.counts_by_category
    return json.dumps(data, indent=indent, default=str)


def to_markdown(report: AuditReport) -> str:
    lines: list[str] = []
    lines.append(f"# Dark Pattern Audit — {report.page_title or report.url}")
    lines.append("")
    lines.append(f"**URL:** {report.url}  ")
    lines.append(f"**Engine:** {report.engine}{f' ({report.model})' if report.model else ''}  ")
    lines.append(f"**Score:** {report.score}/100 (Grade {report.grade}, {report.risk_level} risk)  ")
    lines.append(f"**Findings:** {len(report.findings)}")
    lines.append("")
    if report.summary:
        lines.append("## Summary")
        lines.append("")
        lines.append(report.summary)
        lines.append("")

    if not report.findings:
        lines.append("✅ No dark patterns were detected.")
        return "\n".join(lines)

    lines.append("## Findings")
    lines.append("")
    for i, f in enumerate(report.sorted_findings(), start=1):
        emoji = _SEVERITY_EMOJI.get(f.severity.value, "•")
        lines.append(f"### {i}. {emoji} {f.title} — {f.severity.value.upper()}")
        lines.append("")
        lines.append(f"- **Category:** {f.category_label}")
        lines.append(f"- **Pattern:** `{f.pattern_key}`")
        lines.append(f"- **Confidence:** {f.confidence:.0%}")
        if f.location:
            lines.append(f"- **Location:** {f.location}")
        lines.append("")
        lines.append(f"{f.description}")
        lines.append("")
        lines.append(f"> **Evidence:** {f.evidence}")
        lines.append("")
        lines.append(f"**Recommendation:** {f.recommendation}")
        lines.append("")
    return "\n".join(lines)


def _finding_card_html(f: Finding) -> str:
    import html as _html

    return f"""
      <div class="finding sev-{f.severity.value}">
        <div class="finding-head">
          <span class="sev-badge">{f.severity.value.upper()}</span>
          <h3>{_html.escape(f.title)}</h3>
          <span class="confidence">{f.confidence:.0%} confidence</span>
        </div>
        <div class="finding-meta">{_html.escape(f.category_label)} · <code>{_html.escape(f.pattern_key)}</code></div>
        <p>{_html.escape(f.description)}</p>
        <blockquote>{_html.escape(f.evidence)}</blockquote>
        <p class="rec"><strong>Fix:</strong> {_html.escape(f.recommendation)}</p>
      </div>"""


def to_html(report: AuditReport) -> str:
    """A self-contained, shareable HTML report (no external assets)."""
    import html as _html

    cards = "\n".join(_finding_card_html(f) for f in report.sorted_findings())
    if not report.findings:
        cards = '<p class="clean">✅ No dark patterns were detected on this page.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dark Pattern Audit — {_html.escape(report.page_title or report.url)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #0f1117; color: #e6e8ee; }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 32px 20px 64px; }}
  header h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  .url {{ color: #8a90a2; word-break: break-all; }}
  .scorecard {{ display:flex; gap:24px; align-items:center; background:#181b24; border:1px solid #262a36; border-radius:14px; padding:20px; margin:24px 0; }}
  .grade {{ font-size:3rem; font-weight:800; width:84px; height:84px; display:grid; place-items:center; border-radius:50%; }}
  .grade.A {{ background:#10331f; color:#3ddc84; }} .grade.B {{ background:#13331a; color:#8fe34a; }}
  .grade.C {{ background:#3a3413; color:#f2d24a; }} .grade.D {{ background:#3a2413; color:#f59e42; }}
  .grade.F {{ background:#3a1313; color:#ff6b6b; }}
  .score-meta b {{ font-size:1.3rem; }}
  .summary {{ background:#181b24; border-left:3px solid #4b7bec; padding:14px 18px; border-radius:8px; margin:18px 0; }}
  .finding {{ background:#181b24; border:1px solid #262a36; border-left-width:4px; border-radius:12px; padding:16px 18px; margin:14px 0; }}
  .finding.sev-low {{ border-left-color:#f2d24a; }} .finding.sev-medium {{ border-left-color:#f59e42; }}
  .finding.sev-high {{ border-left-color:#ff6b6b; }} .finding.sev-critical {{ border-left-color:#d6336c; }}
  .finding-head {{ display:flex; align-items:center; gap:10px; }}
  .finding-head h3 {{ margin:0; font-size:1.05rem; flex:1; }}
  .sev-badge {{ font-size:.7rem; font-weight:700; padding:2px 8px; border-radius:999px; background:#262a36; }}
  .confidence {{ font-size:.75rem; color:#8a90a2; }}
  .finding-meta {{ color:#8a90a2; font-size:.8rem; margin:4px 0 8px; }}
  blockquote {{ margin:10px 0; padding:8px 12px; background:#11141c; border-radius:8px; color:#c9cdd8; font-style:italic; }}
  .rec {{ color:#9fb4d8; }}
  code {{ background:#11141c; padding:1px 6px; border-radius:5px; }}
  footer {{ color:#5b6072; font-size:.8rem; margin-top:32px; text-align:center; }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Dark Pattern Audit</h1>
      <div class="url">{_html.escape(report.page_title or "")} — {_html.escape(report.url)}</div>
    </header>
    <div class="scorecard">
      <div class="grade {report.grade}">{report.grade}</div>
      <div class="score-meta">
        <div><b>{report.score}/100</b> design-honesty score</div>
        <div>{report.risk_level.title()} risk · {len(report.findings)} finding(s)</div>
        <div style="color:#8a90a2">Engine: {_html.escape(report.engine)}{f' ({_html.escape(report.model)})' if report.model else ''}</div>
      </div>
    </div>
    <div class="summary">{_html.escape(report.summary)}</div>
    {cards}
    <footer>Generated by Dark Pattern Auditor · {report.fetched_at:%Y-%m-%d %H:%M UTC}</footer>
  </div>
</body>
</html>"""
