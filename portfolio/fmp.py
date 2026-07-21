"""Financial Modeling Prep ingestion — fills the Graham fields yfinance can't.

Free tier: ~250 requests/day, ~5 years of annual statements for US companies.
We use 3 requests per ticker (income statement, balance sheet, quote), so ~80
tickers/day.

IMPORTANT — 5 years, not 10. Graham's earnings-stability and growth rules are
10-year rules. With 5 years of free data we compute the 5-year versions and
record `history_years` so the screen can be honest about it rather than
silently pretending it checked a decade. See graham.py's relaxed mode.

Set FMP_API_KEY to enable. Falls back to yfinance if unset.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date

from .db import connect

BASE = "https://financialmodelingprep.com/stable"
LEGACY = "https://financialmodelingprep.com/api/v3"


class FMPError(RuntimeError):
    pass


def _get(path: str, base: str = BASE, **params) -> list | dict:
    key = os.environ.get("FMP_API_KEY")
    if not key:
        raise FMPError("FMP_API_KEY not set")
    params["apikey"] = key
    url = f"{base}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "graham-portfolio/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if isinstance(data, dict) and data.get("Error Message"):
        raise FMPError(data["Error Message"])
    return data


def _first(d: dict, *keys):
    """FMP has renamed fields across API versions; try several."""
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def fetch_fundamentals(ticker: str, years: int = 5) -> dict:
    """Build a complete fundamentals row from FMP annual statements.

    3 API calls: income-statement, balance-sheet-statement, quote.
    """
    ticker = ticker.upper()

    try:
        income = _get("income-statement", symbol=ticker, limit=years)
        balance = _get("balance-sheet-statement", symbol=ticker, limit=years)
        quote = _get("quote", symbol=ticker)
    except Exception:
        # Older accounts / key types may only have the v3 path.
        income = _get(f"income-statement/{ticker}", base=LEGACY, limit=years)
        balance = _get(f"balance-sheet-statement/{ticker}", base=LEGACY, limit=years)
        quote = _get(f"quote/{ticker}", base=LEGACY)

    if not income or not balance:
        raise FMPError(f"No FMP statement data for {ticker}")

    # Statements come newest-first.
    latest_inc, latest_bal = income[0], balance[0]
    price = None
    if quote:
        q = quote[0] if isinstance(quote, list) else quote
        price = _first(q, "price", "previousClose")

    eps_series = [_first(r, "epsDiluted", "epsdiluted", "eps") for r in income]
    eps_series = [e for e in eps_series if e is not None]

    eps_ttm = eps_series[0] if eps_series else None
    eps_3yr_avg = (sum(eps_series[:3]) / len(eps_series[:3])) if eps_series[:3] else None
    # Oldest available year stands in for "10 years ago" when only 5 exist.
    eps_oldest = eps_series[-1] if eps_series else None

    years_positive = 0
    for e in eps_series:          # count consecutive positive years from newest
        if e is not None and e > 0:
            years_positive += 1
        else:
            break

    shares = _first(latest_inc, "weightedAverageShsOutDil", "weightedAverageShsOut")
    equity = _first(latest_bal, "totalStockholdersEquity", "totalEquity")
    bvps = (equity / shares) if (equity and shares) else None

    return {
        "ticker": ticker,
        "as_of": date.today().isoformat(),
        "revenue": _first(latest_inc, "revenue"),
        "current_assets": _first(latest_bal, "totalCurrentAssets"),
        "current_liabilities": _first(latest_bal, "totalCurrentLiabilities"),
        "eps": eps_ttm,
        "eps_3yr_avg": eps_3yr_avg,
        "eps_10yr_ago": eps_oldest,
        "book_value_ps": bvps,
        "price": price,
        "years_positive_eps": years_positive,
        "years_dividends": None,        # filled by fetch_dividend_years()
        "history_years": len(eps_series),
    }


def fetch_dividend_years(ticker: str) -> int | None:
    """Count consecutive recent calendar years with at least one dividend."""
    try:
        try:
            data = _get("dividends", symbol=ticker.upper(), limit=200)
        except Exception:
            data = _get(f"historical-price-full/stock_dividend/{ticker.upper()}", base=LEGACY)
            data = data.get("historical", []) if isinstance(data, dict) else data
        if not data:
            return 0
        years = set()
        for row in data:
            d = _first(row, "date", "paymentDate", "recordDate")
            if d:
                years.add(int(str(d)[:4]))
        if not years:
            return 0
        # Count back from the most recent dividend year without a gap.
        newest = max(years)
        streak = 0
        y = newest
        while y in years:
            streak += 1
            y -= 1
        return streak
    except Exception:
        return None


def update_fundamentals_fmp(ticker: str, db=None, with_dividends: bool = True) -> dict:
    row = fetch_fundamentals(ticker)
    if with_dividends:
        row["years_dividends"] = fetch_dividend_years(ticker)
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


def available() -> bool:
    return bool(os.environ.get("FMP_API_KEY"))
