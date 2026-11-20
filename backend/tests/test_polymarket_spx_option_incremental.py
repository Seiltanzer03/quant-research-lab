"""All test data are synthetic. No private option history or trading APIs needed."""
import numpy as np
import pandas as pd
import pytest

from scripts.polymarket_spx_option_incremental import (
    odds_logit,
    ridge_offset_fit,
    score_and_trades,
    sigmoid,
    walk_forward,
)


def sample_days(n=14):
    dates = pd.date_range("2026-09-01", periods=n, freq="B")
    rows = []
    for i, date in enumerate(dates):
        rows.append({
            "date": str(date.date()), "pm_yes_mid": 0.25 + .035 * (i % 10),
            "pm_yes_ask": 0.26 + .035 * (i % 10),
            "pm_no_ask": 0.76 - .035 * (i % 10),
            "y": int(i % 3 == 1), "iv": 0.12 + .004 * i,
            "skew": -.045 - .0003 * i, "skew_valid": True,
            "provider_quote_asof_verified": False,
        })
    return pd.DataFrame(rows)


def test_sigmoid_logit_invert_clipped_probabilities():
    x = np.array([.1, .3, .7, .95])
    assert np.allclose(sigmoid(odds_logit(x)), x, atol=1e-10)


def test_offset_only_ridge_is_finite():
    p = np.array([.2, .4, .6, .8])
    y = np.array([0, 1, 1, 0])
    beta = ridge_offset_fit(p, y, np.empty((4, 0)))
    assert beta.shape == (1,)
    assert np.isfinite(beta).all()


def test_walk_forward_uses_only_past_labels():
    a = sample_days()
    initial = walk_forward(a, ["iv"], min_train=8)
    tampered = a.copy()
    tampered.loc[tampered.index >= 12, "y"] = 1 - tampered.loc[
        tampered.index >= 12, "y"
    ]
    after = walk_forward(tampered, ["iv"], min_train=8)
    assert len(initial) == 6
    assert np.allclose(
        initial.iloc[:4].p_model.to_numpy(),
        after.iloc[:4].p_model.to_numpy(),
        atol=1e-12,
    )


def test_missing_skew_not_promoted_to_true_zero():
    data = sample_days()
    data.loc[9, ["skew", "skew_valid"]] = [0.0, False]
    # Eight valid history days only; no prediction on malformed day.
    predictions = walk_forward(data, ["skew"], min_train=8)
    assert data.iloc[9].date not in set(predictions.date)


def test_no_trade_at_market_mid_after_spread_and_fee():
    d = sample_days(1)
    d["p_model"] = d.pm_yes_mid
    result = score_and_trades(d)
    assert result["trades"] == []
    assert result["total_net_one_share_per_trade"] == 0
    assert result["status"] == "RESEARCH_ONLY_NO_VERIFIED_EDGE"


def test_net_expected_edge_triggers_only_after_ask_cost_and_margin():
    d = sample_days(1)
    d["p_model"] = .92
    d["y"] = 1
    d["pm_yes_mid"] = .7
    d["pm_yes_ask"] = .71
    d["pm_no_ask"] = .31
    result = score_and_trades(d)
    assert result["trades"][0]["side"] == "YES"
    assert result["trades"][0]["pnl_usdc_per_share_scenario"] == pytest.approx(
        1 - .71 - .04 * .71 * .29, abs=1e-6
    )


def test_probabilistic_edge_not_claimed_even_if_backtest_wins():
    d = sample_days()
    d["p_model"] = np.clip(d.pm_yes_mid + .05, .01, .99)
    out = score_and_trades(d)
    assert out["option_quote_timestamps_verified"] is False
    assert out["status"] == "RESEARCH_ONLY_NO_VERIFIED_EDGE"
