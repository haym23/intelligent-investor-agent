# Graham Portfolio Agent

A value-investing portfolio tool you drive through the **Pi coding agent**.
The Python core is deterministic (prices, fundamentals, and Graham's math are
computed in code, never by an LLM); the LLM is confined to news sentiment and a
short rationale. Everything is stored as **timestamped rows in SQLite** — no
markdown files to lose track of — and a Streamlit dashboard renders the charts.

## Why it's built this way

- **No markdown rot.** The agent writes rows to a database, not prose files.
  Every verdict is queryable and diffable over time.
- **Math can't be hallucinated.** Graham rules are pure functions with unit
  tests (`tests/test_graham.py`).
- **Pi is the interface.** You talk to Pi; Pi runs the CLI via the skills in
  `.pi/skills/`. Rich graphics open in the browser via Streamlit.

## Setup

```bash
pip install -r requirements.txt
python -m portfolio.cli init
export FMP_API_KEY=...                  # strongly recommended: complete Graham data
export OPENROUTER_API_KEY=sk-or-...     # optional; falls back to rule-based verdicts
export OPENROUTER_MODEL=anthropic/claude-sonnet-4.5   # optional; any OpenRouter model
```

## Use it directly (CLI)

```bash
python -m portfolio.cli watch F VZ MO KHC     # research candidates (0 shares)
python -m portfolio.cli add AAPL 10 150       # a real holding
python -m portfolio.cli update --all
python -m portfolio.cli rank                  # ranked candidate view
python -m portfolio.cli screen AAPL --json
python -m portfolio.cli analyze --all
python -m portfolio.cli status
python -m portfolio.cli dashboard        # opens the browser view
```

## Use it through Pi

Start Pi in this directory. It loads `.pi/AGENTS.md` for context and the skills
in `.pi/skills/`. Then just talk:

- "Screen AAPL against Graham's rules"  → `graham-screen`
- "How's my portfolio doing?"           → `portfolio-status`
- "Should I buy MSFT?"                   → `analyze-ticker`
- "Show me the dashboard"               → `show-dashboard`

Pi runs the underlying command, parses the JSON, and explains it — while the
terminal stays your single command surface.

## Tests

```bash
pytest -q
```

## Data sources

With `FMP_API_KEY` set, fundamentals come from Financial Modeling Prep and all
eight Graham rules are computable. The free tier gives ~250 requests/day and
~5 years of annual statements (each ticker costs ~4 requests, so ~60/day).

Because 5 years is less than Graham's 10-year earnings-stability and 20-year
dividend requirements, those rules are **scaled to available history and
flagged LIMITED** rather than silently passing on thin evidence. Screen output
separates `real_failures` from `missing_data_rules` so a company is never
penalized for absent data.

Without an FMP key it falls back to yfinance, which leaves four fields null —
most tickers will cap around 4/8.

## Caveats

Graham's thresholds (especially P/B <= 1.5) reject most modern quality
companies; treat the score as a filter for further work, not a verdict. A
5-year record through a favorable period proves much less than a 20-year one.
**Not investment advice.**
