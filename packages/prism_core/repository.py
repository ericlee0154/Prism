from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb

from .seed import DEMO_CUTOFF, DEMO_LEDGER


class PrismRepository:
    """Small DuckDB repository with append-only prediction semantics."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(database_path))

    def initialize(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                data_cutoff TIMESTAMPTZ NOT NULL,
                symbol VARCHAR NOT NULL,
                horizon VARCHAR NOT NULL,
                direction VARCHAR NOT NULL,
                confidence DOUBLE NOT NULL,
                expected_range VARCHAR NOT NULL,
                actual_outcome VARCHAR NOT NULL,
                outcome VARCHAR NOT NULL,
                formula_version VARCHAR NOT NULL,
                metric_version VARCHAR NOT NULL,
                input_snapshot_json VARCHAR NOT NULL,
                record_hash VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS formula_experiments (
                experiment_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                formula_version VARCHAR NOT NULL,
                horizon VARCHAR NOT NULL,
                weights_json VARCHAR NOT NULL,
                result_json VARCHAR NOT NULL
            )
            """
        )

    def seed_ledger(self, force: bool = False) -> None:
        count = self.connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        if count and not force:
            return
        if force:
            self.connection.execute(
                "DELETE FROM predictions WHERE formula_version = 'core-v0.1'"
            )
        for row in DEMO_LEDGER:
            created_at, symbol, horizon, direction, confidence, expected, actual, outcome, version = row
            created_timestamp = datetime.fromisoformat(created_at)
            historical_cutoff = min(
                created_timestamp.replace(minute=0, second=0, microsecond=0),
                DEMO_CUTOFF,
            )
            self.append_prediction(
                {
                    "created_at": created_at,
                    "data_cutoff": historical_cutoff,
                    "symbol": symbol,
                    "horizon": horizon,
                    "direction": direction,
                    "confidence": confidence,
                    "expected_range": expected,
                    "actual_outcome": actual,
                    "outcome": outcome,
                    "formula_version": version,
                    "metric_version": "price-core-v0.1",
                    "input_snapshot": {"provider": "demo-seed", "sealed": True},
                }
            )

    def append_prediction(self, record: dict[str, Any]) -> dict[str, Any]:
        prediction_id = str(uuid4())
        serialized_snapshot = json.dumps(record["input_snapshot"], sort_keys=True)
        record_hash = _stable_record_hash(
            prediction_id,
            record["created_at"],
            record["symbol"],
            record["horizon"],
            serialized_snapshot,
        )
        self.connection.execute(
            """
            INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                prediction_id,
                record["created_at"],
                record["data_cutoff"],
                record["symbol"],
                record["horizon"],
                record["direction"],
                record["confidence"],
                record["expected_range"],
                record["actual_outcome"],
                record["outcome"],
                record["formula_version"],
                record["metric_version"],
                serialized_snapshot,
                record_hash,
            ],
        )
        return {"prediction_id": prediction_id, "record_hash": record_hash, **record}

    def list_predictions(
        self,
        horizon: str | None = None,
        outcome: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[str] = []
        if horizon:
            clauses.append("horizon = ?")
            parameters.append(horizon)
        if outcome:
            clauses.append("outcome = ?")
            parameters.append(outcome)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cursor = self.connection.execute(
            f"""
            SELECT prediction_id, created_at, data_cutoff, symbol, horizon,
                   direction, confidence, expected_range, actual_outcome,
                   outcome, formula_version, metric_version, record_hash
            FROM predictions
            {where}
            ORDER BY created_at DESC
            """,
            parameters,
        )
        columns = [item[0] for item in cursor.description]
        return [
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in zip(columns, row, strict=True)
            }
            for row in cursor.fetchall()
        ]

    def append_experiment(
        self,
        formula_version: str,
        horizon: str,
        weights: dict[str, float],
        result: dict[str, Any],
    ) -> str:
        experiment_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO formula_experiments VALUES (?, ?, ?, ?, ?, ?)",
            [
                experiment_id,
                datetime.now().astimezone(),
                formula_version,
                horizon,
                json.dumps(weights, sort_keys=True),
                json.dumps(result, sort_keys=True),
            ],
        )
        return experiment_id

    def close(self) -> None:
        self.connection.close()


def _stable_record_hash(*parts: str) -> str:
    import hashlib

    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
