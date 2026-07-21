"""CLI surface. Pi skills shell out to these commands.

Every command takes --json so an agent gets structured output it can reason
over, while humans get readable text. This dual output is what keeps Pi's
context clean: the skill parses JSON, you read the table.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer

from . import db as dbmod
from . import ingest, agent, graham

app = typer.Typer(add_completion=False, help="Graham-style portfolio agent.")


def _emit(payload, as_json: bool, human):
    if as_json:
        typer.echo(json.dumps(payload, default=str))
    else:
        human(payload)


@app.command()
def init():
    """Create the database."""
    dbmod.init_db()
    typer.echo(f"Initialized {dbmod.DEFAULT_DB}")


@app.command()
def add(ticker: str, shares: float, cost: float, note: str = ""):
    """Add a position: portfolio add AAPL 10 150.00"""
    with dbmod.connect() as conn:
        conn.execute(
            "INSERT INTO positions (ticker, shares, cost_basis, opened_at, note) "
            "VALUES (?,?,?,?,?)",
            (ticker.upper(), shares, cost, dbmod.utcnow(), note),
        )
    typer.echo(f"Added {shares} {ticker.upper()} @ {cost}")


@app.command()
def update(ticker: str = typer.Argument(None), all_positions: bool = typer.Option(False, "--all")):
    """Refresh prices + fundamentals for a ticker (or --all held tickers)."""
    tickers = _resolve_tickers(ticker, all_positions)
    for t in tickers:
        n = ingest.update_prices(t)
        ingest.update_fundamentals(t)
        typer.echo(f"{t}: {n} price rows, fundamentals refreshed")


@app.command()
def screen(ticker: str = typer.Argument(None), all_positions: bool = typer.Option(False, "--all"),
           as_json: bool = typer.Option(False, "--json")):
    """Run Graham screening (pure math, no LLM)."""
    tickers = _resolve_tickers(ticker, all_positions)
    out = []
    for t in tickers:
        f = ingest.load_fundamentals(t) or ingest.update_fundamentals(t)
        out.append(graham.score(f))

    def human(payload):
        for r in payload:
            typer.echo(f"\n{r['ticker']}: {r['score']}/{r['max']} rules passed"
                       f"  | Graham# {r['graham_number']}  price {r['price']}"
                       f"  | MoS {r['margin_of_safety']}")
            for rule in r["rules"]:
                mark = "PASS" if rule["passed"] else "fail"
                typer.echo(f"   [{mark}] {rule['name']}: {rule['value']} "
                           f"(<= {rule['threshold']})")
    _emit(out, as_json, human)


@app.command()
def analyze(ticker: str = typer.Argument(None), all_positions: bool = typer.Option(False, "--all"),
            as_json: bool = typer.Option(False, "--json")):
    """Full agent pipeline: screen + news + buy/hold/sell verdict, saved to DB."""
    tickers = _resolve_tickers(ticker, all_positions)
    out = [agent.analyze(t) for t in tickers]

    def human(payload):
        for r in payload:
            typer.echo(f"\n{r['ticker']}: {r['signal'].upper()} "
                       f"(conf {r['confidence']}) — {r['score']}/{r['max']} Graham")
            typer.echo(f"   {r['rationale']}")
    _emit(out, as_json, human)


@app.command()
def status(as_json: bool = typer.Option(False, "--json")):
    """Show current holdings with latest price, P/L, and last verdict."""
    with dbmod.connect() as conn:
        positions = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]
        for p in positions:
            price = conn.execute(
                "SELECT close FROM prices WHERE ticker=? ORDER BY date DESC LIMIT 1",
                (p["ticker"],)).fetchone()
            latest = conn.execute(
                "SELECT signal, graham_score, graham_max, run_at FROM analysis_runs "
                "WHERE ticker=? ORDER BY run_at DESC LIMIT 1", (p["ticker"],)).fetchone()
            p["price"] = price["close"] if price else None
            p["value"] = (p["price"] * p["shares"]) if p["price"] else None
            p["pl"] = ((p["price"] - p["cost_basis"]) * p["shares"]) if p["price"] else None
            p["signal"] = latest["signal"] if latest else None

    def human(payload):
        typer.echo("Ticker  Shares   Cost    Price   Value      P/L       Signal")
        for p in payload:
            typer.echo(f"{p['ticker']:<7} {p['shares']:<7} {p['cost_basis']:<7} "
                       f"{p['price'] or '-':<7} {p['value'] or '-':<10} "
                       f"{p['pl'] or '-':<9} {p['signal'] or '-'}")
    _emit(positions, as_json, human)


@app.command()
def watch(tickers: list[str]):
    """Add tickers to the watchlist (zero shares, research only).

    portfolio watch F VZ MO KHC
    """
    with dbmod.connect() as conn:
        for t in tickers:
            t = t.upper()
            exists = conn.execute(
                "SELECT 1 FROM positions WHERE ticker=? AND shares=0", (t,)).fetchone()
            if exists:
                typer.echo(f"{t}: already watching")
                continue
            conn.execute(
                "INSERT INTO positions (ticker, shares, cost_basis, opened_at, note) "
                "VALUES (?,0,0,?,'watchlist')", (t, dbmod.utcnow()))
            typer.echo(f"{t}: added to watchlist")


@app.command()
def rank(as_json: bool = typer.Option(False, "--json"),
         min_score: int = typer.Option(0, "--min-score")):
    """Rank every screened ticker by Graham score. The candidate-finding view."""
    with dbmod.connect() as conn:
        tickers = [r["ticker"] for r in
                   conn.execute("SELECT DISTINCT ticker FROM fundamentals").fetchall()]
    out = []
    for t in tickers:
        f = ingest.load_fundamentals(t)
        if f:
            r = graham.score(f)
            if r["score"] >= min_score:
                out.append(r)
    out.sort(key=lambda r: (r["score"], r["margin_of_safety"] or -99), reverse=True)

    def human(payload):
        typer.echo("Ticker  Score  Avail   MoS      RealFails")
        for r in payload:
            mos = f"{r['margin_of_safety']:.2f}" if r["margin_of_safety"] is not None else "-"
            typer.echo(f"{r['ticker']:<7} {r['score']}/{r['max']}    "
                       f"{r['score_of_available']:<7} {mos:<8} "
                       f"{','.join(r['real_failures']) or 'none'}")
    _emit(out, as_json, human)


@app.command()
def dashboard(open_browser: bool = typer.Option(True, "--open/--no-open")):
    """Launch the Streamlit dashboard (rich charts in your browser)."""
    app_path = Path(__file__).parent / "dashboard.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    if not open_browser:
        cmd += ["--server.headless=true"]
    typer.echo("Starting Streamlit… (Ctrl+C to stop)")
    subprocess.run(cmd)


def _resolve_tickers(ticker, all_positions):
    if all_positions:
        with dbmod.connect() as conn:
            return [r["ticker"] for r in
                    conn.execute("SELECT DISTINCT ticker FROM positions").fetchall()]
    if ticker:
        return [ticker.upper()]
    raise typer.BadParameter("Provide a ticker or use --all")


if __name__ == "__main__":
    app()
