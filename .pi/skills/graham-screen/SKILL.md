---
name: graham-screen
description: Screen one or more stock tickers against Benjamin Graham's defensive-investor criteria. Use when the user asks whether a stock passes Graham's rules, wants a value-investing screen, or asks "is X a good buy" from a fundamentals standpoint. Returns per-rule pass/fail with the actual computed values plus a Graham number and margin of safety.
---

# Graham Screen

Run the deterministic Graham screen. The math is done in Python, not by you —
your job is to run the command, read the JSON, and explain the result plainly.

## How to run

For a single ticker:
```bash
./venv/bin/python -m portfolio.cli screen TICKER --json
```

For every held position:
```bash
./venv/bin/python -m portfolio.cli screen --all --json
```

If the command reports missing fundamentals, first refresh data:
```bash
./venv/bin/python -m portfolio.cli update TICKER
```
then screen again.

## Reading the output

The JSON is a list of objects, each with `score`, `max`, `graham_number`,
`price`, `margin_of_safety`, and a `rules` array. Each rule has `name`,
`passed`, `value`, and `threshold`.

When you report back: lead with the score (e.g. "6/8 rules passed"), name the
rules that FAILED and their values, and state the margin of safety. Do not
invent numbers — only report what the JSON contains. A rule with `value: null`
means the data wasn't available and it failed closed; say so rather than
guessing.

Never call this financial advice. It is a mechanical filter, and Graham's
thresholds (especially P/B <= 1.5) reject many strong modern companies.
