import hashlib
import io
import json

import numpy as np
import pandas as pd

from .contracts import Profile, digest, utc_now
from .store import Store


class ImportFailure(ValueError):
    pass


def parse_csv(payload: bytes, profile: Profile, now: pd.Timestamp | None = None) -> tuple[pd.DataFrame, dict]:
    now = pd.Timestamp.now(tz="UTC") if now is None else now
    frame = pd.read_csv(io.BytesIO(payload), encoding="utf-8-sig")
    lookup = {str(column).strip().lower(): column for column in frame.columns}
    mapping = {}
    for column in ["time", "open", "high", "low", "close", "volume"]:
        selected = profile.columns.get(column, lookup.get(column))
        if selected is None and column != "volume":
            raise ImportFailure(f"Missing CSV column: {column}; set profile.columns explicitly")
        if selected is not None:
            if selected not in frame:
                raise ImportFailure(f"Unknown mapped column: {selected}")
            mapping[selected] = column
    if len(set(mapping.values())) != len(mapping) or len(mapping) < 5:
        raise ImportFailure("Column mapping must be one-to-one")
    frame = frame[list(mapping)].rename(columns=mapping)
    if frame.empty:
        raise ImportFailure("CSV is empty")
    try:
        if pd.api.types.is_numeric_dtype(frame["time"]):
            times = pd.to_datetime(frame["time"], unit=profile.timestamp_unit, utc=True, errors="raise")
        else:
            times = pd.to_datetime(frame["time"], format="mixed", errors="raise")
            if times.dt.tz is None:
                times = times.dt.tz_localize(
                    profile.timestamp_timezone, ambiguous="raise", nonexistent="raise"
                )
            times = times.dt.tz_convert("UTC")
    except Exception as exc:
        raise ImportFailure(
            "Invalid/ambiguous timestamps; use epoch or ISO with explicit UTC offset"
        ) from exc
    frame["bar_open_utc"] = times
    step = pd.Timedelta(minutes=profile.timeframe_minutes)
    if times.isna().any() or ((times.dt.as_unit("ns").astype("int64") % step.value) != 0).any():
        raise ImportFailure("Timestamps must align to the configured UTC candle grid")
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    values = frame[["open", "high", "low", "close"]]
    invalid = (~np.isfinite(values).all(axis=1)) | (values <= 0).any(axis=1)
    invalid |= frame.high < frame[["open", "close", "low"]].max(axis=1)
    invalid |= frame.low > frame[["open", "close", "high"]].min(axis=1)
    if invalid.any():
        raise ImportFailure(f"Invalid OHLC rows: {int(invalid.sum())}; raw file preserved")
    if "volume" not in frame:
        frame["volume"] = np.nan
    else:
        raw_volume = frame.volume
        frame["volume"] = pd.to_numeric(raw_volume, errors="coerce")
        invalid_volume = (raw_volume.notna() & frame.volume.isna()) | (
            frame.volume.notna() & ((frame.volume < 0) | ~np.isfinite(frame.volume))
        )
        if invalid_volume.any():
            raise ImportFailure("Invalid volume; use a number >=0 or an empty value")
    duplicate_count = int(frame.duplicated("bar_open_utc").sum())
    comparison = ["bar_open_utc", "open", "high", "low", "close", "volume"]
    unique = frame[comparison].drop_duplicates()
    if unique.duplicated("bar_open_utc").any():
        raise ImportFailure("Conflicting duplicate bars; implicit corrections are forbidden")
    frame = frame.drop_duplicates("bar_open_utc").sort_values("bar_open_utc")
    frame["bar_close_utc"] = frame.bar_open_utc + step
    partial = frame.bar_close_utc > now
    partial_count = int(partial.sum())
    frame = frame.loc[~partial].copy()
    if frame.empty:
        raise ImportFailure("No closed bars available")
    frame["received_at_utc"] = utc_now()
    frame = frame[
        ["bar_open_utc", "bar_close_utc", "open", "high", "low", "close", "volume", "received_at_utc"]
    ].reset_index(drop=True)
    return frame, {
        "duplicate_rows": duplicate_count,
        "partial_rows_excluded": partial_count,
        "invalid_rows": 0,
    }


def quality_report(frame: pd.DataFrame, profile: Profile, now: pd.Timestamp | None = None) -> dict:
    now = pd.Timestamp.now(tz="UTC") if now is None else now
    if frame.empty:
        return {"status": "INSUFFICIENT_DATA", "rows": 0, "coverage": None, "missing_bars": 0}
    start, end = frame.bar_open_utc.min(), frame.bar_open_utc.max()
    expected = pd.date_range(start, end, freq=f"{profile.timeframe_minutes}min")
    expected = expected[profile.calendar.mask(expected)]
    actual = pd.DatetimeIndex(frame.bar_open_utc)
    missing = expected.difference(actual)
    off_session = actual.difference(expected)
    age = max(0.0, (now - frame.bar_close_utc.max()).total_seconds() / 60)
    # Coverage is only within the observed span. A short export is NOT full history.
    flags = []
    if not profile.calendar.verified or profile.data_license == "UNCONFIRMED":
        flags.append("HISTORY_INCOMPLETE")
    if len(missing):
        flags.append("MISSING_BARS")
    if len(off_session):
        flags.append("OUTSIDE_SESSION")
    if age > profile.max_staleness_minutes:
        flags.append("DATA_STALE")
    if profile.is_demo:
        flags.insert(0, "DEMO")
    return {
        "status": flags[0] if flags else "COLLECTING",
        "flags": flags,
        "rows": len(frame),
        "expected_bars_in_observed_span": len(expected),
        "coverage": len(actual.intersection(expected)) / len(expected) if len(expected) else None,
        "missing_bars": len(missing),
        "missing_examples": [x.isoformat() for x in missing[:20]],
        "off_session_bars": len(off_session),
        "first_bar_utc": start.isoformat(),
        "last_bar_close_utc": frame.bar_close_utc.max().isoformat(),
        "age_minutes": round(age, 1),
        "calendar_verified": profile.calendar.verified,
        "history_completeness": "NOT_ESTABLISHED",
        "timeframe_minutes": profile.timeframe_minutes,
    }


def import_csv(store: Store, payload: bytes, profile: Profile, now: pd.Timestamp | None = None) -> dict:
    if len(payload) > 25 * 1024 * 1024:
        raise ImportFailure("CSV exceeds the MVP 25 MiB limit; split the file")
    raw_hash = hashlib.sha256(payload).hexdigest()
    import_id = digest({"raw": raw_hash, "profile": profile.model_dump()})
    raw_path = store.root / "raw" / f"{raw_hash}.csv"
    raw_path.parent.mkdir(exist_ok=True)
    if not raw_path.exists():
        raw_path.write_bytes(payload)
    manifest_path = raw_path.parent / f"{import_id}.profile.json"
    if not manifest_path.exists():
        manifest_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    with store.connect() as db:
        old = db.execute("SELECT payload FROM imports WHERE id=?", [import_id]).fetchone()
    if old:
        previous = json.loads(old[0])
        if previous["status"] == "REJECTED":
            raise ImportFailure(previous["error"])
        return {**previous, "idempotent_replay": True}
    try:
        incoming, parse_report = parse_csv(payload, profile, now)
        existing = store.read_dataset(profile.dataset_id)
        merged = pd.concat([existing, incoming], ignore_index=True) if not existing.empty else incoming
        keys = ["bar_open_utc", "open", "high", "low", "close", "volume"]
        if merged[keys].drop_duplicates().duplicated("bar_open_utc").any():
            raise ImportFailure("DATA_CONFLICT: correction needs a new explicit source/profile version")
        merged = (
            merged.drop_duplicates("bar_open_utc", keep="first")
            .sort_values("bar_open_utc")
            .reset_index(drop=True)
        )
        snapshot = store.save_dataset(profile.dataset_id, merged, profile.model_dump())
        result = {
            "import_id": import_id,
            "dataset_id": profile.dataset_id,
            "dataset_hash": snapshot,
            "raw_hash": raw_hash,
            "received_at_utc": utc_now(),
            "status": "IMPORTED",
            "rows_added": len(merged) - len(existing),
            "parse": parse_report,
            "quality": quality_report(merged, profile, now),
        }
        # A file with an unfinished bar is safely retained, but can be retried after it closes.
        if parse_report["partial_rows_excluded"] == 0:
            store.append("imports", import_id, result)
        return result
    except Exception as exc:
        store.append(
            "imports",
            import_id,
            {"import_id": import_id, "raw_hash": raw_hash, "status": "REJECTED", "error": str(exc)},
        )
        raise


def aggregate(frame: pd.DataFrame, minutes: int, source_minutes: int = 1) -> tuple[pd.DataFrame, int]:
    if minutes < source_minutes or minutes % source_minutes:
        return pd.DataFrame(), 0
    indexed = frame.set_index("bar_open_utc").sort_index()
    grouped = indexed.resample(f"{minutes}min", origin="epoch", closed="left", label="left")
    result = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        count=("close", "count"),
        first=("bar_close_utc", "min"),
        last=("bar_close_utc", "max"),
    )
    result["volume"] = grouped.volume.sum(min_count=1)
    result["bar_close_utc"] = result.index + pd.Timedelta(minutes=minutes)
    complete = (
        (result["count"] == minutes // source_minutes)
        & (result["first"] == result.index + pd.Timedelta(minutes=source_minutes))
        & (result["last"] == result.bar_close_utc)
    )
    incomplete = int(((result["count"] > 0) & ~complete).sum())
    result = result.loc[complete].drop(columns=["count", "first", "last"]).reset_index()
    return result, incomplete
