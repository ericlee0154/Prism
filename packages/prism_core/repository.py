from __future__ import annotations

import json
from datetime import datetime
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

import duckdb

from .models import Bar


def _serialized(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class PrismRepository:
    """Small DuckDB repository with append-only prediction semantics."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.connection = duckdb.connect(str(database_path))

    @_serialized
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
            CREATE TABLE IF NOT EXISTS range_analyses (
                analysis_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                symbol VARCHAR NOT NULL,
                requested_start DATE NOT NULL,
                requested_end DATE NOT NULL,
                metric_version VARCHAR NOT NULL,
                result_json VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS event_research_runs (
                run_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                scope VARCHAR NOT NULL,
                symbols_json VARCHAR NOT NULL,
                window_start DATE,
                window_end DATE,
                provider VARCHAR NOT NULL,
                model VARCHAR NOT NULL,
                prompt_version VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                response_id VARCHAR,
                usage_json VARCHAR,
                error VARCHAR
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS research_events (
                event_id VARCHAR PRIMARY KEY,
                dedupe_key VARCHAR UNIQUE NOT NULL,
                first_seen_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                scope VARCHAR NOT NULL,
                symbol VARCHAR,
                event_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                summary VARCHAR NOT NULL,
                event_date_start DATE,
                event_date_end DATE,
                release_timing VARCHAR,
                importance INTEGER NOT NULL,
                confidence DOUBLE NOT NULL,
                regions_json VARCHAR NOT NULL,
                affected_assets_json VARCHAR NOT NULL,
                watch_items_json VARCHAR NOT NULL,
                expectations_json VARCHAR NOT NULL,
                actual_json VARCHAR NOT NULL,
                reaction_json VARCHAR NOT NULL,
                sources_json VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                model VARCHAR NOT NULL,
                prompt_version VARCHAR NOT NULL,
                last_run_id VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS event_observations (
                observation_id VARCHAR PRIMARY KEY,
                event_id VARCHAR NOT NULL,
                observed_at TIMESTAMPTZ NOT NULL,
                phase VARCHAR NOT NULL,
                run_id VARCHAR,
                payload_json VARCHAR NOT NULL,
                sources_json VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS confidence_evidence (
                evidence_id VARCHAR PRIMARY KEY,
                captured_at TIMESTAMPTZ NOT NULL,
                symbol VARCHAR NOT NULL,
                period_start DATE NOT NULL,
                institution VARCHAR,
                category VARCHAR NOT NULL,
                stance INTEGER NOT NULL,
                statement VARCHAR NOT NULL,
                rationale VARCHAR NOT NULL,
                published_date DATE NOT NULL,
                confidence DOUBLE NOT NULL,
                sources_json VARCHAR NOT NULL,
                run_id VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS confidence_snapshots (
                snapshot_key VARCHAR PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                symbol VARCHAR NOT NULL,
                dimension VARCHAR NOT NULL,
                entity VARCHAR NOT NULL,
                frequency VARCHAR NOT NULL,
                period_start DATE NOT NULL,
                score DOUBLE,
                coverage_status VARCHAR NOT NULL,
                evidence_count INTEGER NOT NULL,
                components_json VARCHAR NOT NULL,
                sources_json VARCHAR NOT NULL,
                data_cutoff TIMESTAMPTZ,
                provider VARCHAR NOT NULL,
                model VARCHAR NOT NULL,
                prompt_version VARCHAR NOT NULL,
                run_id VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS instrument_classifications (
                symbol VARCHAR PRIMARY KEY,
                updated_at TIMESTAMPTZ NOT NULL,
                display_name VARCHAR NOT NULL,
                instrument_type VARCHAR NOT NULL,
                categories_json VARCHAR NOT NULL,
                summary VARCHAR NOT NULL,
                summary_zh VARCHAR NOT NULL,
                sources_json VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                model VARCHAR NOT NULL,
                prompt_version VARCHAR NOT NULL,
                run_id VARCHAR NOT NULL
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

    @_serialized
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

    @_serialized
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

    @_serialized
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

    @_serialized
    def list_symbols(self) -> list[str]:
        return [
            str(row[0])
            for row in self.connection.execute(
                "SELECT DISTINCT symbol FROM market_bars ORDER BY symbol"
            ).fetchall()
        ]

    @_serialized
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

    @_serialized
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

    @_serialized
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

    @_serialized
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

    @_serialized
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

    @_serialized
    def append_range_analysis(
        self,
        *,
        symbol: str,
        requested_start: str,
        requested_end: str,
        metric_version: str,
        result: dict[str, Any],
    ) -> str:
        analysis_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO range_analyses VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                analysis_id,
                datetime.now().astimezone(),
                symbol,
                requested_start,
                requested_end,
                metric_version,
                json.dumps(result, sort_keys=True),
            ],
        )
        return analysis_id

    @_serialized
    def list_range_analyses(self, limit: int = 30) -> list[dict[str, Any]]:
        cursor = self.connection.execute(
            """
            SELECT analysis_id, created_at, symbol, requested_start,
                   requested_end, metric_version, result_json
            FROM range_analyses
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [limit],
        )
        return [
            {
                "analysis_id": row[0],
                "created_at": row[1].isoformat(),
                "symbol": row[2],
                "requested_start": row[3].isoformat(),
                "requested_end": row[4].isoformat(),
                "metric_version": row[5],
                "result": json.loads(row[6]),
            }
            for row in cursor.fetchall()
        ]

    @_serialized
    def begin_event_run(
        self,
        *,
        scope: str,
        symbols: list[str],
        window_start: str | None,
        window_end: str | None,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> str:
        run_id = str(uuid4())
        self.connection.execute(
            """
            INSERT INTO event_research_runs
            (run_id, created_at, scope, symbols_json, window_start, window_end,
             provider, model, prompt_version, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running')
            """,
            [
                run_id,
                datetime.now().astimezone(),
                scope,
                json.dumps(symbols),
                window_start,
                window_end,
                provider,
                model,
                prompt_version,
            ],
        )
        return run_id

    @_serialized
    def finish_event_run(
        self,
        run_id: str,
        *,
        status: str,
        response_id: str | None = None,
        usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE event_research_runs
            SET completed_at = ?, status = ?, response_id = ?, usage_json = ?, error = ?
            WHERE run_id = ?
            """,
            [
                datetime.now().astimezone(),
                status,
                response_id,
                json.dumps(usage or {}, sort_keys=True),
                error,
                run_id,
            ],
        )

    @_serialized
    def upsert_research_event(
        self,
        event: dict[str, Any],
        *,
        run_id: str,
    ) -> str:
        existing = self.connection.execute(
            "SELECT event_id FROM research_events WHERE dedupe_key = ?",
            [event["dedupe_key"]],
        ).fetchone()
        now = datetime.now().astimezone()
        event_id = str(existing[0]) if existing else str(uuid4())
        values = [
            event["scope"],
            event.get("symbol"),
            event["event_type"],
            event["status"],
            event["title"],
            event["summary"],
            event.get("event_date_start"),
            event.get("event_date_end"),
            event.get("release_timing"),
            int(event["importance"]),
            float(event["confidence"]),
            json.dumps(event.get("regions", []), sort_keys=True),
            json.dumps(event.get("affected_assets", []), sort_keys=True),
            json.dumps(event.get("watch_items", []), sort_keys=True),
            json.dumps(event.get("expectations", {}), sort_keys=True),
            json.dumps(event.get("actual", {}), sort_keys=True),
            json.dumps(event.get("reaction", {}), sort_keys=True),
            json.dumps(event.get("sources", []), sort_keys=True),
            event["provider"],
            event["model"],
            event["prompt_version"],
            run_id,
        ]
        if existing:
            self.connection.execute(
                """
                UPDATE research_events
                SET updated_at = ?, scope = ?, symbol = ?, event_type = ?,
                    status = ?, title = ?, summary = ?, event_date_start = ?,
                    event_date_end = ?, release_timing = ?, importance = ?,
                    confidence = ?, regions_json = ?, affected_assets_json = ?,
                    watch_items_json = ?, expectations_json = ?, actual_json = ?,
                    reaction_json = ?, sources_json = ?, provider = ?, model = ?,
                    prompt_version = ?, last_run_id = ?
                WHERE event_id = ?
                """,
                [now, *values, event_id],
            )
        else:
            self.connection.execute(
                """
                INSERT INTO research_events
                (event_id, dedupe_key, first_seen_at, updated_at, scope, symbol,
                 event_type, status, title, summary, event_date_start,
                 event_date_end, release_timing, importance, confidence,
                 regions_json, affected_assets_json, watch_items_json,
                 expectations_json, actual_json, reaction_json, sources_json,
                 provider, model, prompt_version, last_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    event_id,
                    event["dedupe_key"],
                    now,
                    now,
                    *values,
                ],
            )
        return event_id

    @_serialized
    def append_event_observation(
        self,
        *,
        event_id: str,
        phase: str,
        run_id: str | None,
        payload: dict[str, Any],
        sources: list[dict[str, str]],
    ) -> str:
        observation_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO event_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                observation_id,
                event_id,
                datetime.now().astimezone(),
                phase,
                run_id,
                json.dumps(payload, sort_keys=True, default=str),
                json.dumps(sources, sort_keys=True),
            ],
        )
        return observation_id

    @_serialized
    def update_event_outcome(
        self,
        event_id: str,
        *,
        status: str,
        actual_event_date: str | None,
        actual: dict[str, Any],
        reaction: dict[str, Any],
        run_id: str,
    ) -> None:
        current = self.connection.execute(
            "SELECT sources_json FROM research_events WHERE event_id = ?",
            [event_id],
        ).fetchone()
        merged_sources: dict[str, dict[str, str]] = {
            source["url"]: source
            for source in json.loads(current[0] if current else "[]")
            if source.get("url")
        }
        for source in actual.get("sources", []):
            if source.get("url"):
                merged_sources[source["url"]] = source
        self.connection.execute(
            """
            UPDATE research_events
            SET updated_at = ?, status = ?,
                event_date_start = COALESCE(?, event_date_start),
                event_date_end = COALESCE(?, event_date_end),
                actual_json = ?, reaction_json = ?, sources_json = ?,
                last_run_id = ?
            WHERE event_id = ?
            """,
            [
                datetime.now().astimezone(),
                status,
                actual_event_date,
                actual_event_date,
                json.dumps(actual, sort_keys=True, default=str),
                json.dumps(reaction, sort_keys=True, default=str),
                json.dumps(list(merged_sources.values()), sort_keys=True),
                run_id,
                event_id,
            ],
        )

    @_serialized
    def list_research_events(
        self,
        *,
        scope: str | None = None,
        symbol: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        statuses: list[str] | None = None,
        prompt_version: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if scope:
            clauses.append("scope = ?")
            parameters.append(scope)
        if symbol:
            clauses.append("symbol = ?")
            parameters.append(symbol.upper())
        if start_date:
            clauses.append(
                "(event_date_end IS NULL OR event_date_end >= CAST(? AS DATE))"
            )
            parameters.append(start_date)
        if end_date:
            clauses.append(
                "(event_date_start IS NULL OR event_date_start <= CAST(? AS DATE))"
            )
            parameters.append(end_date)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            parameters.extend(statuses)
        if prompt_version:
            clauses.append("prompt_version = ?")
            parameters.append(prompt_version)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT event_id, first_seen_at, updated_at, scope, symbol,
                   event_type, status, title, summary, event_date_start,
                   event_date_end, release_timing, importance, confidence,
                   regions_json, affected_assets_json, watch_items_json,
                   expectations_json, actual_json, reaction_json, sources_json,
                   provider, model, prompt_version, last_run_id
            FROM research_events
            {where}
            ORDER BY
                CASE WHEN event_date_start IS NULL THEN 1 ELSE 0 END,
                event_date_start,
                importance DESC,
                updated_at DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()
        return [_event_row_to_dict(row) for row in rows]

    @_serialized
    def get_research_event(self, event_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT event_id, first_seen_at, updated_at, scope, symbol,
                   event_type, status, title, summary, event_date_start,
                   event_date_end, release_timing, importance, confidence,
                   regions_json, affected_assets_json, watch_items_json,
                   expectations_json, actual_json, reaction_json, sources_json,
                   provider, model, prompt_version, last_run_id
            FROM research_events
            WHERE event_id = ?
            """,
            [event_id],
        ).fetchone()
        return _event_row_to_dict(row) if row else None

    @_serialized
    def list_event_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT run_id, created_at, completed_at, scope, symbols_json,
                   window_start, window_end, provider, model, prompt_version,
                   status, response_id, usage_json, error
            FROM event_research_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()
        return [
            {
                "run_id": row[0],
                "created_at": row[1].isoformat(),
                "completed_at": row[2].isoformat() if row[2] else None,
                "scope": row[3],
                "symbols": json.loads(row[4]),
                "window_start": row[5].isoformat() if row[5] else None,
                "window_end": row[6].isoformat() if row[6] else None,
                "provider": row[7],
                "model": row[8],
                "prompt_version": row[9],
                "status": row[10],
                "response_id": row[11],
                "usage": json.loads(row[12] or "{}"),
                "error": row[13],
            }
            for row in rows
        ]

    @_serialized
    def upsert_instrument_classification(
        self,
        classification: dict[str, Any],
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO instrument_classifications
            (symbol, updated_at, display_name, instrument_type, categories_json,
             summary, summary_zh, sources_json, provider, model, prompt_version,
             run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol) DO UPDATE SET
                updated_at = excluded.updated_at,
                display_name = excluded.display_name,
                instrument_type = excluded.instrument_type,
                categories_json = excluded.categories_json,
                summary = excluded.summary,
                summary_zh = excluded.summary_zh,
                sources_json = excluded.sources_json,
                provider = excluded.provider,
                model = excluded.model,
                prompt_version = excluded.prompt_version,
                run_id = excluded.run_id
            """,
            [
                classification["symbol"].upper(),
                datetime.now().astimezone(),
                classification["display_name"],
                classification["instrument_type"],
                json.dumps(classification["categories"], sort_keys=True),
                classification["summary"],
                classification["summary_zh"],
                json.dumps(classification["sources"], sort_keys=True),
                classification["provider"],
                classification["model"],
                classification["prompt_version"],
                classification["run_id"],
            ],
        )

    @_serialized
    def list_instrument_classifications(
        self,
        *,
        symbols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        parameters: list[Any] = []
        where = ""
        if symbols:
            cleaned = sorted({symbol.upper() for symbol in symbols})
            placeholders = ", ".join("?" for _ in cleaned)
            where = f"WHERE symbol IN ({placeholders})"
            parameters.extend(cleaned)
        rows = self.connection.execute(
            f"""
            SELECT symbol, updated_at, display_name, instrument_type,
                   categories_json, summary, summary_zh, sources_json,
                   provider, model, prompt_version, run_id
            FROM instrument_classifications
            {where}
            ORDER BY symbol
            """,
            parameters,
        ).fetchall()
        return [
            {
                "symbol": row[0],
                "updated_at": row[1].isoformat(),
                "display_name": row[2],
                "instrument_type": row[3],
                "categories": json.loads(row[4]),
                "summary": row[5],
                "summary_zh": row[6],
                "sources": json.loads(row[7]),
                "provider": row[8],
                "model": row[9],
                "prompt_version": row[10],
                "run_id": row[11],
            }
            for row in rows
        ]

    @_serialized
    def append_confidence_evidence(
        self,
        *,
        symbol: str,
        period_start: str,
        evidence: dict[str, Any],
        sources: list[dict[str, str]],
        run_id: str,
    ) -> str:
        evidence_id = str(uuid4())
        self.connection.execute(
            """
            INSERT INTO confidence_evidence
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                evidence_id,
                datetime.now().astimezone(),
                symbol.upper(),
                period_start,
                evidence.get("institution"),
                evidence["category"],
                int(evidence["stance"]),
                evidence["statement"],
                evidence["rationale"],
                evidence["published_date"],
                float(evidence["confidence"]),
                json.dumps(sources, sort_keys=True),
                run_id,
            ],
        )
        return evidence_id

    @_serialized
    def upsert_confidence_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO confidence_snapshots
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                snapshot["snapshot_key"],
                datetime.now().astimezone(),
                snapshot["symbol"].upper(),
                snapshot["dimension"],
                snapshot.get("entity") or "",
                snapshot["frequency"],
                snapshot["period_start"],
                snapshot.get("score"),
                snapshot["coverage_status"],
                int(snapshot["evidence_count"]),
                json.dumps(snapshot.get("components", {}), sort_keys=True),
                json.dumps(snapshot.get("sources", []), sort_keys=True),
                snapshot.get("data_cutoff"),
                snapshot["provider"],
                snapshot["model"],
                snapshot["prompt_version"],
                snapshot["run_id"],
            ],
        )

    @_serialized
    def list_confidence_snapshots(
        self,
        *,
        symbol: str | None = None,
        dimension: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            parameters.append(symbol.upper())
        if dimension:
            clauses.append("dimension = ?")
            parameters.append(dimension)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT snapshot_key, created_at, symbol, dimension, entity,
                   frequency, period_start, score, coverage_status,
                   evidence_count, components_json, sources_json, data_cutoff,
                   provider, model, prompt_version, run_id
            FROM confidence_snapshots
            {where}
            ORDER BY period_start DESC, dimension, entity
            LIMIT ?
            """,
            parameters,
        ).fetchall()
        return [
            {
                "snapshot_key": row[0],
                "created_at": row[1].isoformat(),
                "symbol": row[2],
                "dimension": row[3],
                "entity": row[4] or None,
                "frequency": row[5],
                "period_start": row[6].isoformat(),
                "score": float(row[7]) if row[7] is not None else None,
                "coverage_status": row[8],
                "evidence_count": int(row[9]),
                "components": json.loads(row[10]),
                "sources": json.loads(row[11]),
                "data_cutoff": row[12].isoformat() if row[12] else None,
                "provider": row[13],
                "model": row[14],
                "prompt_version": row[15],
                "run_id": row[16],
            }
            for row in rows
        ]

    @_serialized
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

    @_serialized
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

    @_serialized
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

    @_serialized
    def close(self) -> None:
        self.connection.close()


def _event_row_to_dict(row) -> dict[str, Any]:
    return {
        "event_id": row[0],
        "first_seen_at": row[1].isoformat(),
        "updated_at": row[2].isoformat(),
        "scope": row[3],
        "symbol": row[4],
        "event_type": row[5],
        "status": row[6],
        "title": row[7],
        "summary": row[8],
        "event_date_start": row[9].isoformat() if row[9] else None,
        "event_date_end": row[10].isoformat() if row[10] else None,
        "release_timing": row[11],
        "importance": int(row[12]),
        "confidence": float(row[13]),
        "regions": json.loads(row[14]),
        "affected_assets": json.loads(row[15]),
        "watch_items": json.loads(row[16]),
        "expectations": json.loads(row[17]),
        "actual": json.loads(row[18]),
        "reaction": json.loads(row[19]),
        "sources": json.loads(row[20]),
        "provider": row[21],
        "model": row[22],
        "prompt_version": row[23],
        "last_run_id": row[24],
    }


def _stable_record_hash(*parts: str) -> str:
    import hashlib

    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
