---
name: analyze-ticker
description: Run the full analysis pipeline on a ticker — Graham screen plus news sentiment plus a buy/hold/sell verdict with a short rationale — and save the result to the database as a timestamped run. Use when the user asks for a full opinion on a stock, "should I buy/sell X", or wants the agent's current recommendation. This is the heavier command; use graham-screen alone if they only want the fundamentals check.
---

# Analyze Ticker

Run the complete pipeline and persist a verdict. Each run is timestamped, so
repeated analyses build a history you can compare over time.

## How to run

Single ticker:
```bash
./venv/bin/python -m portfolio.cli analyze TICKER --json
```

All held positions:
```bash
./venv/bin/python -m portfolio.cli analyze --all --json
```

## Reading the output

JSON per ticker includes the full Graham `score`/`max`, `signal`
(buy/hold/sell), `confidence` (0–1), `margin_of_safety`, `avg_news_sentiment`,
and a `rationale`.

Report the signal and confidence first, then the Graham score, then one line
of reasoning. If `ANTHROPIC_API_KEY` is not set the verdict comes from a
deterministic rule-based fallback rather than the LLM — the rationale will say
so; pass that caveat along.

Always remind the user this is a research aid, not investment advice, and that
free fundamentals data can be incomplete.
