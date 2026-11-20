"""Offline unit tests for the Polymarket SPX quote-pair parity experiment."""
import csv
import gzip
import io
import json
import zipfile

import pytest

from scripts.polymarket_spx_parity_audit import audit, input_rows


def pair(**overrides):
    row = {
        "market_slug": "spx-up-or-down-on-september-1-2026",
        "timestamp_utc": "10000000", "yes_quote_time": "9500000",
        "no_quote_time": "9500000",
        "yes_bid": ".44", "yes_ask": ".45",
        "no_bid": ".54", "no_ask": ".55",
    }
    row.update({key: str(val) for key, val in overrides.items()})
    return row


def test_quoted_pair_at_exact_dollar_is_not_arbitrage():
    r = audit([pair()])
    assert r["raw_minute_pair_rows"] == 1
    assert r["eligible_contemporaneous_pairs"] == 1
    assert r["raw_buy_both_ask_lt_one"] == 0
    assert r["eligible_buy_both_ask_plus_buffer_lt_one"] == 0
    assert r["status"] == "NO_EXECUTABLE_EDGE_PROVEN"


def test_theoretical_discount_never_claims_fill():
    r = audit([pair(yes_ask=".40", yes_bid=".39", no_ask=".55")])
    assert r["eligible_buy_both_ask_plus_buffer_lt_one"] == 1
    assert r["fills_proven"] is False
    assert r["depth_verified"] is False
    with_fee = audit([pair(yes_ask=".40", yes_bid=".39", no_ask=".55")],
                     fee_buffer_per_leg=0.03)
    assert with_fee["eligible_buy_both_ask_plus_buffer_lt_one"] == 0


def test_stale_or_future_quote_fails_closed():
    r = audit([pair(yes_quote_time="1000000")])
    assert r["well_formed_pairs"] == 1
    assert r["eligible_contemporaneous_pairs"] == 0
    assert r["exclusion_counts"]["stale_or_future_quote"] == 1
    f = audit([pair(yes_quote_time="11000000")])
    assert f["eligible_contemporaneous_pairs"] == 0


def test_unaligned_pair_fails_closed():
    r = audit([pair(no_quote_time="7000000")])
    assert r["eligible_contemporaneous_pairs"] == 0
    assert r["exclusion_counts"]["unsynchronized_pair"] == 1


def test_spread_gate():
    r = audit([pair(yes_bid=".20")])
    assert r["eligible_contemporaneous_pairs"] == 0
    assert r["exclusion_counts"]["wide_spread"] == 1


def test_bad_prices_and_nan_do_not_create_fake_arbitrage():
    r = audit([pair(yes_bid=".60"), pair(timestamp_utc="11000000", yes_ask="nan")])
    assert r["invalid_pairs"] == 2
    assert r["raw_buy_both_ask_lt_one"] == 0


def test_reject_non_target_family_and_duplicate_minutes():
    with pytest.raises(ValueError, match="wrong market contract"):
        audit([pair(market_slug="spx-opens-up-or-down-on-september-1-2026")])
    with pytest.raises(ValueError, match="duplicate"):
        audit([pair(), pair()])


def test_minimum_and_median_are_data_derived():
    r = audit([pair(), pair(timestamp_utc="11000000", yes_quote_time="10500000",
                            no_quote_time="10500000", yes_ask=".46")])
    assert r["minimum_eligible_ask_sum"] == pytest.approx(1.0)
    assert r["median_eligible_ask_sum"] == pytest.approx(1.005)
    assert r["unique_daily_markets"] == 1


def test_zip_gzip_partition_parser(tmp_path):
    f = tmp_path / "private.zip"
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(pair()))
    writer.writeheader()
    writer.writerow(pair())
    with zipfile.ZipFile(f, "w") as out:
        out.writestr("H2/data/quotes_yes_no_0_21.csv.gz",
                     gzip.compress(buffer.getvalue().encode("utf-8")))
    assert audit(input_rows([f]))["eligible_contemporaneous_pairs"] == 1


def test_missing_fields_are_not_silently_assumed(tmp_path):
    f = tmp_path / "wrong.csv"
    f.write_text("market_slug,yes_ask,no_ask\na,.1,.2\n")
    with pytest.raises(ValueError, match="missing required"):
        list(input_rows([f]))


def test_nonnegative_input_gates():
    with pytest.raises(ValueError):
        audit([], fee_buffer_per_leg=-0.1)
