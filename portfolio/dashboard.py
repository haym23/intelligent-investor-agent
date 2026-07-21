"""Streamlit dashboard. Reads the SQLite DB directly — it never calls the LLM
and never writes. It's a pure view over the rows the agent produced, so it's
always fast and always reflects the latest `analyze` run.

Run via:  python -m portfolio.cli dashboard
"""
from __future__ import annotations

import json
import sqlite3

import pandas as pd
import streamlit as st

from portfolio.db import DEFAULT_DB

st.set_page_config(page_title="Graham Portfolio", layout="wide")

SIGNAL_COLORS = {"buy": "#1a7f37", "hold": "#9a6700", "sell": "#cf222e"}


@st.cache_data(ttl=30)
def q(sql, params=()):
    con = sqlite3.connect(str(DEFAULT_DB))
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


st.title("Graham Portfolio Agent")
st.caption("Deterministic screen + agent verdicts. Not investment advice.")

# --- Holdings + P/L ---------------------------------------------------------
positions = q("SELECT * FROM positions")
if not positions:
    st.info("No positions yet. Add one:  `python -m portfolio.cli add AAPL 10 150`")
else:
    rows = []
    for p in positions:
        price = q("SELECT close FROM prices WHERE ticker=? ORDER BY date DESC LIMIT 1",
                  (p["ticker"],))
        latest = q("SELECT signal, confidence, graham_score, graham_max FROM analysis_runs "
                   "WHERE ticker=? ORDER BY run_at DESC LIMIT 1", (p["ticker"],))
        px = price[0]["close"] if price else None
        v = latest[0] if latest else {}
        rows.append({
            "Ticker": p["ticker"],
            "Shares": p["shares"],
            "Cost": p["cost_basis"],
            "Price": px,
            "Value": round(px * p["shares"], 2) if px else None,
            "P/L": round((px - p["cost_basis"]) * p["shares"], 2) if px else None,
            "Graham": f"{v.get('graham_score','-')}/{v.get('graham_max','-')}",
            "Signal": v.get("signal", "-"),
        })
    df = pd.DataFrame(rows)

    total_value = df["Value"].dropna().sum()
    total_pl = df["P/L"].dropna().sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Portfolio value", f"${total_value:,.2f}")
    c2.metric("Total P/L", f"${total_pl:,.2f}")
    c3.metric("Positions", len(df))

    def color_signal(val):
        return f"color: {SIGNAL_COLORS.get(val, '#57606a')}; font-weight: 600"
    st.dataframe(df.style.map(color_signal, subset=["Signal"]), use_container_width=True)

# --- Ranked buy list --------------------------------------------------------
st.subheader("Latest verdicts (ranked)")
runs = q("""SELECT r.* FROM analysis_runs r
            JOIN (SELECT ticker, MAX(run_at) m FROM analysis_runs GROUP BY ticker) x
            ON r.ticker=x.ticker AND r.run_at=x.m
            ORDER BY r.graham_score DESC, r.confidence DESC""")
if runs:
    # Pull data-quality info from the stored rule detail.
    def _quality(r):
        try:
            detail = json.loads(r["graham_detail_json"] or "[]")
        except Exception:
            return "", ""
        missing = [d["name"] for d in detail if d["value"] is None]
        limited = [d["name"] for d in detail if "LIMITED" in (d.get("detail") or "")]
        return (f"{len(missing)} missing" if missing else "complete",
                f"{len(limited)} limited" if limited else "")

    vdf = pd.DataFrame([{
        "Ticker": r["ticker"],
        "Signal": r["signal"],
        "Confidence": r["confidence"],
        "Graham": f"{r['graham_score']}/{r['graham_max']}",
        "Data": _quality(r)[0],
        "History": _quality(r)[1],
        "Margin of safety": (round(r["margin_of_safety"], 3)
                             if r["margin_of_safety"] is not None else None),
        "Rationale": r["rationale"],
    } for r in runs])
    st.dataframe(vdf, use_container_width=True, hide_index=True)
    st.caption("‘Data: N missing’ means those rules failed for lack of data, "
               "not because the company failed them. ‘History: N limited’ means "
               "a 10/20-year rule was scored on ~5 years.")
else:
    st.info("No analysis runs yet. Run:  `python -m portfolio.cli analyze AAPL`")

# --- Per-ticker detail ------------------------------------------------------
st.subheader("Ticker detail")
tickers = [r["ticker"] for r in q("SELECT DISTINCT ticker FROM analysis_runs")]
if tickers:
    sel = st.selectbox("Ticker", tickers)
    hist = q("SELECT date, close FROM prices WHERE ticker=? ORDER BY date", (sel,))
    if hist:
        ph = pd.DataFrame(hist)
        ph["date"] = pd.to_datetime(ph["date"])
        st.line_chart(ph.set_index("date")["close"], height=240)

    run = q("SELECT * FROM analysis_runs WHERE ticker=? ORDER BY run_at DESC LIMIT 1", (sel,))
    if run:
        detail = json.loads(run[0]["graham_detail_json"] or "[]")
        st.markdown("**Graham rules**")
        rdf = pd.DataFrame([{
            "Rule": d["name"],
            "Passed": "✅" if d["passed"] else "❌",
            "Value": d["value"],
            "Threshold": d["threshold"],
        } for d in detail])
        st.dataframe(rdf, use_container_width=True, hide_index=True)

    news = q("SELECT published, headline, sentiment, reason FROM news "
             "WHERE ticker=? ORDER BY published DESC LIMIT 15", (sel,))
    if news:
        st.markdown("**Recent news**")
        st.dataframe(pd.DataFrame(news), use_container_width=True, hide_index=True)
