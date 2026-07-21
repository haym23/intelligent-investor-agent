---
name: show-dashboard
description: Open the visual Streamlit dashboard in the user's browser, showing portfolio value, P/L, a ranked buy list, per-ticker price charts, Graham rule tables, and recent news. Use when the user wants to SEE their portfolio, asks for charts/graphics, or says "show me the dashboard". The terminal is for quick answers; this is for the rich visual view.
---

# Show Dashboard

Launch the browser dashboard. The terminal can't render good charts, so this is
where price history, the ranked buy list, and color-coded signals live.

## How to run

```bash
./venv/bin/python -m portfolio.cli dashboard
```

This starts Streamlit and opens a browser tab. It runs in the foreground until
the user stops it (Ctrl+C), so tell them it will keep running and that the
terminal is occupied while it does.

If they want it without auto-opening a tab (e.g. remote/headless):
```bash
./venv/bin/python -m portfolio.cli dashboard --no-open
```

The dashboard only reads the database — it shows whatever the latest `analyze`
runs produced. If it looks empty or stale, run `analyze --all` first, then
refresh the browser.
