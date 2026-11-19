"""Two preregistered baselines. Historical simulation is never forward evidence."""

import hashlib
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .contracts import Profile, digest, utc_now
from .store import Store

CONFIDENCES = (0.5, 0.8, 0.9, 0.95)
MODELS = ("B0_seasonal_v1", "B1_vol_scaled_v1")
POLICY = {
    "min_train": 100,
    "lookback": 1000,
    "development_fraction": 0.6,
    "validation_fraction": 0.2,
    "ewma_alpha": 0.06,
    "bootstrap_seed": 42,
    "bootstrap_repetitions": 500,
}


def feature_snapshot(bars: pd.DataFrame, as_of: pd.Timestamp) -> dict:
    past = bars[bars.bar_close_utc <= as_of].sort_values("bar_close_utc")
    if len(past) < 3:
        return {"status": "INSUFFICIENT_DATA"}
    returns = past.close.pct_change().dropna()
    return {
        "as_of_utc": as_of.isoformat(),
        "anchor": float(past.close.iloc[-1]),
        "volatility": float(
            np.sqrt(returns.pow(2).ewm(alpha=POLICY["ewma_alpha"], adjust=False).mean().iloc[-1])
        ),
        "features_version": "past_returns_ewma_v1",
    }


def labels(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars.copy().reset_index(drop=True)
    previous_close = frame.close.shift(1)
    scale = (
        frame.close.pct_change().pow(2).ewm(alpha=POLICY["ewma_alpha"], adjust=False).mean().pow(0.5).shift(1)
    )
    contiguous = frame.bar_close_utc.shift(1) == frame.bar_open_utc
    result = pd.DataFrame(
        {
            "as_of": frame.bar_open_utc,
            "end": frame.bar_close_utc,
            "anchor": previous_close,
            "high": frame.high,
            "low": frame.low,
            "close": frame.close,
            "scale": scale,
            "up": ((frame.high - previous_close) / previous_close).clip(lower=0),
            "down": ((previous_close - frame.low) / previous_close).clip(lower=0),
        }
    )
    return result[contiguous & (scale > 0) & scale.notna()].reset_index(drop=True)


def predict(history: pd.DataFrame, target: pd.Series, model: str) -> dict:
    # horizon_end is simulated availability of the label. Actual imports remain separate.
    known = history[history.end <= target.as_of].tail(POLICY["lookback"])
    if len(known) < POLICY["min_train"]:
        raise ValueError("INSUFFICIENT_DATA")
    seasonal = known[known.as_of.dt.hour == target.as_of.hour]
    chosen = seasonal if len(seasonal) >= POLICY["min_train"] else known
    if model == MODELS[0]:
        up, down, multiplier = chosen.up.to_numpy(), chosen.down.to_numpy(), 1.0
    elif model == MODELS[1]:
        up = (chosen.up / chosen.scale).to_numpy()
        down = (chosen.down / chosen.scale).to_numpy()
        multiplier = float(target.scale)
    else:
        raise ValueError("Unregistered model")
    intervals = {}
    for confidence in CONFIDENCES:
        marginal_quantile = 1 - (1 - confidence) / 2
        u = float(np.quantile(up, marginal_quantile, method="higher")) * multiplier
        d = float(np.quantile(down, marginal_quantile, method="higher")) * multiplier
        intervals[str(confidence)] = {
            "lower": float(target.anchor * (1 - d)),
            "upper": float(target.anchor * (1 + u)),
        }
    return {
        "intervals": intervals,
        "training_n": len(chosen),
        "group": "hour_utc" if len(seasonal) >= POLICY["min_train"] else "pooled",
        "training_end_utc": chosen.end.max().isoformat(),
    }


def envelope_score(lower: float, upper: float, low: float, high: float, confidence: float) -> float:
    """Winkler-like whole-candle score. Not the scalar close-return interval score."""
    return upper - lower + 2 / (1 - confidence) * (max(0, lower - low) + max(0, high - upper))


def pinball(y: float, q: float, level: float) -> float:
    residual = y - q
    return max(level * residual, (level - 1) * residual)


def paired_bootstrap(baseline: pd.DataFrame, challenger: pd.DataFrame) -> dict:
    if list(baseline.as_of) != list(challenger.as_of):
        raise ValueError("Paired comparison requires identical timestamps")
    delta = pd.DataFrame(
        {
            "day": baseline.as_of.dt.strftime("%Y-%m-%d"),
            "improvement": baseline.score_90.to_numpy() - challenger.score_90.to_numpy(),
        }
    )
    groups = delta.groupby("day").improvement.agg(["sum", "count"])
    if len(groups) < 5:
        return {"n": len(delta), "day_blocks": len(groups), "ci95": None, "status": "INSUFFICIENT_BLOCKS"}
    rng = np.random.default_rng(POLICY["bootstrap_seed"])
    draws = rng.integers(0, len(groups), size=(POLICY["bootstrap_repetitions"], len(groups)))
    means = groups["sum"].to_numpy()[draws].sum(axis=1) / groups["count"].to_numpy()[draws].sum(axis=1)
    return {
        "n": len(delta),
        "day_blocks": len(groups),
        "mean_score_improvement_bps": float(delta.improvement.mean()),
        "ci95": [float(x) for x in np.quantile(means, [0.025, 0.975])],
        "status": "RESEARCH_ONLY",
    }


def summarize(rows: pd.DataFrame) -> dict:
    coverages = {str(c): float(rows[f"covered_{c}"].mean()) for c in CONFIDENCES}
    regimes = []
    for regime in ["low", "normal", "high"]:
        subset = rows[rows.regime == regime]
        regimes.append(
            {
                "regime": regime,
                "n": len(subset),
                "coverage_90": float(subset["covered_0.9"].mean()) if len(subset) else None,
            }
        )
    monthly = []
    for month, subset in rows.groupby(rows.as_of.dt.strftime("%Y-%m")):
        monthly.append(
            {
                "month": month,
                "n": len(subset),
                "coverage_90": float(subset["covered_0.9"].mean()),
                "score_90_bps": float(subset.score_90.mean()),
            }
        )
    hourly = [
        {"hour_utc": int(hour), "n": len(s), "coverage_90": float(s["covered_0.9"].mean())}
        for hour, s in rows.groupby(rows.as_of.dt.hour)
    ]
    return {
        "n": len(rows),
        "coverage": coverages,
        "mean_width_90": float(rows.width_90.mean()),
        "median_width_90": float(rows.width_90.median()),
        "score_90_bps": float(rows.score_90.mean()),
        "pinball_90_bps": float(rows.pinball_90.mean()),
        "by_regime": regimes,
        "by_month": monthly,
        "by_hour": hourly,
    }


def approval_gate(metrics: dict, is_demo: bool, forward_count: int = 0) -> dict:
    reasons = []
    if is_demo:
        reasons.append("DEMO_DATA")
    if metrics["n"] < 500:
        reasons.append("OOS_N_BELOW_500")
    if not 0.87 <= metrics["coverage"]["0.9"] <= 0.93:
        reasons.append("COVERAGE_OUTSIDE_87_93")
    if any(r["n"] >= 50 and abs(r["coverage_90"] - 0.9) > 0.07 for r in metrics["by_regime"]):
        reasons.append("REGIME_CALIBRATION_FAILED")
    if forward_count < 500:
        reasons.append("FORWARD_EVIDENCE_MISSING")
    # Historical simulation alone never promotes a model.
    return {
        "status": "DEMO" if is_demo else "BACKTEST_ONLY",
        "approved": False,
        "reasons": reasons,
        "is_trading_qualified": False,
    }


def check_issue_time(available_at: pd.Timestamp, horizon_start: pd.Timestamp, mode: str) -> None:
    if mode != "historical_simulation" and available_at >= horizon_start:
        raise ValueError("LATE_FORECAST: not available before target window")


def run_research(store: Store, bars: pd.DataFrame, profile: Profile, minutes: int, dataset_hash: str) -> dict:
    samples = labels(bars)
    count = len(samples)
    if count < 180:
        return {
            "timeframe": f"M{minutes}" if minutes < 60 else f"H{minutes // 60}",
            "minutes": minutes,
            "status": "INSUFFICIENT_DATA",
            "n_bars": len(bars),
            "required_label_count": 180,
            "models": [],
            "history": [],
            "live_forecast": None,
        }
    validation_start = max(POLICY["min_train"], int(count * 0.6))
    test_start = max(validation_start + 1, int(count * 0.8))
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    run_id = digest(
        {
            "dataset_hash": dataset_hash,
            "profile": profile.model_dump(),
            "minutes": minutes,
            "policy": POLICY,
            "code_hash": code_hash,
        }
    )
    generated = utc_now()
    forecasts, outcomes = [], []
    metric_rows: dict[str, list[dict]] = {model: [] for model in MODELS}
    for i in range(validation_start, count):
        target = samples.iloc[i]
        history = samples.iloc[:i]
        scale_quantiles = history.scale.tail(POLICY["lookback"]).quantile([0.33, 0.67])
        regime = (
            "low"
            if target.scale < scale_quantiles.iloc[0]
            else ("high" if target.scale > scale_quantiles.iloc[1] else "normal")
        )
        for model in MODELS:
            predicted = predict(history, target, model)
            record = {
                "as_of": target.as_of,
                "regime": regime,
                "split": "validation" if i < test_start else "test",
            }
            for confidence, bounds in predicted["intervals"].items():
                record[f"covered_{confidence}"] = (
                    bounds["lower"] <= target.low and target.high <= bounds["upper"]
                )
            q90 = predicted["intervals"]["0.9"]
            record["width_90"] = q90["upper"] - q90["lower"]
            record["score_90"] = (
                envelope_score(q90["lower"], q90["upper"], target.low, target.high, 0.9)
                / target.anchor
                * 10000
            )
            record["pinball_90"] = (
                pinball(float(target.up), (q90["upper"] / target.anchor - 1), 0.95)
                + pinball(float(target.down), (1 - q90["lower"] / target.anchor), 0.95)
            ) * 10000
            metric_rows[model].append(record)
            if i >= test_start:
                forecast_id = digest({"run_id": run_id, "model": model, "as_of": target.as_of.isoformat()})
                forecasts.append(
                    {
                        "forecast_id": forecast_id,
                        "run_id": run_id,
                        "dataset_hash": dataset_hash,
                        "dataset_id": profile.dataset_id,
                        "instrument_id": profile.instrument_id,
                        "source_id": f"{profile.source}/{profile.source_symbol}",
                        "model_version": model,
                        "timeframe_minutes": minutes,
                        "mode": "historical_simulation",
                        "issued_at_utc": generated,
                        "available_at_utc": generated,
                        "as_of_utc": target.as_of.isoformat(),
                        "horizon_start_utc": target.as_of.isoformat(),
                        "horizon_end_utc": target.end.isoformat(),
                        "anchor_price": float(target.anchor),
                        "forecast_quantiles": predicted["intervals"],
                        "training_n": predicted["training_n"],
                        "training_group": predicted["group"],
                        "training_end_utc": predicted["training_end_utc"],
                        "regime": regime,
                        "quality_status": "DEMO" if profile.is_demo else "BACKTEST_ONLY",
                        "eligible_for_forward_validation": False,
                        "is_trading_qualified": False,
                    }
                )
                outcomes.append(
                    {
                        "forecast_id": forecast_id,
                        "realized_high": float(target.high),
                        "realized_low": float(target.low),
                        "realized_close": float(target.close),
                        "outcome_available_at_utc": target.end.isoformat(),
                        "evaluated_at_utc": generated,
                        "joint_covered_90": bool(record["covered_0.9"]),
                        "width_90": float(record["width_90"]),
                        "score_90_bps": float(record["score_90"]),
                    }
                )
    models = []
    test_frames = []
    for model in MODELS:
        frame = pd.DataFrame(metric_rows[model])
        test = frame[frame.split == "test"].reset_index(drop=True)
        test_frames.append(test)
        metrics = summarize(test)
        models.append(
            {
                "id": model,
                "name": "Сезонные квантили" if model == MODELS[0] else "Масштабирование волатильности",
                "role": "baseline" if model == MODELS[0] else "challenger",
                "test": metrics,
                "validation": summarize(frame[frame.split == "validation"].reset_index(drop=True)),
                "gate": approval_gate(metrics, profile.is_demo),
            }
        )
    paired = paired_bootstrap(*test_frames)
    paired["coverage_comparable"] = (
        abs(models[0]["test"]["coverage"]["0.9"] - models[1]["test"]["coverage"]["0.9"]) <= 0.02
    )
    paired["superiority_proven"] = bool(
        paired["coverage_comparable"]
        and paired.get("ci95")
        and paired["ci95"][0] > 0
        and all(m["test"]["n"] >= 500 for m in models)
        and not profile.is_demo
    )
    store.append_batch("forecasts", forecasts, "forecast_id")
    store.append_batch("outcomes", outcomes, "forecast_id")
    experiment = {
        "run_id": run_id,
        "dataset_hash": dataset_hash,
        "code_hash": code_hash,
        "git_sha": os.getenv("GITHUB_SHA", "LOCAL_WORKTREE"),
        "created_at_utc": generated,
        "hypothesis": "B1 reduces whole-candle 90% envelope score vs B0 at comparable joint coverage",
        "policy": POLICY,
        "model_candidates": list(MODELS),
        "split_scheme": "chronological 60/20/20; fixed candidates, no test tuning; non-overlapping windows",
        "split": {
            "validation_start_utc": samples.iloc[validation_start].as_of.isoformat(),
            "test_start_utc": samples.iloc[test_start].as_of.isoformat(),
            "last_label_end_utc": samples.iloc[-1].end.isoformat(),
        },
        "models": models,
        "paired": paired,
        "selection": "B0 fixed benchmark. No production promotion.",
        "mode": "historical_simulation",
    }
    experiment = store.append("experiments", run_id, experiment)
    # Return original persisted issue timestamps, never fresh replacements on replay.
    with store.connect() as db:
        import json

        persisted = {
            r[0]: json.loads(r[1])
            for r in db.execute(
                "SELECT id,payload FROM forecasts WHERE json_extract(payload,'$.run_id')=?", [run_id]
            ).fetchall()
        }
        persisted_outcomes = {
            r[0]: json.loads(r[1])
            for r in db.execute(
                "SELECT outcomes.id,outcomes.payload FROM outcomes JOIN forecasts ON outcomes.id=forecasts.id WHERE json_extract(forecasts.payload,'$.run_id')=?",
                [run_id],
            ).fetchall()
        }
    recent = [
        {**persisted[f["forecast_id"]], "outcome": persisted_outcomes[f["forecast_id"]]}
        for f in forecasts
        if f["model_version"] == MODELS[0]
    ][-120:]
    return {
        "minutes": minutes,
        "timeframe": f"M{minutes}" if minutes < 60 else f"H{minutes // 60}",
        "status": "DEMO" if profile.is_demo else "BACKTEST_ONLY",
        "n_bars": len(bars),
        "run_id": run_id,
        "models": experiment["models"],
        "paired": experiment["paired"],
        "split": experiment["split"],
        "history": recent,
        "live_forecast": None,
        "live_status": "NO_FORECAST",
        "forward_count": 0,
    }


def first_touch(bars_m1: pd.DataFrame, direction: str, tp: float, sl: float) -> str:
    """Observed historical path classification, NOT a model of future probability."""
    if direction not in {"long", "short"}:
        raise ValueError("Invalid direction")
    for bar in bars_m1.itertuples():
        take = bar.high >= tp if direction == "long" else bar.low <= tp
        stop = bar.low <= sl if direction == "long" else bar.high >= sl
        if take and stop:
            return "AMBIGUOUS"
        if take:
            return "TP"
        if stop:
            return "SL"
    return "NEITHER"
