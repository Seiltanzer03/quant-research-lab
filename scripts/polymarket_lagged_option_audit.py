#!/usr/bin/env python3
"""Exploratory option-feature linkage to SPX Polymarket, causally lagged by a session.

Uses local, PRIVATE H2 and SPY/Seiltanzer exports, never modifies either source.
Retains only the last SPY snapshot saved on the *previous SPX trading day*
before a frozen 14:01-14:05 NY Polymarket quote. The original SPY quote-as-of
is unverified: results are retrospective diagnostics, NOT a tradable backtest.
No threshold search, trading orders, or external API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import zipfile
from pathlib import Path

from scripts.polymarket_spx_parity_audit import input_rows
from scripts.polymarket_spx_resolution_baselines import (
    choose_fixed_snapshots,
    load_reference_outcomes,
    market_day,
)


def _real(value):
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return x if math.isfinite(x) else None


def read_spy_lag_candidates(archive):
    """One last immutable (captured and persisted) SPY snapshot per NY day."""
    last_by_day = {}
    with zipfile.ZipFile(archive) as z:
        with z.open("timing_excluded.jsonl") as stream:
            for line in stream:
                r = json.loads(line)
                day = r.get("exchange_date")
                opt = r.get("option") or {}
                skew = opt.get("skew") or {}
                move = opt.get("implied_move") or {}
                capture, stored = _real(r.get("captured_ts")), _real(r.get("created_ts"))
                rr, sigma = _real(skew.get("rr")), _real(move.get("sigma_annual"))
                if not day or opt.get("proxy") != "SPY" or opt.get("demo") is not False:
                    continue
                if any(v is None for v in (capture, stored, rr, sigma)):
                    continue
                if not (0 < sigma < 3 and abs(rr) < 3 and capture <= stored):
                    continue
                old = last_by_day.get(day)
                if old is None or (stored, capture) > (old["stored"], old["captured"]):
                    last_by_day[day] = {
                        "captured": capture, "stored": stored, "rr": rr,
                        "sigma": sigma, "expiry": opt.get("expiry"),
                    }
    return last_by_day


def read_reference_trading_dates(path):
    """Use the reference archive only for calendar/outcome labels, never features."""
    import csv

    dates = set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "date" not in (reader.fieldnames or []):
            raise ValueError("reference daily file missing date")
        for row in reader:
            if row.get("date"):
                dates.add(row["date"])
    return sorted(dates)


def rank_average(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    pos = 0
    while pos < len(order):
        end = pos + 1
        while end < len(order) and values[order[end]] == values[order[pos]]:
            end += 1
        rank = (pos + 1 + end) / 2
        for i in order[pos:end]:
            ranks[i] = rank
        pos = end
    return ranks


def spearman(x, y):
    if len(x) != len(y) or len(x) < 3:
        return None
    a, b = rank_average(x), rank_average(y)
    mean_a, mean_b = statistics.mean(a), statistics.mean(b)
    da = [v - mean_a for v in a]
    db = [v - mean_b for v in b]
    den = math.sqrt(sum(t * t for t in da) * sum(t * t for t in db))
    if den <= 0:
        return None
    return sum(u * v for u, v in zip(da, db, strict=True)) / den


def permutation_pvalue(x, y, *, repetitions=9999, seed=42):
    """Descriptive 2-sided permutation, not a forward/OOS significance test."""
    observed = spearman(x, y)
    if observed is None:
        return None
    rng = random.Random(seed)
    ycopy = list(y)
    extreme = 0
    for _ in range(repetitions):
        rng.shuffle(ycopy)
        corr = spearman(x, ycopy)
        if corr is not None and abs(corr) >= abs(observed) - 1e-12:
            extreme += 1
    return (extreme + 1) / (repetitions + 1)


def evaluate(*, pm_rows, spy_archive, reference_daily, fee_rate_scenario=0.04):
    if fee_rate_scenario < 0:
        raise ValueError("fee must be nonnegative")
    selected = choose_fixed_snapshots(pm_rows)
    opts = read_spy_lag_candidates(spy_archive)
    dates = read_reference_trading_dates(reference_daily)
    previous_day = dict(zip(dates[1:], dates[:-1], strict=True))
    labels = load_reference_outcomes(reference_daily)
    joined = []
    for slug, (when_us, yes_mid, yes_ask, no_mid, no_ask) in selected.items():
        day = market_day(slug)
        prior = previous_day.get(day)
        op = opts.get(prior)
        if op is None:
            continue
        decision_ts = when_us / 1_000_000
        if op["stored"] >= decision_ts:
            continue
        if day not in labels or labels[day] not in ("Up", "Down"):
            continue
        favorite_yes = yes_mid >= no_mid
        win = int((labels[day] == "Up") == favorite_yes)
        price = yes_ask if favorite_yes else no_ask
        result_net = win - price - fee_rate_scenario * price * (1 - price)
        joined.append({
            "date": day, "rr": op["rr"], "sigma": op["sigma"],
            "yes_mid": yes_mid, "favorite_net": result_net,
            "favorite_win": win,
        })
    joined.sort(key=lambda row: row["date"])
    correlations = {}
    tests = [("rr", "yes_mid"), ("rr", "favorite_net"),
             ("sigma", "yes_mid"), ("sigma", "favorite_net")]
    for feature, outcome in tests:
        x = [row[feature] for row in joined]
        y = [row[outcome] for row in joined]
        rho = spearman(x, y)
        p = permutation_pvalue(x, y) if rho is not None else None
        correlations[f"{feature}_vs_{outcome}"] = {
            "spearman_rho": round(rho, 6) if rho is not None else None,
            "permutation_p_exploratory": p,
            "bonferroni_4_tests": min(1.0, p * len(tests)) if p is not None else None,
        }
    return {
        "protocol": "polymarket-spx-lagged-options-descriptive-v1",
        "status": "EXPLORATORY_ONLY_NO_VERIFIED_EDGE",
        "data_scope": "prior-trading-day SPY captures vs fixed-time Polymarket quotes",
        "timing_policy": "prior SPX reference trading day and stored-before-decision",
        "option_quote_asof": "UNVERIFIED_PROVIDER_TIMESTAMP",
        "polymarket_resolution": "SPX_REFERENCE_OUTCOMES_NOT_POLYMARKET_VERIFIED",
        "option_historical_bid_ask": "NOT_AVAILABLE_IN_THIS_ARCHIVE",
        "fee_model": f"SCENARIO_ONLY coefficient={fee_rate_scenario}",
        "model_selection": "NO_FITTING_OR_THRESHOLD_OPTIMIZATION",
        "independent_matched_market_days": len(joined),
        "polymarket_days_with_fixed_time_quotes": len(selected),
        "spy_days_with_lag_candidate": len(opts),
        "correlations": correlations,
        "strategy_return_proven": False,
        "option_basket_pnl_proven": False,
        "new_untouched_oos": False,
    }


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(2**20), b""):
            h.update(data)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--pm-h2-zip", type=Path, required=True)
    p.add_argument("--spy-zip", type=Path, required=True)
    p.add_argument("--reference-spx-daily", type=Path, required=True)
    p.add_argument("--fee-rate-scenario", type=float, default=0.04)
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    result = evaluate(
        pm_rows=input_rows([args.pm_h2_zip]), spy_archive=args.spy_zip,
        reference_daily=args.reference_spx_daily,
        fee_rate_scenario=args.fee_rate_scenario,
    )
    result["source_sha256"] = {
        name: _sha256(path) for name, path in (
            ("pm_h2_zip", args.pm_h2_zip), ("spy_zip", args.spy_zip),
            ("spx_daily", args.reference_spx_daily))
    }
    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(output, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
