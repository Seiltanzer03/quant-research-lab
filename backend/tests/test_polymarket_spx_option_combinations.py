"""Offline tests for option-combination research; never require private quotes."""
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from scripts.polymarket_spx_option_combinations import (
    SPEC,
    _design,
    exact_signflip_p,
    load_private_daily,
    summarize,
    walk_forward,
)


def fixture_days(n=20):
    idx = pd.bdate_range("2026-09-29", periods=n)
    return pd.DataFrame(
        [
            {
                "date": str(day.date()),
                "skew_rr": -0.055 + i * 0.001,
                "atm_iv": 0.12 + (i % 6) * 0.003,
                "term_slope": 0.25 + (i % 8) * 0.03,
                "pm_yes_mid": 0.3 + (i % 5) * 0.1,
                "pm_yes_ask": 0.31 + (i % 5) * 0.1,
                "pm_no_ask": 0.71 - (i % 5) * 0.1,
                "actual_up": int(i % 3 == 0),
                "expiry": "2026-10-16",
                "is_0dte": False,
                "ctx_source_age_minutes": 25.0,
                "source_asof_verified": False,
                "created_ts": 1000.0 + 86400.0 * i,
                "pm_decision_ts": 1000.0 + 86400.0 * i + 900,
            }
            for i, day in enumerate(idx)
        ]
    )


def test_first_prediction_never_uses_future_outcomes():
    original = fixture_days()
    original_preds = walk_forward(original)
    tampered = original.copy()
    tampered.loc[tampered.index >= 12, "actual_up"] = 1 - tampered.loc[
        tampered.index >= 12, "actual_up"
    ]
    revised = walk_forward(tampered)
    first = original_preds.loc[
        original_preds.model == "3_main_effects", "p_model"
    ].to_numpy()
    second = revised.loc[
        revised.model == "3_main_effects", "p_model"
    ].to_numpy()
    assert len(first) == 12
    assert np.allclose(first[:4], second[:4])


def test_scaling_does_not_use_current_test_feature():
    d = fixture_days()
    a, _ = _design(d.iloc[:8], d.iloc[8:9], SPEC["3_main_effects"])
    changed = d.copy()
    changed.loc[8, "atm_iv"] = 50
    b, _ = _design(changed.iloc[:8], changed.iloc[8:9], SPEC["3_main_effects"])
    assert np.allclose(a, b)


def test_zip_requires_a_single_event_per_day(tmp_path):
    d = fixture_days()
    p = tmp_path / "private.zip"
    with ZipFile(p, "w") as z:
        z.writestr(
            "research/tables/fixed_10am_snapshot_pm_15m_later.csv",
            d.to_csv(index=False),
        )
    assert len(load_private_daily(p)) == 20
    d.loc[1, "date"] = d.loc[0, "date"]
    with ZipFile(p, "w") as z:
        z.writestr(
            "research/tables/fixed_10am_snapshot_pm_15m_later.csv",
            d.to_csv(index=False),
        )
    with pytest.raises(ValueError, match="one event"):
        load_private_daily(p)


def test_summary_never_claims_verified_edge():
    d = fixture_days()
    preds = walk_forward(d)
    comparison = summarize(preds)
    assert len(comparison) == len(SPEC)
    assert (comparison.independent_days == 12).all()
    assert preds.source_asof_verified.eq(False).all()
    assert np.isfinite(comparison.model_brier).all()


def test_one_day_cannot_give_significance():
    assert exact_signflip_p([0.01, -0.01]) == pytest.approx(1.0)
