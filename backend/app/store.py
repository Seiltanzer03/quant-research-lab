"""Raw files and dataset versions are immutable; SQLite journals are append-only."""

import json
import sqlite3
from pathlib import Path

import duckdb
import pandas as pd

from .contracts import digest, utc_now


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "metadata.sqlite"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS imports (
                  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS datasets (
                  id TEXT PRIMARY KEY, profile TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS forecasts (
                  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outcomes (
                  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments (
                  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
            """)
            for table in ["imports", "forecasts", "outcomes", "experiments"]:
                for operation in ["UPDATE", "DELETE"]:
                    db.execute(
                        f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only journal'); END"
                    )

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=30)

    def append(self, table: str, item_id: str, payload: dict) -> dict:
        if table not in {"imports", "forecasts", "outcomes", "experiments"}:
            raise ValueError("Unsupported journal")
        with self.connect() as db:
            old = db.execute(f"SELECT payload FROM {table} WHERE id=?", [item_id]).fetchone()
            if old:
                return json.loads(old[0])
            db.execute(
                f"INSERT INTO {table} VALUES (?,?,?)",
                [item_id, utc_now(), json.dumps(payload, sort_keys=True, allow_nan=False)],
            )
        return payload

    def items(self, table: str, limit: int = 500, offset: int = 0) -> list[dict]:
        if table not in {"imports", "forecasts", "outcomes", "experiments"}:
            raise ValueError("Unsupported journal")
        with self.connect() as db:
            rows = db.execute(
                f"SELECT payload FROM {table} ORDER BY rowid DESC LIMIT ? OFFSET ?",
                [min(limit, 1000), max(0, offset)],
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def append_batch(self, table: str, records: list[dict], key: str) -> None:
        if table not in {"forecasts", "outcomes"}:
            raise ValueError("Unsupported batch journal")
        with self.connect() as db:
            db.executemany(
                f"INSERT OR IGNORE INTO {table} VALUES (?,?,?)",
                [(r[key], utc_now(), json.dumps(r, sort_keys=True, allow_nan=False)) for r in records],
            )

    def read_dataset(self, dataset_id: str) -> pd.DataFrame:
        with self.connect() as db:
            row = db.execute("SELECT snapshot FROM datasets WHERE id=?", [dataset_id]).fetchone()
        if not row:
            return pd.DataFrame()
        # Values are bound parameters; no SQL interpolation of user paths.
        with duckdb.connect() as db:
            return db.execute(
                "SELECT * FROM read_parquet(?) ORDER BY bar_open_utc", [str(self.root / row[0])]
            ).df()

    def save_dataset(self, dataset_id: str, frame: pd.DataFrame, profile: dict) -> str:
        normalized = frame.drop(columns=["received_at_utc"], errors="ignore").to_json(
            orient="records", date_format="iso", double_precision=15
        )
        snapshot_hash = digest({"profile": profile, "bars": normalized})
        relative = Path("clean") / dataset_id / f"{snapshot_hash}.parquet"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            frame.to_parquet(target, index=False)
        with self.connect() as db:
            db.execute(
                "INSERT INTO datasets VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot WHERE datasets.snapshot != excluded.snapshot",
                [dataset_id, json.dumps(profile), str(relative)],
            )
        return snapshot_hash

    def dataset_profiles(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT profile FROM datasets ORDER BY id").fetchall()
        return [json.loads(row[0]) for row in rows]

    def checkpoint(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
