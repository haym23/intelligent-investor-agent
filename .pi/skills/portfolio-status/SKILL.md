---
name: portfolio-status
description: Show the user's current holdings with latest price, position value, profit/loss, and the most recent buy/hold/sell signal per ticker. Use when the user asks how their portfolio is doing, what they own, their P/L, or "what's my position in X".
---

# Portfolio Status

Report the current state of the portfolio from the database.

## How to run

```bash
./venv/bin/python -m portfolio.cli status --json
```

To add a position first:
```bash
./venv/bin/python -m portfolio.cli add TICKER SHARES COST_PER_SHARE
```

To refresh prices before reporting (recommended if data looks stale):
```bash
./venv/bin/python -m portfolio.cli update --all
```

## Reading the output

JSON is a list of positions with `ticker`, `shares`, `cost_basis`, `price`,
`value`, `pl` (dollar profit/loss), and `signal`. Summarize total value and
total P/L, then flag any position whose latest signal is `sell`. If `price` is
null, the position hasn't been priced yet — tell the user to run `update`.
