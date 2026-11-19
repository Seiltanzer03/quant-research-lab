"""Optional local API. Bind to 127.0.0.1. Pages never runs this server."""

import json
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, ValidationError, model_validator

from .contracts import Profile
from .ingestion import import_csv
from .store import Store

app = FastAPI(
    title="Quant Research Lab", version="0.1.0", description="Local research API; no broker/order endpoints"
)


def get_store() -> Store:
    return Store(Path(os.getenv("LAB_DATA_DIR", "data")))


def snapshot() -> dict:
    file = get_store().root / "dashboard.json"
    if not file.exists():
        raise HTTPException(503, "Run python -m backend.app.cli build --auto-demo first")
    return json.loads(file.read_text())


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok", "service": "research-local", "auto_execution": False}


@app.get("/readyz")
def ready() -> dict:
    data = snapshot()
    return {"status": "ready", "mode": data["mode"], "market_feed": "NOT_CONNECTED"}


@app.get("/v1/instruments")
def instruments() -> list[dict]:
    return [d["profile"] for d in snapshot()["datasets"]]


@app.get("/v1/dashboard")
def dashboard() -> dict:
    return snapshot()


@app.get("/v1/quality/report")
def quality() -> list[dict]:
    return [{"dataset_id": d["dataset_id"], **d["quality"]} for d in snapshot()["datasets"]]


@app.get("/v1/forecasts/history")
def history(
    limit: Annotated[int, Query(ge=1, le=1000)] = 100, offset: Annotated[int, Query(ge=0)] = 0
) -> dict:
    return {
        "items": get_store().items("forecasts", limit, offset),
        "limit": limit,
        "offset": offset,
        "mode": "historical_simulation",
    }


@app.get("/v1/forecasts/latest")
def latest() -> dict:
    return {"status": "NO_FORECAST", "forecast": None, "reason": "No continuous feed or approved live model"}


@app.get("/v1/experiments")
def experiments(limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> dict:
    return {"items": get_store().items("experiments", limit)}


@app.post("/v1/imports/tradingview-csv")
async def upload_csv(file: Annotated[UploadFile, File()], profile_json: Annotated[str, Form()]) -> dict:
    payload = await file.read(25 * 1024 * 1024 + 1)
    try:
        profile = Profile.model_validate_json(profile_json)
        return import_csv(get_store(), payload, profile)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc


class Scenario(BaseModel):
    direction: Literal["long", "short"]
    entry: float = Field(gt=0, allow_inf_nan=False)
    tp: float = Field(gt=0, allow_inf_nan=False)
    sl: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def levels(self) -> "Scenario":
        if self.direction == "long" and not self.sl < self.entry < self.tp:
            raise ValueError("Long needs SL < Entry < TP")
        if self.direction == "short" and not self.tp < self.entry < self.sl:
            raise ValueError("Short needs TP < Entry < SL")
        return self


@app.post("/v1/scenarios/evaluate")
def scenario(payload: Scenario) -> dict:
    return {
        "reward_risk_before_costs": abs(payload.tp - payload.entry) / abs(payload.entry - payload.sl),
        "p_tp": None,
        "p_sl": None,
        "p_tp_first": None,
        "expected_r": None,
        "status": "PROBABILITIES_NOT_VALIDATED",
        "is_trading_qualified": False,
    }
