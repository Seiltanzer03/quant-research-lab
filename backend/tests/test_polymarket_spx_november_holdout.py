import numpy as np
import pandas as pd

from scripts.polymarket_spx_november_holdout import fit_frozen, score_direction


def prior_days():
    return pd.DataFrame([
        {
            "date": str(day.date()),
            "skew_rr": -.048 - .0005 * i,
            "atm_iv": .11 + .002 * (i % 6),
            "term_slope": .2 + .03 * (i % 7),
            "pm_yes_mid": .3 + .1 * (i % 4),
            "actual_up": int(i % 3 == 0),
        }
        for i, day in enumerate(pd.bdate_range("2026-09-29", periods=20))
    ])


def test_fit_never_uses_november_outcome_or_option_levels():
    old = prior_days()
    beta1, mu1, sd1 = fit_frozen(old, (0, 1, 2))
    nov = pd.DataFrame([
        {"skew_rr": -.3, "atm_iv": .5, "term_slope": -2,
         "actual_up": 1}
    ])
    adjust1 = score_direction(nov, old, (0, 1, 2))
    nov.loc[0, "actual_up"] = 0
    adjust2 = score_direction(nov, old, (0, 1, 2))
    beta2, mu2, sd2 = fit_frozen(old, (0, 1, 2))
    assert np.allclose(beta1, beta2)
    assert np.allclose(mu1, mu2)
    assert np.allclose(sd1, sd2)
    assert np.allclose(adjust1, adjust2)


def test_cannot_fit_with_dates_after_original_training_end():
    prior = prior_days()
    prior.loc[19, "date"] = "2026-11-19"
    try:
        fit_frozen(prior, (0, 1, 2))
        raise AssertionError("Expected a temporal leakage guard")
    except ValueError:
        pass


def test_frozen_tilt_uses_only_frozen_feature_scaling():
    prior = prior_days()
    nov = pd.DataFrame([
        {"skew_rr": -.08, "atm_iv": .21, "term_slope": .2},
        {"skew_rr": -.09, "atm_iv": .23, "term_slope": .1},
    ])
    full = score_direction(nov, prior, (0, 1, 2))
    part = score_direction(nov.iloc[:1], prior, (0, 1, 2))
    assert np.allclose(full[0], part[0])
