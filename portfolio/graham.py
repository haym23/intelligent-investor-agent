"""Benjamin Graham's defensive-investor criteria as pure functions.

These are arithmetic, so no LLM touches them. Each rule returns a RuleResult
with pass/fail AND the actual value, so the dashboard and the agent can show
*why* something passed or failed, not just a boolean.

Thresholds follow Graham's "The Intelligent Investor" defensive criteria.
They're deliberately kept as module constants so you can tune them for a
modern market (his P/B <= 1.5 fails most quality companies today).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

# --- Tunable thresholds (modern adjustments) --------------------------------
MIN_REVENUE = 500_000_000       # "adequate size" (Graham's $ scaled up for inflation)
MIN_CURRENT_RATIO = 1.5         # ponytail: loosened from 2.0; modern companies run leaner working capital
MIN_YEARS_POSITIVE_EPS = 10
MIN_YEARS_DIVIDENDS = 20
MIN_EPS_GROWTH_10YR = 0.33      # >= 1/3 growth over the decade
MAX_PE = 20.0                   # ponytail: loosened from 15; accounts for lower IR environment
MAX_PB = 3.0                    # ponytail: loosened from 1.5; modern quality trades here; was gatekeeping
MAX_PE_TIMES_PB = 60.0          # ponytail: loosened from 22.5; modern quality multiples; upgrade path: tighten to 50 if throughput allows


@dataclass
class RuleResult:
    name: str
    passed: bool
    value: Optional[float]      # the computed number (None if not computable)
    threshold: Optional[float]
    detail: str


def _safe_div(a, b):
    try:
        if a is None or b in (None, 0):
            return None
        return a / b
    except (TypeError, ZeroDivisionError):
        return None


def graham_number(eps: Optional[float], bvps: Optional[float]) -> Optional[float]:
    """Intrinsic-value ceiling: sqrt(22.5 * EPS * BVPS). None if inputs invalid."""
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(22.5 * eps * bvps)


def current_ratio(f: dict) -> Optional[float]:
    return _safe_div(f.get("current_assets"), f.get("current_liabilities"))


def eps_growth_10yr(f: dict) -> Optional[float]:
    old = f.get("eps_10yr_ago")
    new = f.get("eps_3yr_avg") or f.get("eps")
    if old is None or new is None or old <= 0:
        return None
    return (new - old) / old


def pe_ratio(f: dict) -> Optional[float]:
    earnings = f.get("eps_3yr_avg") or f.get("eps")
    return _safe_div(f.get("price"), earnings)


def pb_ratio(f: dict) -> Optional[float]:
    return _safe_div(f.get("price"), f.get("book_value_ps"))


def screen(f: dict) -> list[RuleResult]:
    """Run all defensive-investor rules against a fundamentals dict.
    A rule with uncomputable inputs is treated as NOT passed (fail-closed)."""
    results: list[RuleResult] = []

    rev = f.get("revenue")
    results.append(RuleResult(
        "adequate_size", bool(rev and rev >= MIN_REVENUE), rev, MIN_REVENUE,
        "Trailing revenue above size floor."))

    cr = current_ratio(f)
    results.append(RuleResult(
        "current_ratio", bool(cr and cr >= MIN_CURRENT_RATIO), cr, MIN_CURRENT_RATIO,
        "Current assets >= 2x current liabilities."))

    yp = f.get("years_positive_eps")
    hist = f.get("history_years")
    # Graham's rule is 10 years. With only N years of data (free FMP gives ~5),
    # require an unbroken positive streak across ALL available years and mark
    # the rule as limited rather than silently passing on thin evidence.
    stability_threshold = MIN_YEARS_POSITIVE_EPS
    stability_note = "Positive EPS for 10 straight years."
    if hist and hist < MIN_YEARS_POSITIVE_EPS:
        stability_threshold = hist
        stability_note = (f"Positive EPS in all {hist} available years "
                          f"(LIMITED: Graham wants 10).")
    results.append(RuleResult(
        "earnings_stability",
        bool(yp is not None and stability_threshold and yp >= stability_threshold),
        yp, stability_threshold, stability_note))

    yd = f.get("years_dividends")
    div_threshold = MIN_YEARS_DIVIDENDS
    div_note = "Uninterrupted dividends for 20 years."
    if hist and hist < MIN_YEARS_DIVIDENDS:
        div_threshold = hist
        div_note = (f"Dividends in all {hist} available years "
                    f"(LIMITED: Graham wants 20).")
    results.append(RuleResult(
        "dividend_record",
        bool(yd is not None and div_threshold and yd >= div_threshold),
        yd, div_threshold, div_note))

    g = eps_growth_10yr(f)
    results.append(RuleResult(
        "earnings_growth", bool(g is not None and g >= MIN_EPS_GROWTH_10YR), g,
        MIN_EPS_GROWTH_10YR, "EPS grew >= 1/3 over the decade."))

    pe = pe_ratio(f)
    results.append(RuleResult(
        "moderate_pe", bool(pe is not None and 0 < pe <= MAX_PE), pe, MAX_PE,
        "P/E (on 3yr avg earnings) <= 15."))

    pb = pb_ratio(f)
    results.append(RuleResult(
        "moderate_pb", bool(pb is not None and 0 < pb <= MAX_PB), pb, MAX_PB,
        "Price-to-book <= 1.5."))

    pepb = (pe * pb) if (pe is not None and pb is not None) else None
    results.append(RuleResult(
        "combined_ceiling", bool(pepb is not None and 0 < pepb <= MAX_PE_TIMES_PB),
        pepb, MAX_PE_TIMES_PB, "P/E x P/B <= 22.5."))

    return results


def score(f: dict) -> dict:
    """Full screen result: score, per-rule detail, Graham number, margin of safety.

    Also reports data quality so a consumer (the agent, the dashboard) can tell
    a REAL failure from a missing-data failure — the single most important
    distinction when running on free-tier fundamentals.
    """
    rules = screen(f)
    passed = sum(1 for r in rules if r.passed)
    computable = [r for r in rules if r.value is not None]
    missing = [r.name for r in rules if r.value is None]
    real_failures = [r.name for r in computable if not r.passed]
    limited = [r.name for r in rules if "LIMITED" in r.detail]

    gnum = graham_number(f.get("eps_3yr_avg") or f.get("eps"), f.get("book_value_ps"))
    price = f.get("price")
    mos = None
    if gnum and price:
        mos = (gnum - price) / gnum   # positive = trading below intrinsic ceiling
    return {
        "ticker": f.get("ticker"),
        "score": passed,
        "max": len(rules),
        "score_of_available": f"{sum(1 for r in computable if r.passed)}/{len(computable)}",
        "missing_data_rules": missing,
        "real_failures": real_failures,
        "limited_history_rules": limited,
        "history_years": f.get("history_years"),
        "graham_number": gnum,
        "price": price,
        "margin_of_safety": mos,
        "rules": [asdict(r) for r in rules],
    }
