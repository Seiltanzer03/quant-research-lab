#!/usr/bin/env python3
"""Exploratory GEX×Polymarket statistical audit on INDEPENDENT market days.

External CBOE delayed-quote GEX archive: public GEX collector's NY local poll
time is not verified quote time, and archival GitHub publish time is unknown.
Never promote this to a live/as-of trading result. No network access or orders.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

from scripts.polymarket_lagged_option_audit import permutation_pvalue, spearman
from scripts.polymarket_spx_parity_audit import input_rows
from scripts.polymarket_spx_resolution_baselines import (
    choose_fixed_snapshots,
    load_reference_outcomes,
    market_day,
)

_FIXED_GEX_CUTOFF_ET = "13:45"
_N_TESTS = 4


def gex_from_csv(path):
    """Last archived 0DTE observation at/before 13:45 ET, per market date.

    13:45 allows a minimum 16-minute capture-to-PM window, not a proof of
    true provider quote freshness or public archival availability at 14:01.
    """
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = {"date", "time", "spot", "net", "peak_strike", "gamma_flip"}
        if not fields.issubset(reader.fieldnames or []):
            raise ValueError("public GEX CSV missing fields")
        for row in reader:
            day, hm = row["date"], row["time"]
            if not "09:30" <= hm <= _FIXED_GEX_CUTOFF_ET:
                continue
            try:
                spot, net, peak, flip = [float(row[key])
                                        for key in ("spot", "net", "peak_strike", "gamma_flip")]
            except (ValueError, TypeError):
                continue
            if not all(math.isfinite(x) for x in (spot, net, peak, flip)):
                continue
            if min(spot, peak, flip) <= 0:
                continue
            item = {
                "date": day, "time": hm, "net": net,
                "positive_gex": float(net > 0),
                "flip_distance_bp": 10_000 * (spot - flip) / spot,
                "peak_distance_bp": 10_000 * (spot - peak) / spot,
            }
            if day not in out or hm > out[day]["time"]:
                out[day] = item
            elif hm == out[day]["time"] and item != out[day]:
                raise ValueError(f"conflicting public GEX at {day} {hm}")
    return out


def evaluate(pm_rows, gex_path, outcomes_reference, *, fee_rate_scenario=0.04):
    if fee_rate_scenario < 0:
        raise ValueError("negative fee coefficient")
    gex = gex_from_csv(gex_path)
    pm = choose_fixed_snapshots(pm_rows)
    labels = load_reference_outcomes(outcomes_reference)
    rows = []
    for slug, (_, y_mid, y_ask, n_mid, n_ask) in pm.items():
        day = market_day(slug)
        f = gex.get(day)
        if not f or day not in labels:
            continue
        favorite_yes = y_mid >= n_mid
        win = int((labels[day] == "Up") == favorite_yes)
        price = y_ask if favorite_yes else n_ask
        rows.append({
            **f, "fav_net": win - price - fee_rate_scenario * price * (1 - price),
            "fav_win": win,
        })
    rows.sort(key=lambda r: r["date"])
    features = ["net", "positive_gex", "flip_distance_bp", "peak_distance_bp"]
    tests = {}
    for key in features:
        x = [row[key] for row in rows]
        y = [row["fav_net"] for row in rows]
        rho = spearman(x, y)
        p = permutation_pvalue(x, y) if rho is not None else None
        tests[key + "_vs_favorite_net"] = {
            "rho": round(rho, 6) if rho is not None else None,
            "permutation_p_exploratory": p,
            "bonferroni_4_tests": min(1.0, _N_TESTS * p) if p is not None else None,
        }
    by_sign = {}
    for direction in (0.0, 1.0):
        group = [r for r in rows if r["positive_gex"] == direction]
        by_sign["positive" if direction else "negative_or_zero"] = {
            "days": len(group), "favorite_wins": sum(x["fav_win"] for x in group),
            "mean_favorite_net_usdc": statistics.mean(r["fav_net"] for r in group)
            if group else None,
        }
    return {
        "protocol": "spx-public-0dte-gex-lagged-descriptive-v1",
        "status": "EXPLORATORY_ONLY_NO_VERIFIED_EDGE",
        "source": "Alexduanran/spx-0dte-archive gex/summary.csv",
        "source_method": "CBOE delayed options gamma + OI, approximated dealer GEX",
        "asof_limit": "poll time <=13:45 NY; GitHub publish timestamp and underlying quote timestamps not proven",
        "option_execution_bid_ask": "NOT_AVAILABLE",
        "pm_execution": "OBSERVED_ASK_NOT_PROVEN_FILL",
        "settlement_authority": "REFERENCE_SPX_NOT_VERIFIED_POLYMARKET",
        "fee_scenario_coefficient": fee_rate_scenario,
        "public_days_at_or_before_cutoff": len(gex),
        "matched_pm_market_days": len(rows),
        "matched_quote_days": len(pm),
        "sign_summary": by_sign,
        "exploratory_correlations": tests,
        "new_oos": False,
        "net_statistical_edge_proven": False,
    }


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for data in iter(lambda: f.read(1 << 20), b""):
            h.update(data)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--pm-h2-zip", type=Path, required=True)
    p.add_argument("--gex-csv", type=Path, required=True)
    p.add_argument("--reference-spx-daily", type=Path, required=True)
    p.add_argument("--fee-rate-scenario", type=float, default=.04)
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    result = evaluate(
        input_rows([args.pm_h2_zip]), args.gex_csv, args.reference_spx_daily,
        fee_rate_scenario=args.fee_rate_scenario,
    )
    result["input_sha256"] = {
        "pm_h2_zip": _sha(args.pm_h2_zip),
        "gex_csv": _sha(args.gex_csv),
        "reference_spx_daily": _sha(args.reference_spx_daily),
    }
    output = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    print(output, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
