"""Option-statistical-linkage tests use only synthetic fixtures, never source archives."""
import json
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from scripts.polymarket_lagged_option_audit import (
    evaluate,
    permutation_pvalue,
    rank_average,
    read_spy_lag_candidates,
    spearman,
)


def spy_line(day, capture, rr=-0.04, sigma=0.16):
    return json.dumps({
        "exchange_date": day, "captured_ts": capture, "created_ts": capture + 1,
        "option": {
            "proxy": "SPY", "demo": False, "expiry": day,
            "skew": {"rr": rr}, "implied_move": {"sigma_annual": sigma},
        },
    })


def spy_zip(path, lines):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("timing_excluded.jsonl", "\n".join(lines) + "\n")


def quote(day="2026-10-01", y_bid=0.69, y_ask=0.71, n_bid=0.29, n_ask=0.31):
    date = datetime.fromisoformat(day + "T14:02:00").replace(
        tzinfo=ZoneInfo("America/New_York"))
    now = round(date.timestamp() * 1_000_000)
    return {
        "market_slug": f"spx-up-or-down-on-{date.strftime('%B').lower()}-{date.day}-{date.year}",
        "timestamp_utc": str(now),
        "yes_quote_time": str(now - 500_000),
        "no_quote_time": str(now - 500_000),
        "yes_bid": str(y_bid), "yes_ask": str(y_ask),
        "no_bid": str(n_bid), "no_ask": str(n_ask),
    }


def spx_reference(path):
    path.write_text(
        "date,actual_outcome\n"
        "2026-09-30,Down\n"
        "2026-10-01,Up\n"
        "2026-10-02,Down\n",
        encoding="utf-8",
    )


def test_last_prior_session_snapshot_selected_and_not_current_day(tmp_path):
    p = tmp_path / "spy.zip"
    spy_zip(p, [spy_line("2026-09-30", 100, rr=-.05),
                spy_line("2026-09-30", 200, rr=-.03),
                spy_line("2026-10-01", 300, rr=-.01)])
    candidates = read_spy_lag_candidates(p)
    assert candidates["2026-09-30"]["rr"] == pytest.approx(-.03)


def test_only_previous_trading_day_is_joined(tmp_path):
    spy = tmp_path / "spy.zip"
    ref = tmp_path / "spx.csv"
    spx_reference(ref)
    previous = datetime(2026, 9, 30, 15, tzinfo=ZoneInfo("America/New_York")).timestamp()
    spy_zip(spy, [spy_line("2026-09-30", previous, rr=-.075),
                  spy_line("2026-10-01", previous + 86400, rr=.10)])
    result = evaluate(pm_rows=[quote()], spy_archive=spy, reference_daily=ref)
    assert result["independent_matched_market_days"] == 1
    assert result["option_quote_asof"] == "UNVERIFIED_PROVIDER_TIMESTAMP"
    assert result["strategy_return_proven"] is False
    assert result["option_basket_pnl_proven"] is False


def test_fail_closed_when_record_created_after_decision(tmp_path):
    spy = tmp_path / "spy.zip"
    ref = tmp_path / "spx.csv"
    spx_reference(ref)
    decision = datetime(2026, 10, 1, 14, 2,
                        tzinfo=ZoneInfo("America/New_York")).timestamp()
    # Even though labeled as Sept 30, this record was written on Oct 1 after
    # the Polymarket decision; time gate must reject it.
    spy_zip(spy, [spy_line("2026-09-30", decision + 60)])
    result = evaluate(pm_rows=[quote()], spy_archive=spy, reference_daily=ref)
    assert result["independent_matched_market_days"] == 0


def test_no_leak_current_day_and_missing_previous_day(tmp_path):
    spy = tmp_path / "spy.zip"
    ref = tmp_path / "spx.csv"
    spx_reference(ref)
    previous = datetime(2026, 10, 1, 13,
                        tzinfo=ZoneInfo("America/New_York")).timestamp()
    spy_zip(spy, [spy_line("2026-10-01", previous)])
    result = evaluate(pm_rows=[quote()], spy_archive=spy, reference_daily=ref)
    assert result["independent_matched_market_days"] == 0


def test_permutation_pvalue_bounds_and_spearman_sign():
    assert rank_average([1, 2, 2, 3]) == [1, 2.5, 2.5, 4]
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1, 1, 1], [1, 2, 3]) is None
    p = permutation_pvalue([1, 2, 3, 4, 5], [5, 1, 4, 2, 3],
                           repetitions=199, seed=17)
    assert p is not None and 0 < p <= 1
    assert permutation_pvalue([1, 1, 1], [1, 2, 3]) is None


def test_reject_negative_scenario_fee(tmp_path):
    spy = tmp_path / "spy.zip"
    ref = tmp_path / "spx.csv"
    spx_reference(ref)
    spy_zip(spy, [])
    with pytest.raises(ValueError):
        evaluate(pm_rows=[], spy_archive=spy, reference_daily=ref,
                 fee_rate_scenario=-0.01)
