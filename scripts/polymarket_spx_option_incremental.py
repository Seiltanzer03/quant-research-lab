#!/usr/bin/env python3
"""Retrospective, private-input-only SPX PM incremental IV/skew model.

Do not imply verified option quote timestamps or any live trading edge.
One selected event per NY market day; historical chronological expanding replay.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -45, 45)))


def odds_logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-8, 1 - 1e-8)
    return np.log(p / (1 - p))


def load_private_events(spy_zip, pm_clean_csv, reference_spx_daily, lag_minutes=15):
    """Select first stored option record per day; PM entry only AFTER persistence."""
    with zipfile.ZipFile(spy_zip) as archive:
        lines = archive.open("timing_excluded.jsonl")
        try:
            options = []
            for line in lines:
                raw = json.loads(line)
                option = raw["option"]
                if raw.get("instrument") != "SP500" or option.get("demo") is not False:
                    continue
                options.append({
                    "date": raw["exchange_date"],
                    "created": float(raw["created_ts"]),
                    "iv": float(option["implied_move"]["sigma_annual"]),
                    "skew": float(option["skew"]["rr"]),
                    "expiry": option["expiry"],
                    "strict_quote_asof": bool(raw.get("asof_timing_passed")),
                })
        finally:
            lines.close()
    if not options:
        raise ValueError("No real SPY option snapshots in archive")
    options = pd.DataFrame(options).sort_values(["date", "created"]).drop_duplicates(
        "date", keep="first"
    )
    pm = pd.read_csv(pm_clean_csv).sort_values(["date", "ts"])
    ref = pd.read_csv(reference_spx_daily).set_index("date")
    records = []
    for _, opt in options.iterrows():
        day = opt["date"]
        if day not in ref.index:
            continue
        label = ref.loc[day, "actual_outcome"]
        if label not in ("Up", "Down"):
            continue
        target = opt["created"] + lag_minutes * 60
        # Execution is represented by the first quality-filtered paired PM
        # quote at or AFTER target, within 6min. No hindsight best-price pick.
        quotes = pm.loc[(pm.date == day) & pm.ts.between(target, target + 360)]
        if quotes.empty:
            continue
        q = quotes.iloc[0]
        records.append({
            "date": day,
            "option_created_ts": opt["created"],
            "decision_ts": float(q.ts),
            "delay_seconds": float(q.ts - opt["created"]),
            "iv": float(opt["iv"]),
            "skew": float(opt["skew"]),
            "skew_valid": bool(float(opt["skew"]) != 0),
            "expiry": opt["expiry"],
            "is_0dte": bool(opt["expiry"] == day),
            "provider_quote_asof_verified": bool(opt["strict_quote_asof"]),
            "pm_yes_mid": float(q.yes_mid),
            "pm_yes_ask": float(q.yes_ask),
            "pm_no_ask": float(q.no_ask),
            "y": int(label == "Up"),
        })
    return pd.DataFrame(records).sort_values("date").reset_index(drop=True)


def ridge_offset_fit(market_p, y, standardized_features, lam=8.0):
    """Convex ridge fit on additive logit correction, solved via Newton steps."""
    x = np.column_stack([np.ones(len(market_p)), standardized_features])
    offset = odds_logit(market_p)
    beta = np.zeros(x.shape[1])
    for _ in range(60):
        p = sigmoid(offset + x @ beta)
        gradient = x.T @ (p - y) + lam * beta
        hessian = x.T @ (x * (p * (1 - p))[:, None]) + lam * np.eye(len(beta))
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if np.max(np.abs(step)) < 1e-12:
            break
    return beta


def walk_forward(events, features, min_train=8, lam=8.0):
    """Chronological only. All z-score means/sds are fit on previous days."""
    predictions = []
    for i in range(min_train, len(events)):
        train = events.iloc[:i]
        candidate = events.iloc[i]
        if "skew" in features:
            train = train.loc[train.skew_valid]
            if not bool(candidate["skew_valid"]):
                continue
        if len(train) < min_train:
            continue
        x = train[features].to_numpy(dtype=float)
        mu = x.mean(axis=0)
        sd = np.maximum(x.std(axis=0), 0.005)
        x_train = (x - mu) / sd
        x_test = (candidate[features].to_numpy(dtype=float) - mu) / sd
        coeff = ridge_offset_fit(
            train.pm_yes_mid.to_numpy(dtype=float),
            train.y.to_numpy(dtype=float), x_train, lam=lam
        )
        estimate = sigmoid(
            odds_logit(candidate["pm_yes_mid"])
            + np.r_[1.0, x_test] @ coeff
        )
        r = candidate.to_dict()
        r["p_model"] = float(estimate)
        r["training_days"] = int(len(train))
        predictions.append(r)
    return pd.DataFrame(predictions)


def score_and_trades(predictions, fee_coefficient=0.04, min_edge=0.03):
    if predictions.empty:
        return {"n": 0}
    p = predictions.p_model.to_numpy()
    market = predictions.pm_yes_mid.to_numpy()
    y = predictions.y.to_numpy()
    yask = predictions.pm_yes_ask.to_numpy()
    nask = predictions.pm_no_ask.to_numpy()
    brier_model = np.mean((y - p) ** 2)
    brier_market = np.mean((y - market) ** 2)
    edge_yes = p - yask - fee_coefficient * yask * (1 - yask)
    edge_no = (1 - p) - nask - fee_coefficient * nask * (1 - nask)
    side = np.where((edge_yes > edge_no) & (edge_yes > min_edge), "YES",
                    np.where((edge_no >= edge_yes) & (edge_no > min_edge),
                             "NO", "PASS"))
    realized = np.where(
        side == "YES", y - yask - fee_coefficient * yask * (1 - yask),
        np.where(side == "NO",
                 (1 - y) - nask - fee_coefficient * nask * (1 - nask),
                 0.0)
    )
    trades = [
        {"date": row["date"], "side": str(side[i]),
         "pnl_usdc_per_share_scenario": round(float(realized[i]), 6)}
        for i, row in predictions.reset_index(drop=True).iterrows()
        if side[i] != "PASS"
    ]
    return {
        "n": len(predictions),
        "market_brier": float(brier_market),
        "model_brier": float(brier_model),
        "delta_brier": float(brier_model - brier_market),
        "trades": trades,
        "total_net_one_share_per_trade": float(sum(v["pnl_usdc_per_share_scenario"] for v in trades)),
        "option_quote_timestamps_verified": bool(
            predictions.provider_quote_asof_verified.all()
        ),
        "status": "RESEARCH_ONLY_NO_VERIFIED_EDGE",
    }


def evaluate(spy_zip, pm_clean_csv, reference_spx_daily):
    results = {}
    for delay in (15, 30):
        events = load_private_events(
            spy_zip, pm_clean_csv, reference_spx_daily, delay
        )
        results[f"delay_{delay}m"] = {
            "days_matched": len(events),
            "date_from": events.date.iloc[0] if len(events) else None,
            "date_to": events.date.iloc[-1] if len(events) else None,
            "quote_asof_verified_count": int(
                events.provider_quote_asof_verified.sum()
            ) if len(events) else 0,
        }
        for name, feats in (
            ("PM_calibrated", []),
            ("PM_plus_IV", ["iv"]),
            ("PM_plus_skew", ["skew"]),
            ("PM_plus_IV_skew", ["iv", "skew"]),
        ):
            predictions = walk_forward(events, feats)
            results[f"delay_{delay}m"][name] = score_and_trades(predictions)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--spy-zip", type=Path, required=True)
    parser.add_argument("--pm-clean-csv", type=Path, required=True)
    parser.add_argument("--reference-spx-daily", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    report = evaluate(
        args.spy_zip, args.pm_clean_csv, args.reference_spx_daily
    )
    output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
