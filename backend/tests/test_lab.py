import json
import sqlite3
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.contracts import Calendar, Profile, Session
from backend.app.ingestion import ImportFailure, aggregate, import_csv, parse_csv, quality_report
from backend.app.main import app
from backend.app.pipeline import build, demo_data
from backend.app.research import (
    MODELS,
    approval_gate,
    check_issue_time,
    envelope_score,
    feature_snapshot,
    first_touch,
    labels,
    paired_bootstrap,
    predict,
    run_research,
)
from backend.app.store import Store


@pytest.fixture
def sample():
    payload, profile = demo_data("XAUUSD", days=4)
    frame, _ = parse_csv(payload, profile)
    return payload, profile, frame


def test_ingest_idempotence_and_duckdb(tmp_path, sample):
    payload, profile, frame = sample
    store = Store(tmp_path)
    first = import_csv(store, payload, profile)
    second = import_csv(store, payload, profile)
    assert first["dataset_hash"] == second["dataset_hash"]
    assert second["idempotent_replay"]
    assert len(store.read_dataset(profile.dataset_id)) == len(frame)
    assert len(store.items("imports")) == 1
    assert len(list((tmp_path / "raw").glob("*.csv"))) == 1


def test_invalid_ohlc_preserves_raw(tmp_path, sample):
    payload, profile, _ = sample
    text = payload.decode().splitlines()
    row = text[1].split(",")
    row[2] = "1"
    text[1] = ",".join(row)
    store = Store(tmp_path)
    with pytest.raises(ImportFailure, match="Invalid OHLC"):
        import_csv(store, "\n".join(text).encode(), profile)
    assert list((tmp_path / "raw").glob("*.csv"))
    assert store.items("imports")[0]["status"] == "REJECTED"


def test_conflicting_reimport_rejected(tmp_path, sample):
    payload, profile, _ = sample
    store = Store(tmp_path)
    import_csv(store, payload, profile)
    frame = pd.read_csv(__import__("io").BytesIO(payload))
    frame.loc[0, "high"] += 1
    with pytest.raises(ImportFailure, match="DATA_CONFLICT"):
        import_csv(store, frame.to_csv(index=False).encode(), profile)
    assert store.read_dataset(profile.dataset_id).high.iloc[0] != frame.high.iloc[0]


@pytest.mark.parametrize("minutes", [15, 60, 240])
def test_resample_vs_reference(sample, minutes):
    _, _, frame = sample
    source = frame.iloc[:960]
    actual, incomplete = aggregate(source, minutes)
    assert incomplete == 0
    assert len(actual) == 960 // minutes
    for i, bar in actual.iterrows():
        group = source.iloc[i * minutes : (i + 1) * minutes]
        assert bar.open == group.open.iloc[0]
        assert bar.close == group.close.iloc[-1]
        assert bar.high == group.high.max()
        assert bar.low == group.low.min()
        assert bar.volume == group.volume.sum()


def test_missing_data_gate(sample):
    _, profile, frame = sample
    broken = frame.drop(index=12)
    report = quality_report(broken, profile)
    assert report["missing_bars"] == 1
    assert "MISSING_BARS" in report["flags"]
    _, incomplete = aggregate(broken, 15)
    assert incomplete == 1


def test_partial_bar_not_available(sample):
    payload, profile, all_bars = sample
    now = all_bars.bar_open_utc.iloc[10] + pd.Timedelta(seconds=30)
    frame, report = parse_csv(payload, profile, now=now)
    assert len(frame) == 10
    assert report["partial_rows_excluded"] == len(all_bars) - 10
    assert frame.bar_close_utc.max() <= now


def test_timezones_dst_and_holiday():
    calendar = Calendar(
        timezone="America/New_York", sessions=[Session(open_minute=570, close_minute=960)], verified=True
    )
    times = pd.DatetimeIndex(["2026-03-06T14:30:00Z", "2026-03-09T13:30:00Z", "2026-03-09T12:30:00Z"])
    assert calendar.mask(times).tolist() == [True, True, False]
    calendar.closed_dates = ["2026-03-09"]
    assert calendar.mask(times).tolist() == [True, False, False]


def test_ambiguous_local_dst_rejected(sample):
    _, profile, _ = sample
    profile.timestamp_timezone = "America/New_York"
    payload = b"time,open,high,low,close\n2026-11-01T01:30:00,10,11,9,10\n"
    with pytest.raises(ImportFailure, match="ambiguous"):
        parse_csv(payload, profile)


def test_no_future_leakage(sample):
    _, _, raw = sample
    bars, _ = aggregate(raw, 15)
    as_of = bars.bar_open_utc.iloc[220]
    snapshot = feature_snapshot(bars, as_of)
    changed = bars.copy()
    changed.loc[changed.bar_open_utc >= as_of, ["open", "high", "low", "close"]] *= 2
    assert feature_snapshot(changed, as_of) == snapshot
    original = labels(bars)
    altered = labels(changed)
    index = original.index[original.as_of == as_of][0]
    for model in MODELS:
        assert predict(original.iloc[:index], original.iloc[index], model) == predict(
            altered.iloc[:index], altered.iloc[index], model
        )


def test_prediction_immutability(tmp_path):
    store = Store(tmp_path)
    store.append("forecasts", "id", {"value": 1})
    assert store.append("forecasts", "id", {"value": 2}) == {"value": 1}
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE forecasts SET payload='{}' WHERE id='id'")


def test_joint_interval_checks_high_and_low():
    assert envelope_score(90, 110, 85, 105, 0.9) > envelope_score(90, 110, 95, 105, 0.9)
    assert envelope_score(90, 110, 95, 115, 0.9) > envelope_score(90, 110, 95, 105, 0.9)


def test_nested_joint_quantiles(sample):
    _, _, raw = sample
    bars, _ = aggregate(raw, 15)
    dataset = labels(bars)
    result = predict(dataset.iloc[:200], dataset.iloc[200], MODELS[0])["intervals"]
    lows = [v["lower"] for v in result.values()]
    highs = [v["upper"] for v in result.values()]
    assert lows == sorted(lows, reverse=True)
    assert highs == sorted(highs)


def test_ambiguous_stop_take():
    frame = pd.DataFrame([{"high": 120, "low": 80}])
    assert first_touch(frame, "long", 110, 90) == "AMBIGUOUS"
    assert first_touch(frame, "short", 90, 110) == "AMBIGUOUS"


def test_market_alias_basis(sample):
    _, profile, _ = sample
    assert profile.execution_instrument_id is None
    with pytest.raises(ValidationError):
        Profile(**{**profile.model_dump(), "source_symbol": "GC"})


def test_baseline_paired():
    baseline = pd.DataFrame(
        {"as_of": pd.date_range("2026-01-01", periods=10, tz="UTC"), "score_90": np.arange(10) + 2}
    )
    challenger = baseline.assign(score_90=np.arange(10))
    paired = paired_bootstrap(baseline, challenger)
    assert paired["ci95"] == [2.0, 2.0]
    with pytest.raises(ValueError, match="identical timestamps"):
        paired_bootstrap(baseline, challenger.iloc[1:])


def test_validation_registry_and_demo_no_trade():
    metrics = {"n": 1000, "coverage": {"0.9": 0.9}, "by_regime": []}
    result = approval_gate(metrics, True, forward_count=1000)
    assert result["status"] == "DEMO"
    assert not result["approved"] and not result["is_trading_qualified"]
    assert not approval_gate(metrics, False, forward_count=1000)["approved"]


def test_late_forecast():
    time = pd.Timestamp("2026-11-01T10:00Z")
    with pytest.raises(ValueError, match="LATE_FORECAST"):
        check_issue_time(time + pd.Timedelta(seconds=1), time, "next_closed_bar")
    check_issue_time(time + pd.Timedelta(days=1), time, "historical_simulation")


def test_model_version_reproducible(tmp_path, sample):
    _, profile, raw = sample
    bars, _ = aggregate(raw, 15)
    store = Store(tmp_path)
    first = run_research(store, bars, profile, 15, "fixed-snapshot")
    second = run_research(store, bars, profile, 15, "fixed-snapshot")
    assert first["run_id"] == second["run_id"]
    assert first["models"] == second["models"]
    assert first["history"][-1]["issued_at_utc"] == second["history"][-1]["issued_at_utc"]
    assert all(not f["eligible_for_forward_validation"] for f in second["history"])
    assert first["live_forecast"] is None


def test_stale_and_unverified_calendar(sample):
    _, profile, frame = sample
    profile.is_demo = False
    profile.asset_class = "cfd"
    profile.calendar.verified = False
    report = quality_report(frame, profile, now=pd.Timestamp(datetime.now(UTC)))
    assert "HISTORY_INCOMPLETE" in report["flags"]
    assert "DATA_STALE" in report["flags"]


def test_nullable_volume(sample):
    _, profile, _ = sample
    payload = b"time,open,high,low,close\n2026-01-01T00:00:00Z,10,11,9,10\n"
    frame, _ = parse_csv(payload, profile)
    assert frame.volume.isna().all()


def test_real_data_not_silently_published(tmp_path, sample):
    payload, profile, _ = sample
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "x.csv").write_bytes(payload)
    profile.publish_allowed = False
    (inputs / "x.profile.json").write_text(profile.model_dump_json())
    with pytest.raises(ValueError, match="Public build denied"):
        build(Store(tmp_path / "data"), tmp_path / "out.json", inputs=inputs, public=True)


def test_api_local_no_unsupported_probabilities(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get("/healthz").json()["auto_execution"] is False
    assert client.get("/v1/forecasts/latest").json()["forecast"] is None
    assert client.get("/v1/forecasts/history?limit=1001").status_code == 422
    result = client.post(
        "/v1/scenarios/evaluate", json={"direction": "long", "entry": 100, "tp": 120, "sl": 90}
    ).json()
    assert result["reward_risk_before_costs"] == 2
    assert result["expected_r"] is None and result["p_tp_first"] is None
    assert (
        client.post(
            "/v1/scenarios/evaluate", json={"direction": "long", "entry": 100, "tp": 90, "sl": 110}
        ).status_code
        == 422
    )


def test_raw_json_never_contains_nan(sample):
    payload, profile, _ = sample
    frame, _ = parse_csv(payload, profile)
    json.dumps(quality_report(frame, profile), allow_nan=False)
