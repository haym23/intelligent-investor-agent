"""Unit tests for the Graham screen — the payoff of keeping the math LLM-free.
Run: pytest -q
"""
import math
import pytest

from portfolio import graham


def test_graham_number_known_value():
    # sqrt(22.5 * 5 * 20) = sqrt(2250) = 47.4341649...
    assert graham.graham_number(5, 20) == pytest.approx(math.sqrt(2250))


def test_graham_number_invalid_inputs_return_none():
    assert graham.graham_number(None, 20) is None
    assert graham.graham_number(-1, 20) is None
    assert graham.graham_number(5, 0) is None


def test_current_ratio():
    assert graham.current_ratio({"current_assets": 200, "current_liabilities": 100}) == 2.0
    assert graham.current_ratio({"current_assets": 200, "current_liabilities": 0}) is None


def test_eps_growth():
    assert graham.eps_growth_10yr({"eps_10yr_ago": 3, "eps_3yr_avg": 4}) == pytest.approx(1/3)
    assert graham.eps_growth_10yr({"eps_10yr_ago": 0, "eps_3yr_avg": 4}) is None


def test_screen_all_pass():
    f = {
        "ticker": "GOOD",
        "revenue": 1_000_000_000,
        "current_assets": 300, "current_liabilities": 100,   # ratio 3
        "eps": 10, "eps_3yr_avg": 10, "eps_10yr_ago": 5,     # +100% growth
        "book_value_ps": 100, "price": 120,                   # P/E 12, P/B 1.2
        "years_positive_eps": 12, "years_dividends": 25,
    }
    result = graham.score(f)
    assert result["score"] == result["max"] == 8


def test_screen_fails_closed_on_missing_data():
    # Empty fundamentals: nothing computable, nothing passes.
    result = graham.score({"ticker": "EMPTY"})
    assert result["score"] == 0
    assert result["max"] == 8


def test_margin_of_safety_positive_when_cheap():
    f = {"ticker": "CHEAP", "eps_3yr_avg": 5, "book_value_ps": 20, "price": 30}
    # graham number ~47.4, price 30 -> positive MoS
    result = graham.score(f)
    assert result["margin_of_safety"] > 0


def test_combined_ceiling_rule():
    # P/E 20 * P/B 1.0 = 20 <= 22.5 -> passes combined even though P/E > 15 fails.
    f = {"ticker": "X", "eps_3yr_avg": 5, "book_value_ps": 100, "price": 100}
    rules = {r.name: r.passed for r in graham.screen(f)}
    assert rules["moderate_pe"] is False   # P/E 20 > 15
    assert rules["combined_ceiling"] is True


def test_limited_history_scales_thresholds():
    """With 5 years of data, stability rule requires 5 consecutive positive years."""
    f = {
        "ticker": "LTD", "revenue": 1e9,
        "current_assets": 300, "current_liabilities": 100,
        "eps": 10, "eps_3yr_avg": 10, "eps_10yr_ago": 5,
        "book_value_ps": 100, "price": 120,
        "years_positive_eps": 5, "years_dividends": 5,
        "history_years": 5,
    }
    rules = {r.name: r for r in graham.screen(f)}
    assert rules["earnings_stability"].passed is True
    assert rules["earnings_stability"].threshold == 5
    assert "LIMITED" in rules["earnings_stability"].detail
    assert rules["dividend_record"].passed is True


def test_limited_history_still_fails_on_broken_streak():
    f = {"ticker": "BRK", "years_positive_eps": 3, "history_years": 5,
         "years_dividends": 2}
    rules = {r.name: r for r in graham.screen(f)}
    assert rules["earnings_stability"].passed is False   # 3 < 5 available years
    assert rules["dividend_record"].passed is False


def test_score_separates_real_failures_from_missing_data():
    # P/B genuinely fails; several fields absent entirely.
    f = {"ticker": "MIX", "eps_3yr_avg": 5, "book_value_ps": 10, "price": 100}
    r = graham.score(f)
    assert "moderate_pb" in r["real_failures"]           # computable and failed
    assert "adequate_size" in r["missing_data_rules"]    # no revenue provided
    assert "moderate_pb" not in r["missing_data_rules"]


def test_full_history_uses_grahams_original_thresholds():
    f = {"ticker": "FULL", "years_positive_eps": 12, "years_dividends": 25,
         "history_years": 30}
    rules = {r.name: r for r in graham.screen(f)}
    assert rules["earnings_stability"].threshold == 10
    assert rules["dividend_record"].threshold == 20
    assert "LIMITED" not in rules["earnings_stability"].detail
