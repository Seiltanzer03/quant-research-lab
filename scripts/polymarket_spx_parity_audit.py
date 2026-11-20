#!/usr/bin/env python3
"""Reproducible, non-trading SPX daily Polymarket YES/NO parity audit.

Accepts private local ZIP with the two .csv.gz quote partitions from H2
research, or ordinary .csv[.gz] files. No server or exchange API calls.
Never copies licensed/raw user quotes into the public repository.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import zipfile

_REQUIRED = {
    "market_slug", "timestamp_utc", "yes_quote_time", "no_quote_time",
    "yes_bid", "yes_ask", "no_bid", "no_ask",
}


def input_rows(paths):
    """Iterate quote snapshots, returning errors for unsupported layouts."""
    for path in map(Path, paths):
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                items = sorted(
                    item for item in archive.namelist()
                    if item.endswith(".csv.gz") and "quotes_yes_no" in item
                )
                if not items:
                    raise ValueError(f"no quotes_yes_no .csv.gz partitions: {path}")
                for item in items:
                    with archive.open(item) as stream:
                        with gzip.open(stream, "rt", encoding="utf-8", newline="") as handle:
                            yield from _read_csv(handle)
        elif path.name.endswith(".csv.gz"):
            with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                yield from _read_csv(handle)
        elif path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                yield from _read_csv(handle)
        else:
            raise ValueError(f"not a supported ZIP/CSV input: {path}")


def _read_csv(handle):
    reader = csv.DictReader(handle)
    if not _REQUIRED.issubset(set(reader.fieldnames or [])):
        raise ValueError(f"missing required quote fields: {sorted(_REQUIRED - set(reader.fieldnames or []))}")
    yield from reader


def _float(row, field):
    value = float(row[field])
    if not (-float("inf") < value < float("inf")):
        raise ValueError(f"nonfinite {field}")
    return value


def audit(rows, max_age_seconds=30.0, max_spread=0.05,
          max_quote_skew_seconds=1.0, fee_buffer_per_leg=0.0):
    """Fail closed on malformed pairs, stale clocks and inconsistent bid/ask.

    A below-$1 paired Ask is only a *theoretical* candidate: execution also
    requires quantities at both asks, fees, order latency, and eventual payout.
    Snapshot correlation is not equivalent to simultaneous executable quotes.
    """
    if min(max_age_seconds, max_spread, max_quote_skew_seconds, fee_buffer_per_leg) < 0:
        raise ValueError("filters and fees must be non-negative")
    seen = set()
    raw_pairs = eligible_pairs = invalid_pairs = 0
    raw_discounts = eligible_discounts = 0
    market_names = set()
    eligible_markets = set()
    raw_sums, eligible_sums = [], []
    reasons = {}
    for row in rows:
        raw_pairs += 1
        market = str(row.get("market_slug") or "")
        if not market.startswith("spx-up-or-down-on-"):
            raise ValueError(f"wrong market contract family: {market}")
        ts = str(row.get("timestamp_utc") or "")
        key = (market, ts)
        if key in seen:
            raise ValueError(f"duplicate market+timestamp row: {market}, {ts}")
        seen.add(key)
        market_names.add(market)
        try:
            yes_bid = _float(row, "yes_bid")
            yes_ask = _float(row, "yes_ask")
            no_bid = _float(row, "no_bid")
            no_ask = _float(row, "no_ask")
            now_us = _float(row, "timestamp_utc")
            y_us = _float(row, "yes_quote_time")
            n_us = _float(row, "no_quote_time")
        except (ValueError, TypeError, KeyError):
            invalid_pairs += 1
            reasons["invalid_field"] = reasons.get("invalid_field", 0) + 1
            continue
        if not (0 < yes_bid <= yes_ask < 1 and 0 < no_bid <= no_ask < 1):
            invalid_pairs += 1
            reasons["invalid_price"] = reasons.get("invalid_price", 0) + 1
            continue
        ask_sum = yes_ask + no_ask
        raw_sums.append(ask_sum)
        if ask_sum < 1 - 1e-10:
            raw_discounts += 1
        y_age = (now_us - y_us) / 1_000_000
        n_age = (now_us - n_us) / 1_000_000
        if not (0 <= y_age <= max_age_seconds and 0 <= n_age <= max_age_seconds):
            reason = "stale_or_future_quote"
        elif abs(y_us - n_us) / 1_000_000 > max_quote_skew_seconds:
            reason = "unsynchronized_pair"
        elif (yes_ask - yes_bid > max_spread + 1e-12 or
              no_ask - no_bid > max_spread + 1e-12):
            reason = "wide_spread"
        else:
            reason = None
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        eligible_pairs += 1
        eligible_markets.add(market)
        eligible_sums.append(ask_sum)
        if ask_sum + 2 * fee_buffer_per_leg < 1 - 1e-10:
            eligible_discounts += 1

    return {
        "protocol": "polymarket-spx-parity-v1",
        "market_family": "spx-up-or-down-on-*",
        "raw_minute_pair_rows": raw_pairs,
        "unique_daily_markets": len(market_names),
        "well_formed_pairs": len(raw_sums),
        "invalid_pairs": invalid_pairs,
        "eligible_contemporaneous_pairs": eligible_pairs,
        "eligible_markets": len(eligible_markets),
        "raw_buy_both_ask_lt_one": raw_discounts,
        "eligible_buy_both_ask_plus_buffer_lt_one": eligible_discounts,
        "minimum_raw_ask_sum": min(raw_sums) if raw_sums else None,
        "median_raw_ask_sum": statistics.median(raw_sums) if raw_sums else None,
        "minimum_eligible_ask_sum": min(eligible_sums) if eligible_sums else None,
        "median_eligible_ask_sum": statistics.median(eligible_sums) if eligible_sums else None,
        "max_age_seconds": max_age_seconds,
        "max_spread_per_leg": max_spread,
        "max_pair_quote_time_skew_seconds": max_quote_skew_seconds,
        "fee_buffer_per_leg_usd": fee_buffer_per_leg,
        "exclusion_counts": reasons,
        "fills_proven": False,
        "depth_verified": False,
        "status": "NO_EXECUTABLE_EDGE_PROVEN",
    }


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit YES+NO pair ask parity without live requests")
    parser.add_argument("inputs", nargs="+", help="H2 ZIP archive or local quote .csv[.gz]")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--max-age", type=float, default=30.0)
    parser.add_argument("--max-spread", type=float, default=0.05)
    parser.add_argument("--max-skew", type=float, default=1.0)
    parser.add_argument("--fee-per-leg", type=float, default=0.0)
    args = parser.parse_args(argv)
    result = audit(input_rows(args.inputs), args.max_age, args.max_spread,
                   args.max_skew, args.fee_per_leg)
    result["input_sha256"] = {str(x): file_hash(x) for x in args.inputs}
    content = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(content, encoding="utf-8")
    print(content, end="")
    return result


if __name__ == "__main__":
    main()
