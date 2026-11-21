#!/usr/bin/env python3
"""Retrospective November SPY option odds-tilt diagnostic.

Uses private archived Seiltanzer feature exports and prior 20-day frozen input.
Does NOT obtain Polymarket prices or assert a true provider-quote as-of timestamp.
This only tests the *direction* of a frozen correction relative to later SPX closes.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from scripts.polymarket_spx_option_combinations import _fit

FEATURES = ("skew_rr", "atm_iv", "term_slope")
L2 = 8


def extract_november(options_zip: Path) -> pd.DataFrame:
    with ZipFile(options_zip) as archive:
        df = pd.read_csv(
            io.BytesIO(archive.read("options_history.csv")), encoding="utf-8-sig"
        )
    df = df.loc[
        (df.record_type == "trades_observation")
        & df.date_et.between("2026-11-04", "2026-11-20")
    ].copy()
    t = pd.to_datetime(df.snapshot_et).dt.tz_localize(None)
    df["_time"] = t
    df = df.loc[(t.dt.hour >= 10) & (t.dt.hour < 14)]
    df = df.sort_values(["date_et", "_time", "snapshot_id"]).drop_duplicates(
        "date_et", keep="first"
    )
    if df[list(FEATURES)].isna().any().any():
        raise ValueError("Missing ATM IV / RR / term slope")
    if df.option_quote_time_verified.fillna(False).any():
        raise ValueError("This audit expects UNVERIFIED option source timestamps")
    return df.reset_index(drop=True)


def fit_frozen(prior: pd.DataFrame, keys: tuple[int, ...]):
    """No November features or outcomes enter training/scaling."""
    if prior.date.max() > "2026-10-28":
        raise ValueError("Expected September/October training cohort only")
    if len(prior) != 20 or prior.date.nunique() != 20:
        raise ValueError("Expected 20 independent original training days")
    x = prior[list(FEATURES)].to_numpy(float)
    mu = x.mean(axis=0)
    sd = np.maximum(x.std(axis=0), [0.005, 0.005, 0.05])
    standardized = (x - mu) / sd
    A = np.column_stack([np.ones(len(x)), standardized[:, keys]])
    # Legacy fit from our previous risk study has frozen L2 penalty 8.
    beta = _fit(prior.pm_yes_mid.to_numpy(), prior.actual_up.to_numpy(), A, penalty=L2)
    return beta, mu, sd


def score_direction(nov: pd.DataFrame, prior: pd.DataFrame, keys):
    beta, mu, sd = fit_frozen(prior, keys)
    z = (nov[list(FEATURES)].to_numpy(float) - mu) / sd
    return beta[0] + z[:, keys] @ beta[1:]


def evaluate(options_zip: Path, prior_csv: Path, spx_csv: Path):
    prior = pd.read_csv(prior_csv)
    nov = extract_november(options_zip)
    spx = pd.read_csv(spx_csv).sort_values("date")
    spx["prior_close"] = spx.close.shift(1)
    spx["up"] = (spx.close > spx.prior_close).astype(int)
    nov = nov.merge(
        spx[["date", "close", "prior_close", "up"]],
        left_on="date_et", right_on="date",
        how="left", validate="one_to_one"
    )
    if nov.up.isna().any():
        raise ValueError("No SPX reference label for a selected November day")
    for name, keys in (
        ("three_main", (0, 1, 2)),
        ("skew_iv", (0, 1)),
    ):
        nov[name + "_logit_shift"] = score_direction(nov, prior, keys)
        nov[name + "_odds_multiplier"] = np.exp(nov[name + "_logit_shift"])
        nov[name + "_direction_helps"] = (
            nov[name + "_logit_shift"] * (2 * nov.up - 1) > 0
        )
    nov["stale_60m"] = (
        pd.to_numeric(nov.context_option_static_age_min, errors="coerce") > 60
    )
    summary = {
        "status": "RESEARCH_ONLY_NOT_VALIDATED",
        "november_selected_days": len(nov),
        "up_days_reference_spx": int(nov.up.sum()),
        "down_days_reference_spx": int((1 - nov.up).sum()),
        "three_main_tilts_yes_days": int((nov.three_main_logit_shift > 0).sum()),
        "three_main_tilts_wrong_direction_days": int(
            (~nov.three_main_direction_helps).sum()
        ),
        "skew_iv_tilts_wrong_direction_days": int(
            (~nov.skew_iv_direction_helps).sum()
        ),
        "fresh_days": int((~nov.stale_60m).sum()),
        "fresh_wrong_direction_days": int(
            ((~nov.stale_60m) & (~nov.three_main_direction_helps)).sum()
        ),
        "genuine_option_quote_timestamps": int(
            nov.option_quote_time_verified.fillna(False).sum()
        ),
        "november_pm_ask_bid_data": False,
        "november_brier": None,
        "november_profit": None,
        "no_executable_edge_claim": True,
        "explanation": (
            "The sign of log-odds correction improves squared error versus "
            "the same unknown PM base probability if it agrees with the "
            "eventual outcome; it harms squared error if it disagrees. "
            "This is NOT a binary trading prediction or a PnL calculation."
        ),
    }
    return nov, summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--option-zip", type=Path, required=True)
    p.add_argument("--prior-20-csv", type=Path, required=True)
    p.add_argument("--spx-close-csv", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    nov, summary = evaluate(
        a.option_zip, a.prior_20_csv, a.spx_close_csv
    )
    a.out.mkdir(parents=True, exist_ok=True)
    display = ["date_et", "snapshot_et", "expiry_date", "atm_iv",
               "skew_rr", "term_slope", "context_option_static_age_min",
               "up", "three_main_logit_shift", "skew_iv_logit_shift",
               "three_main_direction_helps", "skew_iv_direction_helps"]
    nov[display].to_csv(a.out / "november_diagnostics.csv", index=False)
    (a.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
