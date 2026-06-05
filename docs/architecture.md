# Architecture

Dark Pattern Auditor is a small, layered Python application. Each layer has one job
and a clean interface, so the engine, the fetcher and the UI can evolve independently.

```
                ┌──────────────────────────────────────────────┐
   User ───────▶│  Web dashboard (web/) │  CLI (dpa.cli)        │
                └───────────────┬───────────────┬──────────────┘
                                │ HTTP/JSON     │ function call
                ┌───────────────▼───────────────▼──────────────┐
                │            Orchestration (dpa.service)        │
                │            audit_url() / audit_html()         │
                └───────────────┬───────────────┬──────────────┘
                                │               │
                 ┌──────────────▼───┐   ┌───────▼───────────────┐
                 │  Fetcher         │   │  Analyzer (engine)    │
                 │  dpa.fetcher     │   │  dpa.analyzer         │
                 │  Playwright →    │   │  ClaudeEngine  ┐      │
                 │  httpx fallback  │   │  HeuristicEngine┘     │
                 └──────────────────┘   └───────┬───────────────┘
                                                │ shared contracts
                 ┌──────────────────────────────▼───────────────┐
                 │  Domain: taxonomy · models · prompts          │
                 │  dpa.taxonomy / dpa.models / dpa.prompts      │
                 └───────────────────────────────────────────────┘
```

## Layers

### Domain (`taxonomy.py`, `models.py`, `prompts.py`)
The single source of truth. `taxonomy.py` encodes the seven dark-pattern categories
(Mathur et al., 2019) and ~20 concrete pattern types. `models.py` defines the Pydantic
`Finding` and `AuditReport`, including the 0–100 honesty score, letter grade and risk
level. `prompts.py` turns the taxonomy into the Claude system prompt and the
structured-output tool schema, so the model can only return findings that fit the
taxonomy.

### Fetcher (`fetcher.py`)
Renders a page with a headless Chromium browser via **Playwright**, capturing the
fully-rendered DOM, the visible text, interactive controls (including which checkboxes
are pre-checked) and a full-page **screenshot** for vision analysis. If Playwright or
its browser binaries are unavailable, it transparently falls back to a static
**httpx + BeautifulSoup** fetch so the tool always works.

### Analyzer (`analyzer.py`)
Two interchangeable engines behind one `analyze(page) -> AuditReport` method:

- **ClaudeEngine** — sends text + screenshot to Claude and forces a single
  `report_dark_patterns` tool call for clean, schema-validated output. The taxonomy
  system prompt is **prompt-cached** to cut cost and latency across audits.
- **HeuristicEngine** — deterministic regex/DOM rules. Needs no API key, so the app
  runs and demos offline; it also serves as the ground-truth fixture for the test suite.

`get_engine()` picks the engine from `DPA_ENGINE` (`auto` → Claude if a key is present,
else heuristic).

### Orchestration (`service.py`)
Thin async glue: fetch → analyze → report. Both the CLI and the web API call the same
two functions, so behaviour is identical across interfaces.

### Interfaces
- **`server.py`** — FastAPI app exposing `/api/audit`, `/api/health`, `/api/taxonomy`
  and serving the static dashboard in `web/`.
- **`cli.py`** — a Typer CLI (`dpa audit`, `dpa serve`, `dpa patterns`).
- **`web/`** — a dependency-free dashboard (vanilla HTML/CSS/JS) that renders the score
  ring, findings and a shareable report.

## Scoring

Each finding subtracts a severity-weighted penalty (low 4 → critical 30), scaled by the
model's confidence, from a starting score of 100. The result maps to a grade (A–F) and a
risk level. See `models.AuditReport.score`.

## Design choices

- **Graceful degradation everywhere** — no browser, no API key, or a malformed model
  response never crashes an audit; the tool downgrades and records a note instead.
- **One taxonomy, many consumers** — the prompt, the heuristics, the scoring and the UI
  all read the same definitions, so adding a pattern is a one-file change.
- **Offline-testable** — the heuristic engine + inline-HTML path mean the whole suite
  runs in CI with no secrets and no network.
