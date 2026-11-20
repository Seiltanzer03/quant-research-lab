"""Fixed-time settlement development baselines never become prospective OOS."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from scripts.polymarket_spx_resolution_baselines import (
    block_ci, choose_fixed_snapshots, eligible_record, evaluate, market_day,
)


NY = ZoneInfo("America/New_York")


def snapshot(day="2026-09-01", hour=14, minute=1, **overrides):
    t = int(datetime.fromisoformat(f"{day}T{hour:02d}:{minute:02d}:00")
            .replace(tzinfo=NY).timestamp() * 1_000_000)
    month = datetime.fromisoformat(day).strftime("%B").lower()
    row = {"market_slug": f"spx-up-or-down-on-{month}-{int(day[-2:])}-{day[:4]}",
           "timestamp_utc": str(t), "yes_quote_time": str(t-500_000),
           "no_quote_time": str(t-500_000), "yes_bid": ".29",
           "yes_ask": ".31", "no_bid": ".67", "no_ask": ".69"}
    row.update({k: str(v) for k, v in overrides.items()})
    return row


def test_reference_slug_must_be_spx_close_contract():
    assert market_day("spx-up-or-down-on-september-1-2026") == "2026-09-01"
    with pytest.raises(ValueError):
        market_day("spx-opens-up-or-down-on-september-1-2026")


def test_entry_is_at_fixed_ny_time_not_future_or_stale():
    assert eligible_record(snapshot()) is not None
    assert eligible_record(snapshot(minute=0)) is None
    assert eligible_record(snapshot(hour=15)) is None
    assert eligible_record(snapshot(yes_quote_time="0")) is None


def test_select_earliest_asof_quote_per_daily_market():
    rows = [snapshot(minute=3, yes_ask=".35"),
            snapshot(minute=1, yes_ask=".31")]
    selected = choose_fixed_snapshots(rows)
    assert len(selected) == 1
    assert next(iter(selected.values()))[2] == pytest.approx(.31)


def test_favorite_and_underdog_frozen_net_to_reference_settlement():
    labels = {"2026-09-01": "Down"}
    r = evaluate([snapshot()], labels, fee_rate=.04)
    assert r["edge_verified"] is False
    fav = r["strategies"]["favorite"]["train"]
    dog = r["strategies"]["underdog"]["train"]
    assert fav["market_days"] == 1
    assert fav["mean_net_usd_per_share"] == pytest.approx(1-.69-.04*.69*.31)
    assert dog["mean_net_usd_per_share"] == pytest.approx(-.31-.04*.31*.69)
    assert r["status"] == "EXPLORATORY_ONLY_NOT_OOS"


def test_unknown_labels_and_duplicate_quotes_fail_closed():
    r = evaluate([snapshot()], {}, fee_rate=.04)
    assert r["outcome_labeled_market_days"] == 0
    with pytest.raises(ValueError, match="duplicate"):
        evaluate([snapshot(), snapshot()], {"2026-09-01": "Up"})


def test_bootstrap_market_day_requires_at_least_five_independent_days():
    assert block_ci([1, 1, 1, 1]) is None
    assert block_ci([1]*5) == pytest.approx([1., 1.])


def test_negative_fee_rate_is_not_allowed():
    with pytest.raises(ValueError):
        evaluate([], {}, fee_rate=-1)
