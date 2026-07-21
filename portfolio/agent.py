"""The LLM layer. Confined to the two things an LLM is actually good at:
reading news and writing a short rationale. Both return STRUCTURED data that
goes into the database as rows — never loose prose, never a markdown file.

If no API key is set, falls back to a deterministic heuristic so the whole
pipeline still runs offline (and tests don't need a network).
"""
from __future__ import annotations

import json
import os
from datetime import date

from .db import connect, utcnow
from . import graham, ingest


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Override with OPENROUTER_MODEL to use any model OpenRouter exposes.
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")


def _has_llm() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _llm_json(system: str, user: str) -> dict:
    """Call OpenRouter, forcing a JSON object back. Returns {} on any failure.

    Uses the OpenAI-compatible chat/completions schema with response_format
    json_object. Falls back silently so the pipeline never breaks on an API
    hiccup — the caller's deterministic path takes over.
    """
    try:
        import urllib.request

        key = os.environ["OPENROUTER_API_KEY"]
        payload = {
            "model": DEFAULT_MODEL,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system",
                 "content": system + "\nRespond with ONLY a JSON object, no prose, no markdown."},
                {"role": "user", "content": user},
            ],
        }
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                # Optional but recommended by OpenRouter for attribution.
                "HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "http://localhost"),
                "X-Title": "Graham Portfolio Agent",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        text = data["choices"][0]["message"]["content"]
        return json.loads(text.strip().strip("`").removeprefix("json").strip())
    except Exception:
        return {}


def score_news(headline: str) -> dict:
    """Sentiment + materiality for one headline -> dict for the news table."""
    if _has_llm():
        out = _llm_json(
            "You score financial news for one stock.",
            f"Headline: {headline}\n"
            "Return keys: sentiment (-1..1 float), materiality (0..1 float), "
            "reason (short string).",
        )
        if out:
            return {
                "sentiment": float(out.get("sentiment", 0)),
                "materiality": float(out.get("materiality", 0)),
                "reason": str(out.get("reason", ""))[:300],
            }
    # Offline fallback: neutral, low materiality.
    return {"sentiment": 0.0, "materiality": 0.1, "reason": "heuristic: no LLM configured"}


def synthesize(ticker: str, screen_result: dict, news_sentiment: float) -> dict:
    """Combine Graham score + news into a buy/hold/sell verdict (structured)."""
    score = screen_result["score"]
    maxs = screen_result["max"]
    mos = screen_result.get("margin_of_safety")

    if _has_llm():
        out = _llm_json(
            "You are a disciplined value-investing analyst in the Graham tradition. "
            "You weight the quantitative screen heavily and news lightly.",
            f"Ticker {ticker}. Graham score {score}/{maxs}. "
            f"Margin of safety {mos}. Average news sentiment {news_sentiment}. "
            "Return keys: signal ('buy'|'hold'|'sell'), confidence (0..1 float), "
            "rationale (<= 3 sentences).",
        )
        if out.get("signal") in ("buy", "hold", "sell"):
            return {
                "signal": out["signal"],
                "confidence": float(out.get("confidence", 0.5)),
                "rationale": str(out.get("rationale", ""))[:600],
            }

    # Deterministic fallback so the pipeline always produces a verdict.
    ratio = score / maxs if maxs else 0
    if ratio >= 0.75 and (mos is None or mos > 0):
        sig, conf = "buy", 0.6 + 0.4 * ratio
    elif ratio <= 0.375:
        sig, conf = "sell", 0.5 + 0.3 * (1 - ratio)
    else:
        sig, conf = "hold", 0.5
    return {
        "signal": sig,
        "confidence": round(min(conf, 0.99), 2),
        "rationale": f"Rule-based: passed {score}/{maxs} Graham criteria; "
                     f"margin of safety {mos}; news sentiment {news_sentiment:.2f}.",
    }


def analyze(ticker: str, db=None) -> dict:
    """Full pipeline for one ticker: ensure data, screen, verdict, persist a run."""
    f = ingest.load_fundamentals(ticker, db=db)
    if f is None:
        f = ingest.update_fundamentals(ticker, db=db)

    result = graham.score(f)

    with connect(db) as conn:
        rows = conn.execute(
            "SELECT sentiment FROM news WHERE ticker=? ORDER BY published DESC LIMIT 20",
            (ticker,),
        ).fetchall()
    sentiments = [r["sentiment"] for r in rows if r["sentiment"] is not None]
    avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0.0

    verdict = synthesize(ticker, result, avg_sent)

    with connect(db) as conn:
        conn.execute(
            """INSERT INTO analysis_runs
               (ticker, run_at, graham_score, graham_max, graham_detail_json,
                margin_of_safety, signal, confidence, rationale)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (ticker, utcnow(), result["score"], result["max"],
             json.dumps(result["rules"]), result.get("margin_of_safety"),
             verdict["signal"], verdict["confidence"], verdict["rationale"]),
        )
    return {**result, **verdict, "avg_news_sentiment": avg_sent}
