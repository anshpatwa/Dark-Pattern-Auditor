<div align="center">

# 🕵️ Dark Pattern Auditor

**AI-powered auditing for deceptive UX.** Point it at any web page and it detects
*dark patterns* — confirmshaming, fake urgency, hidden subscriptions, pre-checked
opt-ins, roach-motel cancellation and more — then scores the page's design honesty
and tells you how to fix each issue.

[![CI](https://github.com/anshpatwa/Dark-Pattern-Auditor/actions/workflows/ci.yml/badge.svg)](https://github.com/anshpatwa/Dark-Pattern-Auditor/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by Claude](https://img.shields.io/badge/AI-Claude-a06bff.svg)](https://www.anthropic.com/)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

</div>

---

## What are dark patterns?

Dark patterns (a.k.a. *deceptive design patterns*) are interface and copy choices that
trick users into doing things they didn't mean to — buying insurance they didn't ask
for, signing up for a subscription that's hard to cancel, or being shamed out of
declining an offer. They're increasingly **regulated** (FTC, EU DSA, India's CCPA
guidelines). This tool audits a page for them, automatically.

## ✨ Features

- **🧠 AI detection engine** — sends the rendered page **and a screenshot** to an LLM and
  gets back schema-validated findings (multimodal: it reads *and sees* the page).
- **🔌 Pluggable backends** — use **Anthropic Claude** *or* **Google Gemini** (which has a
  **free tier, no credit card**). The engine auto-selects from whichever key you provide.
- **🦾 Works with no API key** — a built-in **heuristic engine** runs fully offline, so the
  app demos instantly; add a (free) key later to unlock the AI engine.
- **🌐 Full-browser rendering** — uses **Playwright** (headless Chromium) to catch
  JavaScript-injected timers, pop-ups and pre-checked boxes; falls back to a static
  fetch automatically if a browser isn't available.
- **📊 Honesty score & grade** — every audit gets a 0–100 score, an A–F grade and a risk
  level, with per-severity and per-category breakdowns.
- **🎛️ Two interfaces** — a polished **web dashboard** *and* a scriptable **CLI**.
- **📚 Research-backed taxonomy** — 7 categories / ~20 pattern types from Mathur et al.
  (2019) and [deceptive.design](https://www.deceptive.design/).
- **📦 Production-shaped** — typed (Pydantic), tested (pytest, offline), linted (ruff),
  CI on GitHub Actions, MIT-licensed.

## 🖼️ The dashboard

Paste a URL → get a scored, evidence-backed report you can share:

```
┌─────────────────────────────────────────────────────────┐
│  🕵️ Dark Pattern Auditor          AI · Claude (opus 4.8) │
│  ┌─────────────────────────────────────────────────────┐│
│  │  https://example.com/checkout         [ Audit page ] ││
│  └─────────────────────────────────────────────────────┘│
│   ( D )   42/100 honesty score · High risk · 6 findings  │
│           ⛔1  🔴2  🟠2  🟡1                               │
│   ▸ Confirmshaming — HIGH        "No thanks, I don't…"   │
│   ▸ Pre-checked opt-in — HIGH     checkbox (CHECKED)     │
│   ▸ Hidden subscription — HIGH    "billed $29/month…"    │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick start

```bash
# 1. Clone and install
git clone https://github.com/anshpatwa/Dark-Pattern-Auditor.git
cd Dark-Pattern-Auditor
python -m venv .venv && .venv\Scripts\activate      # Windows
# source .venv/bin/activate                          # macOS/Linux
pip install -e .

# 2. (Optional but recommended) install the browser for full rendering
python -m playwright install chromium

# 3. (Optional) enable the AI engine
copy .env.example .env
#   then add ONE of:
#     GEMINI_API_KEY=...      ← free, no card: https://aistudio.google.com
#     ANTHROPIC_API_KEY=...   ← Claude (paid): https://console.anthropic.com

# 4. Launch the dashboard
dpa serve
#  → open http://127.0.0.1:8000
```

Without any key it runs in **heuristic mode** and still produces a full report.
Add a **`GEMINI_API_KEY`** (free) or **`ANTHROPIC_API_KEY`** to `.env` and the matching
AI engine is selected automatically — the dashboard pill flips to "AI · Gemini/Claude".

## 🖥️ CLI usage

```bash
dpa audit https://example.com                 # pretty console report
dpa audit https://example.com -f json -o report.json
dpa audit https://example.com -f html -o report.html
dpa audit https://example.com --no-browser    # static fetch only
dpa patterns                                  # list the taxonomy it checks
dpa serve --port 9000                         # run the web dashboard
```

## 🔌 API

The FastAPI backend exposes a small JSON API (great for CI gates or browser extensions):

| Method | Endpoint            | Description                              |
|--------|---------------------|------------------------------------------|
| `POST` | `/api/audit`        | Audit a URL → full JSON report           |
| `POST` | `/api/audit/html`   | Audit raw HTML (no network)              |
| `GET`  | `/api/taxonomy`     | The dark-pattern taxonomy                |
| `GET`  | `/api/health`       | Active engine, model, key status         |

```bash
curl -s -X POST http://127.0.0.1:8000/api/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' | jq .score
```

## 🧭 The taxonomy

| Category        | Example patterns                                              |
|-----------------|--------------------------------------------------------------|
| **Sneaking**    | hidden costs, hidden subscription, sneak-into-basket          |
| **Urgency**     | fake countdown timers, limited-time messaging                |
| **Misdirection**| confirmshaming, visual interference, trick wording           |
| **Social proof**| fake activity pop-ups, fake testimonials                     |
| **Scarcity**    | "only 2 left", "18 people viewing"                           |
| **Obstruction** | hard-to-cancel (roach motel), comparison prevention, nagging |
| **Forced action**| forced enrollment, pre-checked opt-ins, forced continuity   |

Run `dpa patterns` for the full list with default severities.

## 🏗️ Architecture

A clean, layered design — see [`docs/architecture.md`](docs/architecture.md).

```
web/ + cli  →  service (orchestration)  →  fetcher (Playwright/httpx)
                                        →  analyzer (Claude / heuristic)
                          ↘ shared domain: taxonomy · models · prompts
```

## 🧪 Development

```bash
pip install -e ".[dev]"
pytest          # full suite runs offline — no API key, no network
ruff check src tests
```

The test suite audits bundled fixture pages
([`examples/`](examples/)) with the heuristic engine, so CI is hermetic.

## 🗺️ Roadmap

- [ ] Batch auditing + CSV/HTML export across many URLs
- [ ] Browser extension that audits the page you're on
- [ ] Per-element bounding boxes from vision for visual highlighting
- [ ] Regression/CI gate: fail a build if a page's honesty score drops

## ⚖️ Responsible use

This is an **educational and defensive** tool: it helps designers, researchers and
regulators *find and remove* manipulative patterns. Audit only pages you are authorised
to, and respect each site's terms of service and rate limits.

## 📄 License

[MIT](LICENSE) © 2026 Ansh Patwa

<div align="center">
<sub>Built with FastAPI · Playwright · Anthropic Claude · Pydantic</sub>
</div>
