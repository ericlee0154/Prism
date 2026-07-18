from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb

from .models import Bar


class PrismRepository:
    """Small DuckDB repository with append-only prediction semantics."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(database_path))

    def initialize(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_bars (
                symbol VARCHAR NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                available_at TIMESTAMPTZ NOT NULL,
                open DOUBLE NOT NULL,
                high DOUBLE NOT NULL,
                low DOUBLE NOT NULL,
                close DOUBLE NOT NULL,
                volume DOUBLE NOT NULL,
                source VARCHAR NOT NULL,
                fetched_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (symbol, timestamp, source)
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_runs (
                sync_id VARCHAR PRIMARY KEY,
                started_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                provider VARCHAR NOT NULL,
                symbols_json VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                rows_written BIGINT NOT NULL,
                error VARCHAR
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_runs (
                backtest_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                metric_version VARCHAR NOT NULL,
                horizon_sessions INTEGER NOT NULL,
                symbols_json VARCHAR NOT NULL,
                parameters_json VARCHAR NOT NULL,
                result_json VARCHAR NOT NULL
            )
            """
        )
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
        # Remove records created by the retired deterministic demo provider.
        # Real provider failures must leave the workspace empty or stale, never
        # silently repopulate it with fixtures.
        self.connection.execute(
            "DELETE FROM predictions WHERE input_snapshot_json LIKE '%demo-seed%'"
        )
        self.connection.execute(
            "DELETE FROM formula_experiments WHERE result_json LIKE '%demo-%'"
        )

    def begin_sync(self, provider: str, symbols: list[str]) -> str:
        sync_id = str(uuid4())
        self.connection.execute(
            """
            INSERT INTO sync_runs
            (sync_id, started_at, provider, symbols_json, status, rows_written)
            VALUES (?, ?, ?, ?, 'running', 0)
            """,
            [sync_id, datetime.now().astimezone(), provider, json.dumps(symbols)],
        )
        return sync_id

    def finish_sync(
        self,
        sync_id: str,
        *,
        status: str,
        rows_written: int,
        error: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE sync_runs
            SET completed_at = ?, status = ?, rows_written = ?, error = ?
            WHERE sync_id = ?
            """,
            [datetime.now().astimezone(), status, rows_written, error, sync_id],
        )

    def upsert_bars(self, bars: list[Bar]) -> int:
        if not bars:
            return 0
        fetched_at = datetime.now().astimezone()
        self.connection.executemany(
            """
            INSERT OR REPLACE INTO market_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [
                    bar.symbol,
                    bar.timestamp,
                    bar.available_at,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    float(bar.volume),
                    bar.source,
                    fetched_at,
                ]
                for bar in bars
            ],
        )
        return len(bars)

    def list_symbols(self) -> list[str]:
        return [
            str(row[0])
            for row in self.connection.execute(
                "SELECT DISTINCT symbol FROM market_bars ORDER BY symbol"
            ).fetchall()
        ]

    def list_bars(
        self,
        symbol: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Bar]:
        clauses = ["symbol = ?"]
        parameters: list[Any] = [symbol.upper()]
        if start is not None:
            clauses.append("timestamp >= ?")
            parameters.append(start)
        if end is not None:
            clauses.append("timestamp <= ?")
            parameters.append(end)
        cursor = self.connection.execute(
            f"""
            SELECT symbol, timestamp, available_at, open, high, low, close,
                   volume, source
            FROM market_bars
            WHERE {' AND '.join(clauses)}
            ORDER BY timestamp
            """,
            parameters,
        )
        return [
            Bar(
                symbol=str(row[0]),
                timestamp=row[1],
                available_at=row[2],
                open=float(row[3]),
                high=float(row[4]),
                low=float(row[5]),
                close=float(row[6]),
                volume=int(row[7]),
                source=str(row[8]),
            )
            for row in cursor.fetchall()
        ]

    def market_summary(self) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT
                COUNT(*) AS bar_count,
                COUNT(DISTINCT symbol) AS symbol_count,
                MIN(timestamp) AS first_observation,
                MAX(timestamp) AS last_observation,
                MAX(available_at) AS data_cutoff,
                MAX(fetched_at) AS last_synced_at
            FROM market_bars
            """
        ).fetchone()
        return {
            "bar_count": int(row[0] or 0),
            "symbol_count": int(row[1] or 0),
            "first_observation": row[2].isoformat() if row[2] else None,
            "last_observation": row[3].isoformat() if row[3] else None,
            "data_cutoff": row[4].isoformat() if row[4] else None,
            "last_synced_at": row[5].isoformat() if row[5] else None,
            "database_bytes": (
                self.database_path.stat().st_size
                if self.database_path.exists()
                else 0
            ),
        }

    def list_sync_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self.connection.execute(
            """
            SELECT sync_id, started_at, completed_at, provider, symbols_json,
                   status, rows_written, error
            FROM sync_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            [limit],
        )
        return [
            {
                "sync_id": row[0],
                "started_at": row[1].isoformat(),
                "completed_at": row[2].isoformat() if row[2] else None,
                "provider": row[3],
                "symbols": json.loads(row[4]),
                "status": row[5],
                "rows_written": int(row[6]),
                "error": row[7],
            }
            for row in cursor.fetchall()
        ]

    def append_backtest(
        self,
        *,
        metric_version: str,
        horizon_sessions: int,
        symbols: list[str],
        parameters: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        backtest_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO backtest_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                backtest_id,
                datetime.now().astimezone(),
                metric_version,
                horizon_sessions,
                json.dumps(symbols, sort_keys=True),
                json.dumps(parameters, sort_keys=True),
                json.dumps(result, sort_keys=True),
            ],
        )
        return backtest_id

    def list_backtests(self, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self.connection.execute(
            """
            SELECT backtest_id, created_at, metric_version, horizon_sessions,
                   symbols_json, parameters_json, result_json
            FROM backtest_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [limit],
        )
        return [
            {
                "backtest_id": row[0],
                "created_at": row[1].isoformat(),
                "metric_version": row[2],
                "horizon_sessions": int(row[3]),
                "symbols": json.loads(row[4]),
                "parameters": json.loads(row[5]),
                "result": json.loads(row[6]),
            }
            for row in cursor.fetchall()
        ]

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
