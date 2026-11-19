import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .contracts import Profile, utc_now
from .ingestion import aggregate, import_csv, quality_report
from .research import run_research
from .store import Store


def demo_data(instrument: str, days: int = 32) -> tuple[bytes, Profile]:
    """Deterministic SYNTHETIC candles. Never connected to a market data endpoint."""
    rng = np.random.default_rng(20261119 if instrument == "XAUUSD" else 20261120)
    n = days * 1440
    times = pd.date_range("2026-10-01", periods=n, freq="min", tz="UTC")
    initial = 2600.0 if instrument == "XAUUSD" else 20000.0
    cycle = 0.7 + 0.6 * (np.sin(np.arange(n) / 1440 * 2 * np.pi) ** 2)
    volatility = 0.00010 * cycle * (1 + 0.6 * np.sin(np.arange(n) / 6000) ** 2)
    close = initial * np.exp(np.cumsum(rng.normal(0, volatility, n)))
    opens = np.r_[initial, close[:-1]]
    high = np.maximum(opens, close) * (1 + np.abs(rng.normal(0, volatility / 2, n)))
    low = np.minimum(opens, close) * (1 - np.abs(rng.normal(0, volatility / 2, n)))
    frame = pd.DataFrame(
        {
            "time": times.as_unit("ns").asi8 // 10**9,
            "open": opens.round(2),
            "high": high.round(2),
            "low": low.round(2),
            "close": close.round(2),
            "volume": rng.integers(50, 500, n),
        }
    )
    profile = Profile(
        instrument_id=instrument,
        source="demo_generator_v1",
        source_symbol=f"DEMO:{instrument}",
        asset_class="synthetic",
        is_demo=True,
        available_volume_type="synthetic",
        data_license="Synthetic fixture / CC0",
        publish_allowed=True,
        calendar={"timezone": "UTC", "verified": True, "sessions": [{"weekdays": list(range(7))}]},
    )
    return frame.to_csv(index=False).encode(), profile


def bar_records(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "time": int(row.bar_open_utc.timestamp()),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
        }
        for row in frame.tail(180).itertuples()
    ]


def build(
    store: Store, output: Path, inputs: Path | None = None, auto_demo: bool = False, public: bool = False
) -> dict:
    if inputs is not None:
        for csv_file in sorted(inputs.glob("*.csv")):
            profile_path = csv_file.with_suffix(".profile.json")
            if not profile_path.exists():
                raise ValueError(f"Missing manifest: {profile_path}")
            profile = Profile.model_validate_json(profile_path.read_text())
            if public and not profile.publish_allowed:
                raise ValueError(
                    f"Public build denied: {profile_path.name} needs explicit publish_allowed=true"
                )
            import_csv(store, csv_file.read_bytes(), profile)
    if auto_demo and not store.dataset_profiles():
        for instrument in ["XAUUSD", "NAS100"]:
            payload, profile = demo_data(instrument)
            import_csv(store, payload, profile)
    datasets = []
    for data_profile in store.dataset_profiles():
        profile = Profile.model_validate(data_profile)
        if public and not profile.publish_allowed:
            continue
        frame = store.read_dataset(profile.dataset_id)
        # Also excludes rows that could have been imported with a future machine clock.
        frame = frame[frame.bar_close_utc <= pd.Timestamp.now(tz="UTC")].reset_index(drop=True)
        snapshot_hash = store.save_dataset(profile.dataset_id, frame, profile.model_dump())
        quality = quality_report(frame, profile)
        horizons = {}
        for minutes in [15, 60, 240]:
            bars, incomplete = aggregate(frame, minutes, profile.timeframe_minutes)
            # Strict calendar membership at the input resolution; no holiday interpolation.
            if not bars.empty:
                allowed = []
                for start in bars.bar_open_utc:
                    expected = pd.date_range(
                        start,
                        periods=minutes // profile.timeframe_minutes,
                        freq=f"{profile.timeframe_minutes}min",
                    )
                    allowed.append(bool(profile.calendar.mask(expected).all()))
                bars = bars.loc[allowed].reset_index(drop=True)
            research = (
                run_research(store, bars, profile, minutes, snapshot_hash)
                if len(bars)
                else {
                    "minutes": minutes,
                    "status": "INSUFFICIENT_DATA",
                    "models": [],
                    "history": [],
                    "live_forecast": None,
                }
            )
            horizons[str(minutes)] = {
                **research,
                "bars": bar_records(bars),
                "incomplete_windows_excluded": incomplete,
            }
        datasets.append(
            {
                "dataset_id": profile.dataset_id,
                "dataset_hash": snapshot_hash,
                "profile": profile.model_dump(),
                "quality": quality,
                "horizons": horizons,
                "latest_close": float(frame.close.iloc[-1]) if len(frame) else None,
            }
        )
    result = {
        "schema_version": "1.0",
        "generated_at_utc": utc_now(),
        "git_sha": os.getenv("GITHUB_SHA", "LOCAL_WORKTREE"),
        "mode": "DEMO" if datasets and all(d["profile"]["is_demo"] for d in datasets) else "RESEARCH",
        "operational_status": "NO_FORECAST",
        "schedule": "17 */6 * * * (UTC)",
        "forward_count": 0,
        "datasets": datasets,
        "modules": [
            {"id": "polymarket", "name": "Polymarket", "status": "PLANNED"},
            {"id": "macro", "name": "Макрокалендарь", "status": "PLANNED"},
            {"id": "lightgbm", "name": "LightGBM / HAR", "status": "PLANNED"},
            {"id": "webhook", "name": "TradingView Webhook", "status": "VPS_REQUIRED"},
        ],
        "limitations": [
            "GitHub Pages отдаёт статический снимок исследования, не поток котировок.",
            "Историческая симуляция не является прогнозом, опубликованным до события.",
            "Ни одна модель не допущена к торговле; преимущество не заявлено.",
            "Session/D1 и вероятности TP/SL пока не реализованы.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    temporary = output.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(output)
    (store.root / "dashboard.json").write_text(text, encoding="utf-8")
    store.checkpoint()
    return result


def preview_csv(payload: bytes) -> dict:
    frame = pd.read_csv(io.BytesIO(payload), nrows=5)
    return {"columns": list(frame.columns), "preview": json.loads(frame.to_json(orient="records"))}
