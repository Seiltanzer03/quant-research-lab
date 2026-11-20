#!/usr/bin/env python3
"""Exploratory close-to-close SPX binary settlement baselines, never live/OOS.

Historical independent daily market; one predetermined snapshot at 14:01–14:05
America/New_York. Resolution labels are UNVERIFIED REFERENCE (e.g. Yahoo SPX
daily close comparisons), not authenticated Polymarket settlement records.
Do not trade from this analysis.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import random
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.polymarket_spx_parity_audit import input_rows

NY = ZoneInfo("America/New_York")


def load_reference_outcomes(path):
    """Immutable result labels used for post-event scoring, never as features."""
    results = {}
    with open(path, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not {"date", "actual_outcome"}.issubset(reader.fieldnames or []):
            raise ValueError("reference CSV requires date and actual_outcome")
        for row in reader:
            day = row["date"]
            outcome = row["actual_outcome"]
            if outcome not in {"Up", "Down"}:
                continue  # Tie/uncertain event must not be guessed.
            if day in results and results[day] != outcome:
                raise ValueError(f"conflicting outcomes: {day}")
            results[day] = outcome
    return results


def market_day(slug):
    prefix = "spx-up-or-down-on-"
    if not slug.startswith(prefix):
        raise ValueError(f"wrong market family: {slug}")
    return datetime.strptime(slug[len(prefix):], "%B-%d-%Y").date().isoformat()


def _float(row, name):
    x = float(row[name])
    if not (-float("inf") < x < float("inf")):
        raise ValueError(name)
    return x


def eligible_record(row):
    """Entry quote must be available by the snapshot time, never later."""
    try:
        now, yt, nt = [_float(row, k) for k in
                       ("timestamp_utc", "yes_quote_time", "no_quote_time")]
        yb, ya, nb, na = [_float(row, k) for k in
                          ("yes_bid", "yes_ask", "no_bid", "no_ask")]
    except (ValueError, TypeError, KeyError):
        return None
    if not (0 < yb <= ya < 1 and 0 < nb <= na < 1):
        return None
    if not (0 <= (now - yt) / 1e6 <= 30 and 0 <= (now - nt) / 1e6 <= 30):
        return None
    if abs(yt - nt) / 1e6 > 1:
        return None
    if max(ya - yb, na - nb) > 0.05 + 1e-12:
        return None
    dt_local = datetime.fromtimestamp(now / 1e6, timezone.utc).astimezone(NY)
    if dt_local.hour != 14 or not (1 <= dt_local.minute <= 5):
        return None
    if market_day(row["market_slug"]) != dt_local.date().isoformat():
        return None
    return (now, (yb + ya) / 2, ya, (nb + na) / 2, na)


def choose_fixed_snapshots(rows):
    """Earliest eligible within pre-specified 14:01–14:05 ET execution window."""
    selected = {}
    seen = set()
    for row in rows:
        slug = str(row.get("market_slug", ""))
        t = str(row.get("timestamp_utc", ""))
        key = (slug, t)
        if key in seen:
            raise ValueError("duplicate market timestamp")
        seen.add(key)
        snap = eligible_record(row)
        if snap and (slug not in selected or snap[0] < selected[slug][0]):
            selected[slug] = snap
    return selected


def block_ci(values, seed=42, replications=3000):
    if len(values) < 5:
        return None
    rng = random.Random(seed)
    means = sorted(sum(values[rng.randrange(len(values))]
                       for _ in range(len(values))) / len(values)
                   for _ in range(replications))
    return [means[int(.025 * replications)],
            means[min(replications - 1, int(.975 * replications))]]


def period(day):
    if day < "2026-10-01":
        return "train"
    if day <= "2026-10-15":
        return "validation"
    return "reviewed_test_not_true_oos"


def evaluate(rows, outcomes, fee_rate=0.04):
    """Two fixed comparators: buy more likely side or less likely side."""
    if fee_rate < 0:
        raise ValueError("fee_rate")
    quotes = choose_fixed_snapshots(rows)
    pnl = {side: {name: [] for name in
                  ("train", "validation", "reviewed_test_not_true_oos", "all")}
           for side in ("favorite", "underdog")}
    outcome_coverage = 0
    for slug, (_, y_mid, y_ask, n_mid, n_ask) in quotes.items():
        date = market_day(slug)
        if date not in outcomes:
            continue
        outcome_coverage += 1
        for side in ("favorite", "underdog"):
            buy_yes = ((y_mid >= n_mid) == (side == "favorite"))
            contract = "Up" if buy_yes else "Down"
            price = y_ask if buy_yes else n_ask
            cost = fee_rate * price * (1 - price)
            net = float(contract == outcomes[date]) - price - cost
            pnl[side][period(date)].append(net)
            pnl[side]["all"].append(net)
    summaries = {}
    for side, periods in pnl.items():
        summaries[side] = {}
        for name, values in periods.items():
            summaries[side][name] = {
                "market_days": len(values),
                "mean_net_usd_per_share": statistics.mean(values) if values else None,
                "sum_net_at_one_share_per_day": sum(values),
                "bootstrap_market_day_95_pct": block_ci(values),
            }
    return {
        "protocol": "spx-14et-resolution-baseline-dev-v1",
        "status": "EXPLORATORY_ONLY_NOT_OOS",
        "resolution_label_authority": "REFERENCE_SPX_CLOSE_COMPARISON_UNVERIFIED_BY_POLYMARKET",
        "quote_execution": "OBSERVED_ASK_NOT_GUARANTEED_FILL",
        "market_rule": "SPX close vs previous official SPX close",
        "entry_window_ny": "14:01:00-14:05:59",
        "fee_rate_scenario": fee_rate,
        "fee_source_status": "PUBLIC_FINANCE_CATEGORY_REFERENCE_NOT_VERIFIED_PER_HISTORICAL_MARKET",
        "eligible_market_days": len(quotes),
        "outcome_labeled_market_days": outcome_coverage,
        "strategies": summaries,
        "edge_verified": False,
    }


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--quotes", required=True, help="private H2 ZIP with YES/NO quote partitions")
    p.add_argument("--reference-spx-daily", required=True, help="private reference SPX daily outcome CSV")
    p.add_argument("--fee-rate", type=float, default=0.04,
                   help="scenario only; check market-specific historical fee")
    p.add_argument("--json-out", type=Path)
    args = p.parse_args(argv)
    labels = load_reference_outcomes(args.reference_spx_daily)
    result = evaluate(input_rows([args.quotes]), labels, args.fee_rate)
    result["input_sha256"] = {
        "quotes": file_sha(args.quotes),
        "reference_labels": file_sha(args.reference_spx_daily),
    }
    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(output, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
