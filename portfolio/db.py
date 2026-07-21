"""SQLite storage. The whole point of this project: the agent writes rows here,
not markdown files. Every verdict is timestamped so you can see how the agent's
opinion of a ticker changed over time.

One file, no server. Set PORTFOLIO_DB to override the path (tests use :memory:).
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("PORTFOLIO_DB", Path.home() / ".portfolio" / "portfolio.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL,
    shares      REAL NOT NULL,
    cost_basis  REAL NOT NULL,          -- per-share cost
    opened_at   TEXT NOT NULL,
    note        TEXT
);

CREATE TABLE IF NOT EXISTS prices (
    ticker  TEXT NOT NULL,
    date    TEXT NOT NULL,              -- ISO date
    open    REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (ticker, date)
);

-- One row per ticker: the latest snapshot of the numbers Graham needs.
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker              TEXT PRIMARY KEY,
    as_of               TEXT NOT NULL,
    revenue             REAL,           -- trailing annual
    current_assets      REAL,
    current_liabilities REAL,
    eps                 REAL,           -- trailing EPS
    eps_3yr_avg         REAL,           -- 3-yr average EPS
    eps_10yr_ago        REAL,           -- for growth rule
    book_value_ps       REAL,
    price               REAL,           -- latest price used for ratios
    years_positive_eps  INTEGER,        -- consecutive years of positive earnings
    years_dividends     INTEGER,        -- consecutive years paying dividends
    history_years       INTEGER         -- how many years of statements we actually have
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL,
    run_at      TEXT NOT NULL,
    graham_score        INTEGER,        -- rules passed (0..N)
    graham_max          INTEGER,        -- N
    graham_detail_json  TEXT,           -- per-rule pass/fail + values
    margin_of_safety    REAL,           -- (graham_number - price) / graham_number
    signal      TEXT,                   -- buy | hold | sell
    confidence  REAL,                   -- 0..1
    rationale   TEXT                    -- short, one paragraph, stored not filed
);

CREATE TABLE IF NOT EXISTS news (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL,
    published   TEXT,
    headline    TEXT NOT NULL,
    url         TEXT,
    sentiment   REAL,                   -- -1..1
    materiality REAL,                   -- 0..1
    reason      TEXT,
    fetched_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_ticker ON analysis_runs(ticker, run_at);
CREATE INDEX IF NOT EXISTS idx_news_ticker ON news(ticker, published);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: Path | str | None = None):
    path = Path(db_path) if db_path else DEFAULT_DB
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DEFAULT_DB}")
