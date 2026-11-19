"""Explicit source, calendar and timestamp contracts. No automatic instrument aliases."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()
    ).hexdigest()


class Session(BaseModel):
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    open_minute: int = Field(default=0, ge=0, le=1439)
    close_minute: int = Field(default=1440, ge=1, le=1440)

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls, values: list[int]) -> list[int]:
        if not values or any(x < 0 or x > 6 for x in values):
            raise ValueError("weekdays must contain ISO weekdays 0..6")
        return sorted(set(values))


class Calendar(BaseModel):
    timezone: str = "UTC"
    verified: bool = False
    sessions: list[Session] = Field(default_factory=lambda: [Session()])
    closed_dates: list[str] = Field(default_factory=list)
    # Explicit local-date overrides cover holidays and shortened sessions.
    overrides: dict[str, list[Session]] = Field(default_factory=dict)

    @field_validator("timezone")
    @classmethod
    def zone_exists(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    def mask(self, times: pd.DatetimeIndex) -> np.ndarray:
        local = times.tz_convert(self.timezone)
        minute = np.asarray(local.hour * 60 + local.minute)
        days = np.asarray(local.day_of_week)
        dates = np.asarray(local.strftime("%Y-%m-%d"))

        def session_mask(sessions: list[Session]) -> np.ndarray:
            result = np.zeros(len(times), dtype=bool)
            for session in sessions:
                if session.close_minute > session.open_minute:
                    result |= (
                        np.isin(days, session.weekdays)
                        & (minute >= session.open_minute)
                        & (minute < session.close_minute)
                    )
                else:
                    result |= (np.isin(days, session.weekdays) & (minute >= session.open_minute)) | (
                        np.isin((days - 1) % 7, session.weekdays) & (minute < session.close_minute)
                    )
            return result

        result = session_mask(self.sessions)
        result[np.isin(dates, self.closed_dates)] = False
        for date, sessions in self.overrides.items():
            chosen = dates == date
            result[chosen] = session_mask(sessions)[chosen]
        return result


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    instrument_id: Literal["XAUUSD", "NAS100", "SPX500", "XAGUSD"]
    source: str = Field(min_length=1, max_length=80)
    source_symbol: str = Field(min_length=3, max_length=100)
    asset_class: Literal["spot", "cfd", "index", "futures", "synthetic"]
    timeframe_minutes: Literal[1, 15, 60] = 1
    timestamp_timezone: str = "UTC"
    timestamp_unit: Literal["s", "ms"] = "s"
    standard_ohlc: bool = True
    quote_currency: str = "USD"
    price_precision: int = Field(default=2, ge=0, le=8)
    tick_size: float = Field(default=0.01, gt=0)
    available_volume_type: Literal["tick", "exchange", "none", "synthetic"] = "none"
    execution_instrument_id: str | None = None
    roll_policy: str | None = None
    data_license: str = "UNCONFIRMED"
    publish_allowed: bool = False
    is_demo: bool = False
    calendar: Calendar = Field(default_factory=Calendar)
    columns: dict[str, str] = Field(default_factory=dict)
    max_staleness_minutes: int = Field(default=5, ge=1, le=1440)

    @field_validator("timestamp_timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @model_validator(mode="after")
    def enforce_source(self) -> "Profile":
        if not self.standard_ohlc:
            raise ValueError("Only standard time-based OHLC candles are supported")
        if ":" not in self.source_symbol:
            raise ValueError("Use an explicit PROVIDER:SYMBOL; aliases are not inferred")
        if self.is_demo != (self.asset_class == "synthetic"):
            raise ValueError("Synthetic data must be marked DEMO, and vice versa")
        if self.is_demo and not self.source.startswith("demo"):
            raise ValueError("DEMO needs a demo source namespace")
        if self.asset_class == "futures" and not self.roll_policy:
            raise ValueError("Futures require an explicit roll policy")
        return self

    @property
    def dataset_id(self) -> str:
        return digest(self.model_dump())[:24]
