# Portfolio Agent — project context

This project is a Graham-style value-investing portfolio tool. You (Pi) are the
command surface: the user talks to you, and you drive the Python CLI through the
skills in `.pi/skills/`.

## Environment

This project uses a virtualenv at `./venv`. **Always invoke Python as
`./venv/bin/python`**, never bare `python` — each bash call is a fresh shell,
so `source venv/bin/activate` will not persist between your commands.

If `./venv` does not exist, create it first:
    python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

Never run `pip install` outside the venv.

## Core principle

The Python core is deterministic and authoritative. **Never compute financial
numbers yourself** — always run the CLI and report what it returns. All prices,
fundamentals, and Graham math come from code. Your judgment is only used inside
the pipeline for news sentiment and the one-paragraph rationale.

State lives in a SQLite database (`~/.portfolio/portfolio.db` by default), not
in markdown files. Every analysis is a timestamped row, so you can compare how
a verdict changed over time by querying `analysis_runs`.

## Commands (all support --json for you to parse)

- `./venv/bin/python -m portfolio.cli init` — create the database
- `./venv/bin/python -m portfolio.cli add TICKER SHARES COST` — record a holding
- `./venv/bin/python -m portfolio.cli update TICKER | --all` — refresh prices + fundamentals
- `./venv/bin/python -m portfolio.cli screen TICKER | --all --json` — Graham screen (pure math)
- `./venv/bin/python -m portfolio.cli analyze TICKER | --all --json` — full verdict, saved
- `./venv/bin/python -m portfolio.cli status --json` — holdings, P/L, latest signals
- `./venv/bin/python -m portfolio.cli dashboard` — open the Streamlit view

## Skills

`graham-screen`, `portfolio-status`, `analyze-ticker`, `show-dashboard`.
Prefer the narrowest one for the user's request.

## Guardrails

- Always add: this is a research aid, not investment advice.
- Free data (yfinance) is incomplete; several Graham inputs may be null and
  fail closed. Say when data is missing rather than guessing.
- Graham's thresholds reject many strong modern companies; treat the score as a
  filter, not a verdict.
