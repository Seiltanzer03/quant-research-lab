"""Public SPX GEX audit tests use synthetic snapshots, not external data."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from scripts.polymarket_public_gex_audit import evaluate, gex_from_csv


def quote(day="2026-10-01"):
    at = datetime.fromisoformat(day + "T14:02:00").replace(
        tzinfo=ZoneInfo("America/New_York"))
    ts = int(at.timestamp() * 1e6)
    return {
        "market_slug": "spx-up-or-down-on-october-1-2026",
        "timestamp_utc": str(ts),
        "yes_quote_time": str(ts - 500_000),
        "no_quote_time": str(ts - 500_000),
        "yes_bid": ".69", "yes_ask": ".71",
        "no_bid": ".29", "no_ask": ".31",
    }


def test_research_uses_last_gex_not_after_1345(tmp_path):
    gex = tmp_path / "gex.csv"
    gex.write_text(
        "date,time,spot,net,peak_strike,gamma_flip\n"
        "2026-10-01,11:15,100,2,99,98\n"
        "2026-10-01,13:45,100,-4,99,99\n"
        "2026-10-01,14:00,100,500,97,101\n",
        encoding="utf-8",
    )
    out = gex_from_csv(gex)
    assert out["2026-10-01"]["net"] == -4
    assert out["2026-10-01"]["positive_gex"] == 0
    assert out["2026-10-01"]["flip_distance_bp"] == pytest.approx(100.0)


def test_one_day_stays_exploratory_and_cannot_claim_execution(tmp_path):
    gex = tmp_path / "gex.csv"
    outcome = tmp_path / "spx.csv"
    gex.write_text(
        "date,time,spot,net,peak_strike,gamma_flip\n"
        "2026-10-01,13:45,100,-4,99,99\n",
        encoding="utf-8",
    )
    outcome.write_text("date,actual_outcome\n2026-10-01,Up\n", encoding="utf-8")
    r = evaluate([quote()], gex, outcome)
    assert r["matched_pm_market_days"] == 1
    assert r["matched_quote_days"] == 1
    assert r["sign_summary"]["negative_or_zero"]["days"] == 1
    assert r["sign_summary"]["negative_or_zero"]["favorite_wins"] == 1
    assert r["exploratory_correlations"]["net_vs_favorite_net"]["rho"] is None
    assert r["net_statistical_edge_proven"] is False
    assert r["new_oos"] is False
    assert r["option_execution_bid_ask"] == "NOT_AVAILABLE"


def test_no_future_gamma_and_wrong_market_date_is_not_joined(tmp_path):
    gex = tmp_path / "gex.csv"
    outcome = tmp_path / "spx.csv"
    gex.write_text(
        "date,time,spot,net,peak_strike,gamma_flip\n"
        "2026-10-01,14:15,100,2,99,98\n",
        encoding="utf-8",
    )
    outcome.write_text("date,actual_outcome\n2026-10-01,Up\n", encoding="utf-8")
    r = evaluate([quote()], gex, outcome)
    assert r["matched_pm_market_days"] == 0


def test_duplicate_conflicting_public_sample_rejected(tmp_path):
    gex = tmp_path / "gex.csv"
    gex.write_text(
        "date,time,spot,net,peak_strike,gamma_flip\n"
        "2026-10-01,13:45,100,2,99,98\n"
        "2026-10-01,13:45,100,4,99,98\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="conflicting"):
        gex_from_csv(gex)
