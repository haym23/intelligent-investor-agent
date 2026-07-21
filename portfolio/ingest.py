"""Deterministic ingestion. Numbers come from code, never from an LLM.

Uses yfinance (free). Fundamentals from free sources are patchy: some fields
(10-yr-ago EPS, consecutive dividend years) aren't cleanly available, so we
fill what we can and leave the rest None. graham.py fails those rules closed
rather than guessing. Swap in FMP/Finnhub later for cleaner data.
"""
from __future__ import annotations

from datetime import date

from .db import connect, utcnow


def _lazy_yf():
    try:
        import yfinance as yf
        return yf
    except ImportError as e:
        raise SystemExit(
            "yfinance not installed. Run: pip install yfinance"
        ) from e


def update_prices(ticker: str, period: str = "1y", db=None) -> int:
    yf = _lazy_yf()
    hist = yf.Ticker(ticker).history(period=period)
    rows = 0
    with connect(db) as conn:
        for idx, r in hist.iterrows():
            conn.execute(
                """INSERT OR REPLACE INTO prices
                   (ticker, date, open, high, low, close, volume)
                   VALUES (?,?,?,?,?,?,?)""",
                (ticker, idx.date().isoformat(), float(r["Open"]), float(r["High"]),
                 float(r["Low"]), float(r["Close"]), float(r["Volume"])),
            )
            rows += 1
    return rows


def update_fundamentals(ticker: str, db=None) -> dict:
    """Pull fundamentals. Prefers FMP (complete Graham fields) when FMP_API_KEY
    is set; falls back to yfinance (several fields will be None)."""
    from . import fmp
    if fmp.available():
        try:
            return fmp.update_fundamentals_fmp(ticker, db=db)
        except Exception as e:
            print(f"  FMP failed for {ticker} ({e}); falling back to yfinance")
    return _update_fundamentals_yf(ticker, db=db)


def _update_fundamentals_yf(ticker: str, db=None) -> dict:
    """Pull what yfinance exposes and map to our fundamentals schema.
    Missing fields stay None on purpose (fail-closed screening)."""
    yf = _lazy_yf()
    t = yf.Ticker(ticker)
    info = t.info or {}

    price = info.get("currentPrice") or info.get("previousClose")
    eps = info.get("trailingEps")
    bvps = info.get("bookValue")

    # Current assets/liabilities from the latest balance sheet if available.
    ca = cl = None
    try:
        bs = t.balance_sheet
        if bs is not None and not bs.empty:
            col = bs.columns[0]
            for key in ("Current Assets", "Total Current Assets"):
                if key in bs.index:
                    ca = float(bs.loc[key, col]); break
            for key in ("Current Liabilities", "Total Current Liabilities"):
                if key in bs.index:
                    cl = float(bs.loc[key, col]); break
    except Exception:
        pass

    row = {
        "ticker": ticker,
        "as_of": date.today().isoformat(),
        "revenue": info.get("totalRevenue"),
        "current_assets": ca,
        "current_liabilities": cl,
        "eps": eps,
        "eps_3yr_avg": None,     # needs multi-year history; fill from a better source
        "eps_10yr_ago": None,
        "book_value_ps": bvps,
        "price": price,
        "years_positive_eps": None,
        "years_dividends": None,
        "history_years": None,
    }
    with connect(db) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO fundamentals
               (ticker, as_of, revenue, current_assets, current_liabilities,
                eps, eps_3yr_avg, eps_10yr_ago, book_value_ps, price,
                years_positive_eps, years_dividends, history_years)
               VALUES (:ticker,:as_of,:revenue,:current_assets,:current_liabilities,
                       :eps,:eps_3yr_avg,:eps_10yr_ago,:book_value_ps,:price,
                       :years_positive_eps,:years_dividends,:history_years)""",
            row,
        )
    return row


def load_fundamentals(ticker: str, db=None) -> dict | None:
    with connect(db) as conn:
        r = conn.execute("SELECT * FROM fundamentals WHERE ticker=?", (ticker,)).fetchone()
        return dict(r) if r else None
