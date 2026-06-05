"""Command-line interface for the Dark Pattern Auditor."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dpa import __version__
from dpa.config import settings
from dpa.models import AuditReport
from dpa.report import to_html, to_json, to_markdown
from dpa.service import audit_url
from dpa.taxonomy import categories

app = typer.Typer(
    add_completion=False,
    help="AI-powered auditor that detects deceptive UX (dark patterns) on web pages.",
)
console = Console()

_GRADE_COLOR = {"A": "green", "B": "green", "C": "yellow", "D": "dark_orange", "F": "red"}
_SEV_COLOR = {"low": "yellow", "medium": "dark_orange", "high": "red", "critical": "bright_red"}


@app.command()
def audit(
    url: str = typer.Argument(..., help="The URL to audit."),
    fmt: str = typer.Option("console", "--format", "-f", help="console | json | md | html"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write the report to a file."),
    browser: bool = typer.Option(True, "--browser/--no-browser", help="Use a headless browser (Playwright)."),
    screenshots: Path | None = typer.Option(None, "--screenshots", help="Directory to save the page screenshot."),
) -> None:
    """Audit a single URL and print or save the report."""
    report = asyncio.run(
        audit_url(url, use_browser=browser, capture_screenshot=browser, screenshot_dir=screenshots)
    )

    rendered = _render(report, fmt)
    if output is not None:
        output.write_text(rendered if fmt != "console" else to_markdown(report), encoding="utf-8")
        console.print(f"[green]Report written to[/green] {output}")
        if fmt == "console":
            _print_console(report)
    elif fmt == "console":
        _print_console(report)
    else:
        console.print(rendered)


@app.command()
def serve(
    host: str = typer.Option(settings.dpa_host, help="Host to bind."),
    port: int = typer.Option(settings.dpa_port, help="Port to bind."),
) -> None:
    """Launch the web dashboard."""
    import uvicorn

    console.print(
        Panel.fit(
            f"Dark Pattern Auditor dashboard\nhttp://{host}:{port}\n"
            f"Engine: [bold]{settings.resolved_engine()}[/bold]"
            + ("" if settings.has_api_key else "  (no API key → heuristic mode)"),
            border_style="cyan",
        )
    )
    uvicorn.run("dpa.server:app", host=host, port=port, reload=False)


@app.command()
def patterns() -> None:
    """List the dark-pattern taxonomy the auditor checks for."""
    for cat in categories():
        table = Table(title=f"{cat.name} — {cat.description}", show_lines=False, expand=True)
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Pattern")
        table.add_column("Default", justify="center")
        for p in cat.patterns:
            table.add_row(p.key, p.name, p.default_severity)
        console.print(table)
        console.print()


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"dark-pattern-auditor {__version__}")


def _render(report: AuditReport, fmt: str) -> str:
    fmt = fmt.lower()
    if fmt in {"json"}:
        return to_json(report)
    if fmt in {"md", "markdown"}:
        return to_markdown(report)
    if fmt in {"html"}:
        return to_html(report)
    return to_markdown(report)


def _print_console(report: AuditReport) -> None:
    grade_color = _GRADE_COLOR.get(report.grade, "white")
    console.print(
        Panel.fit(
            f"[bold {grade_color}]{report.grade}[/]  "
            f"[bold]{report.score}/100[/]  ·  {report.risk_level} risk  ·  "
            f"{len(report.findings)} finding(s)\n"
            f"[dim]{report.url}[/dim]\n"
            f"[dim]engine: {report.engine}{f' ({report.model})' if report.model else ''}[/dim]",
            title="Dark Pattern Audit",
            border_style=grade_color,
        )
    )
    if report.summary:
        console.print(f"[italic]{report.summary}[/italic]\n")

    if not report.findings:
        console.print("[green]✅ No dark patterns detected.[/green]")
        return

    for i, f in enumerate(report.sorted_findings(), start=1):
        color = _SEV_COLOR.get(f.severity.value, "white")
        console.print(
            f"[bold]{i}. [{color}]{f.severity.value.upper()}[/] {f.title}[/]  "
            f"[dim]({f.category_label} · {f.confidence:.0%})[/dim]"
        )
        console.print(f"   {f.description}")
        console.print(f"   [dim]Evidence:[/dim] {f.evidence}")
        console.print(f"   [green]Fix:[/green] {f.recommendation}\n")


if __name__ == "__main__":
    app()
