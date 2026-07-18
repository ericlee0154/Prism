from __future__ import annotations

import hashlib
import math
import os
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from .ai_events import (
    PROMPT_VERSION,
    OpenAIEventResearchProvider,
    OpenAIQuotaExceeded,
)
from .backtest import BACKTEST_VERSION, walk_forward_backtest
from .codex_cli_events import CodexCliEventResearchProvider
from .event_reaction import REACTION_VERSION, compute_event_reaction
from .forecast import historical_analog_forecast
from .metrics import CATALOG, METRIC_VERSION, compute_price_metrics
from .providers.massive import MassiveMarketDataProvider, MassiveQuotaExceeded
from .repository import PrismRepository


def _percentile(values: list[float], value: float) -> float:
    if len(values) <= 1:
        return 50.0
    below = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    return round(100 * (below + 0.5 * equal) / len(values), 1)


def _normalized_path(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high == low:
        return [50.0 for _ in values]
    return [round(12 + 82 * (value - low) / (high - low), 1) for value in values]


class PrismService:
    """Local-only research service backed exclusively by stored provider data."""

    def __init__(self, repository: PrismRepository) -> None:
        self.repository = repository
        api_key = os.getenv("MASSIVE_API_KEY", "").strip()
        self.provider = MassiveMarketDataProvider(api_key=api_key) if api_key else None
        self.ai_provider_mode = (
            os.getenv("PRISM_AI_PROVIDER", "codex_cli").strip().lower()
        )
        self.ai_configuration_error: str | None = None
        if self.ai_provider_mode == "codex_cli":
            self.ai_provider = CodexCliEventResearchProvider()
            self.ai_configuration_error = self.ai_provider.configuration_error
        elif self.ai_provider_mode == "openai":
            self.ai_provider = OpenAIEventResearchProvider(
                api_key=os.getenv("OPENAI_API_KEY", "").strip()
            )
            if not self.ai_provider.configured:
                self.ai_configuration_error = "OPENAI_API_KEY is not configured"
        elif self.ai_provider_mode in {"disabled", "none", "off"}:
            self.ai_provider = None
            self.ai_configuration_error = "AI research is disabled"
        else:
            self.ai_provider = None
            self.ai_configuration_error = (
                f"Unknown PRISM_AI_PROVIDER: {self.ai_provider_mode}"
            )

    @property
    def provider_name(self) -> str | None:
        return self.provider.name if self.provider else None

    @property
    def provider_configured(self) -> bool:
        return self.provider is not None

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_provider and self.ai_provider.configured)

    @property
    def ai_model(self) -> str | None:
        return self.ai_provider.model if self.ai_provider else None

    @property
    def ai_provider_name(self) -> str | None:
        return self.ai_provider.name if self.ai_provider else None

    def _require_ai_provider(self) -> None:
        if not self.ai_configured:
            raise RuntimeError(
                self.ai_configuration_error
                or "AI research provider is not configured"
            )

    def sync_market_data(
        self,
        symbols: list[str],
        years: int = 2,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        if not self.provider:
            raise RuntimeError("MASSIVE_API_KEY is not configured")
        cleaned = sorted(
            {
                symbol.strip().upper()
                for symbol in symbols
                if symbol.strip()
            }
        )
        if not cleaned:
            raise ValueError("At least one symbol is required")
        if len(cleaned) > 100:
            raise ValueError("A single sync is limited to 100 symbols")
        if years < 1 or years > 20:
            raise ValueError("Years must be between 1 and 20")

        end = (
            datetime.combine(end_date, time.max, tzinfo=UTC)
            if end_date
            else datetime.now(UTC)
        )
        start = (
            datetime.combine(start_date, time.min, tzinfo=UTC)
            if start_date
            else end - timedelta(days=366 * years)
        )
        if start >= end:
            raise ValueError("Start date must precede end date")
        if end > datetime.now(UTC) + timedelta(days=1):
            raise ValueError("End date cannot be in the future")
        sync_id = self.repository.begin_sync(self.provider.name, cleaned)
        rows_written = 0
        failures: list[dict[str, str]] = []
        not_attempted: list[str] = []
        for index, symbol in enumerate(cleaned):
            try:
                bars = self.provider.bars(symbol, start, end)
                rows_written += self.repository.upsert_bars(bars)
            except MassiveQuotaExceeded as error:
                failures.append({"symbol": symbol, "error": str(error)})
                not_attempted = cleaned[index + 1 :]
                break
            except Exception as error:
                failures.append({"symbol": symbol, "error": str(error)})

        status = "complete" if not failures else "partial" if rows_written else "failed"
        error_text = (
            "; ".join(f"{item['symbol']}: {item['error']}" for item in failures)
            if failures
            else None
        )
        self.repository.finish_sync(
            sync_id,
            status=status,
            rows_written=rows_written,
            error=error_text,
        )
        summary = self.repository.market_summary()
        coverage = {}
        for symbol in cleaned:
            stored = self.repository.list_bars(symbol, start=start, end=end)
            coverage[symbol] = {
                "bar_count": len(stored),
                "first_observation": (
                    stored[0].timestamp.astimezone(UTC).isoformat() if stored else None
                ),
                "last_observation": (
                    stored[-1].timestamp.astimezone(UTC).isoformat() if stored else None
                ),
            }
        return {
            "sync_id": sync_id,
            "status": status,
            "provider": self.provider.name,
            "symbols": cleaned,
            "rows_written": rows_written,
            "failures": failures,
            "not_attempted": not_attempted,
            "requested_start": start.date().isoformat(),
            "requested_end": end.date().isoformat(),
            "coverage": coverage,
            "market": summary,
        }

    def analyze_range(
        self,
        symbol: str,
        *,
        start_date: date,
        end_date: date,
    ) -> dict:
        ticker = symbol.strip().upper()
        if not ticker:
            raise ValueError("Symbol is required")
        if start_date >= end_date:
            raise ValueError("Start date must precede end date")
        start = datetime.combine(start_date, time.min, tzinfo=UTC)
        end = datetime.combine(end_date, time.max, tzinfo=UTC)
        bars = self.repository.list_bars(ticker, start=start, end=end)
        if not bars:
            raise ValueError("No stored bars exist in the requested range")
        if len(bars) < 21:
            raise ValueError("At least 21 stored sessions are required")

        cutoff = max(bar.available_at for bar in bars)
        snapshot = compute_price_metrics(bars, cutoff)
        actual_start = bars[0].timestamp.astimezone(UTC).date()
        actual_end = bars[-1].timestamp.astimezone(UTC).date()
        coverage_warnings: list[str] = []
        if actual_start > start_date:
            coverage_warnings.append("requested_start_precedes_stored_data")
        if actual_end < end_date - timedelta(days=4):
            coverage_warnings.append("requested_end_exceeds_stored_data")

        forecasts = {
            str(horizon): historical_analog_forecast(
                bars,
                horizon_sessions=horizon,
            )
            for horizon in (10, 30, 90)
        }
        horizon_ends = {
            str(horizon): actual_end
            + timedelta(days=math.ceil(horizon * 7 / 5) + 4)
            for horizon in (10, 30, 90)
        }
        scheduled_events = []
        for event in self.repository.list_research_events(
            scope="company",
            symbol=ticker,
            start_date=(actual_end + timedelta(days=1)).isoformat(),
            end_date=horizon_ends["90"].isoformat(),
            statuses=["scheduled", "date_uncertain"],
            prompt_version=PROMPT_VERSION,
        ):
            if not event["event_date_start"]:
                continue
            event_date = date.fromisoformat(event["event_date_start"])
            scheduled_events.append(
                {
                    **event,
                    "forecast_horizons": [
                        int(horizon)
                        for horizon, horizon_end in horizon_ends.items()
                        if event_date <= horizon_end
                    ],
                }
            )
        result = {
            "symbol": ticker,
            "requested_start": start_date.isoformat(),
            "requested_end": end_date.isoformat(),
            "actual_start": actual_start.isoformat(),
            "actual_end": actual_end.isoformat(),
            "bar_count": len(bars),
            "data_cutoff": cutoff.isoformat(),
            "source": bars[-1].source,
            "metric_version": snapshot.metric_version,
            "metrics": snapshot.values,
            "coverage_warnings": coverage_warnings,
            "forecasts": forecasts,
            "forecast_horizon_ends": {
                horizon: value.isoformat()
                for horizon, value in horizon_ends.items()
            },
            "scheduled_events": scheduled_events,
            "series": [
                {
                    "date": bar.timestamp.astimezone(UTC).date().isoformat(),
                    "close": bar.close,
                }
                for bar in bars
            ],
        }
        analysis_id = self.repository.append_range_analysis(
            symbol=ticker,
            requested_start=start_date.isoformat(),
            requested_end=end_date.isoformat(),
            metric_version=snapshot.metric_version,
            result=result,
        )
        return {"analysis_id": analysis_id, **result}

    def event_center(
        self,
        *,
        scope: str | None = None,
        symbol: str | None = None,
        limit: int = 200,
    ) -> dict:
        events = self.repository.list_research_events(
            scope=scope,
            symbol=symbol,
            prompt_version=PROMPT_VERSION,
            limit=limit,
        )
        classifications = self.repository.list_instrument_classifications(
            symbols=self.repository.list_symbols(),
        )
        events = [
            _event_with_portfolio_matches(event, classifications)
            for event in events
        ]
        today = date.today()
        due_count = sum(
            event["scope"] == "company"
            and event["status"] in {"scheduled", "date_uncertain"}
            and event["event_date_start"] is not None
            and date.fromisoformat(event["event_date_start"]) <= today
            for event in events
        )
        return {
            "provider": self.ai_provider_name,
            "provider_configured": self.ai_configured,
            "configuration_error": self.ai_configuration_error,
            "model": self.ai_model,
            "prompt_version": PROMPT_VERSION,
            "due_event_count": due_count,
            "events": events,
            "runs": self.repository.list_event_runs(),
            "portfolio_classifications": classifications,
            "classification_coverage": _classification_coverage(
                self.repository.list_symbols(),
                classifications,
            ),
        }

    def instrument_classification_center(self) -> dict:
        symbols = self.repository.list_symbols()
        classifications = self.repository.list_instrument_classifications(
            symbols=symbols,
        )
        return {
            "provider": self.ai_provider_name,
            "provider_configured": self.ai_configured,
            "model": self.ai_model,
            "prompt_version": PROMPT_VERSION,
            "items": classifications,
            "coverage": _classification_coverage(symbols, classifications),
        }

    def refresh_instrument_classifications(self) -> dict:
        self._require_ai_provider()
        assert self.ai_provider is not None
        symbols = self.repository.list_symbols()
        if not symbols:
            raise ValueError("No tracked symbols are stored")
        run_id = self.repository.begin_event_run(
            scope="instrument_classification",
            symbols=symbols,
            window_start=None,
            window_end=date.today().isoformat(),
            provider=self.ai_provider.name,
            model=self.ai_provider.model,
            prompt_version=PROMPT_VERSION,
        )
        try:
            research = self.ai_provider.instrument_classifications(
                symbols=symbols,
                as_of=date.today(),
            )
            tracked = set(symbols)
            stored: list[str] = []
            for classification_model in research.payload.instruments:
                item = classification_model.model_dump(mode="json")
                ticker = item["symbol"].upper()
                if ticker not in tracked:
                    continue
                sources = _sources_for_references(
                    item["source_references"],
                    research.sources,
                )
                if not sources:
                    continue
                self.repository.upsert_instrument_classification(
                    {
                        **item,
                        "symbol": ticker,
                        "sources": sources,
                        "provider": self.ai_provider.name,
                        "model": research.model,
                        "prompt_version": PROMPT_VERSION,
                        "run_id": run_id,
                    }
                )
                stored.append(ticker)
            self.repository.finish_event_run(
                run_id,
                status="complete",
                response_id=research.response_id,
                usage=research.usage,
            )
        except OpenAIQuotaExceeded as error:
            self.repository.finish_event_run(
                run_id,
                status="quota",
                error=str(error),
            )
            raise
        except Exception as error:
            self.repository.finish_event_run(
                run_id,
                status="failed",
                error=str(error),
            )
            raise
        center = self.instrument_classification_center()
        return {
            "run_id": run_id,
            "status": "complete",
            "stored": sorted(stored),
            **center,
        }

    def confidence_center(
        self,
        *,
        symbol: str | None = None,
        limit: int = 500,
    ) -> dict:
        return {
            "provider": self.ai_provider_name,
            "provider_configured": self.ai_configured,
            "configuration_error": self.ai_configuration_error,
            "model": self.ai_model,
            "prompt_version": PROMPT_VERSION,
            "snapshots": self.repository.list_confidence_snapshots(
                symbol=symbol,
                limit=limit,
            ),
        }

    def refresh_confidence(self, *, symbol: str) -> dict:
        self._require_ai_provider()
        assert self.ai_provider is not None
        ticker = symbol.strip().upper()
        if ticker not in self.repository.list_symbols():
            raise ValueError(f"No stored market data for {ticker}")
        as_of = date.today()
        week_start = as_of - timedelta(days=as_of.weekday())
        month_start = as_of.replace(day=1)
        run_id = self.repository.begin_event_run(
            scope="confidence",
            symbols=[ticker],
            window_start=(as_of - timedelta(days=45)).isoformat(),
            window_end=as_of.isoformat(),
            provider=self.ai_provider.name,
            model=self.ai_provider.model,
            prompt_version=PROMPT_VERSION,
        )
        try:
            research = self.ai_provider.confidence_evidence(
                symbol=ticker,
                as_of=as_of,
            )
            evidence_rows: list[dict[str, Any]] = []
            for item in research.payload.evidence:
                evidence = item.model_dump(mode="json")
                sources = _sources_for_urls(
                    evidence["source_urls"],
                    research.sources,
                )
                self.repository.append_confidence_evidence(
                    symbol=ticker,
                    period_start=week_start.isoformat(),
                    evidence=evidence,
                    sources=sources,
                    run_id=run_id,
                )
                evidence_rows.append({**evidence, "sources": sources})

            institution_groups: dict[str, list[dict[str, Any]]] = {}
            brand_evidence: list[dict[str, Any]] = []
            for evidence in evidence_rows:
                institution = (evidence.get("institution") or "").strip()
                if institution:
                    institution_groups.setdefault(institution, []).append(evidence)
                elif evidence["category"] not in {
                    "institutional_rating",
                    "institutional_outlook",
                }:
                    brand_evidence.append(evidence)

            snapshots: list[dict[str, Any]] = []
            for institution, items in sorted(institution_groups.items()):
                score = _evidence_confidence_score(items)
                snapshot = _confidence_snapshot(
                    symbol=ticker,
                    dimension="institution",
                    entity=institution,
                    frequency="weekly",
                    period_start=week_start.isoformat(),
                    score=score,
                    coverage_status="complete",
                    evidence=items,
                    components={
                        "formula": "50 + 25 × confidence-weighted ordinal stance",
                        "stance_scale": [-2, -1, 0, 1, 2],
                    },
                    data_cutoff=None,
                    provider=self.ai_provider.name,
                    model=research.model,
                    run_id=run_id,
                )
                self.repository.upsert_confidence_snapshot(snapshot)
                snapshots.append(snapshot)

            bars = self.repository.list_bars(ticker)
            market_component = _long_term_market_component(bars)
            institutional_component = (
                sum(
                    _evidence_confidence_score(items)
                    for items in institution_groups.values()
                )
                / len(institution_groups)
                if institution_groups
                else None
            )
            brand_component = (
                _evidence_confidence_score(brand_evidence)
                if brand_evidence
                else None
            )
            component_scores = {
                "market_price": market_component.get("score"),
                "institutional": institutional_component,
                "brand_evidence": brand_component,
            }
            weights = {
                "market_price": 0.50,
                "institutional": 0.30,
                "brand_evidence": 0.20,
            }
            available_weight = sum(
                weights[key]
                for key, value in component_scores.items()
                if value is not None
            )
            long_term_score = (
                sum(
                    float(value) * weights[key]
                    for key, value in component_scores.items()
                    if value is not None
                )
                / available_weight
                if available_weight
                else None
            )
            long_term_evidence = [
                item for items in institution_groups.values() for item in items
            ] + brand_evidence
            long_term = _confidence_snapshot(
                symbol=ticker,
                dimension="company_long_term",
                entity="",
                frequency="monthly",
                period_start=month_start.isoformat(),
                score=long_term_score,
                coverage_status=(
                    "complete"
                    if all(value is not None for value in component_scores.values())
                    else "partial"
                    if long_term_score is not None
                    else "unavailable"
                ),
                evidence=long_term_evidence,
                components={
                    "formula": "available-component weighted mean",
                    "weights": weights,
                    "scores": component_scores,
                    "market_detail": market_component,
                },
                data_cutoff=market_component.get("data_cutoff"),
                provider=f"prism+{self.ai_provider.name}",
                model=research.model,
                run_id=run_id,
            )
            self.repository.upsert_confidence_snapshot(long_term)
            snapshots.append(long_term)
            self.repository.finish_event_run(
                run_id,
                status="complete",
                response_id=research.response_id,
                usage=research.usage,
            )
        except OpenAIQuotaExceeded as error:
            self.repository.finish_event_run(
                run_id,
                status="quota",
                error=str(error),
            )
            raise
        except Exception as error:
            self.repository.finish_event_run(
                run_id,
                status="failed",
                error=str(error),
            )
            raise
        return {
            "run_id": run_id,
            "status": "complete",
            "symbol": ticker,
            "snapshots": snapshots,
        }

    def refresh_world_events(
        self,
        *,
        lookback_days: int = 7,
        lookahead_days: int = 30,
    ) -> dict:
        self._require_ai_provider()
        assert self.ai_provider is not None
        if lookback_days < 1 or lookback_days > 90:
            raise ValueError("lookback_days must be between 1 and 90")
        if lookahead_days < 1 or lookahead_days > 180:
            raise ValueError("lookahead_days must be between 1 and 180")
        as_of = date.today()
        window_start = as_of - timedelta(days=lookback_days)
        window_end = as_of + timedelta(days=lookahead_days)
        run_id = self.repository.begin_event_run(
            scope="world",
            symbols=[],
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            provider=self.ai_provider.name,
            model=self.ai_provider.model,
            prompt_version=PROMPT_VERSION,
        )
        try:
            research = self.ai_provider.world_events(
                as_of=as_of,
                lookback_days=lookback_days,
                lookahead_days=lookahead_days,
            )
            event_ids = [
                self._store_world_event(
                    item.model_dump(mode="json"),
                    run_id=run_id,
                    model=research.model,
                    sources=research.sources,
                )
                for item in research.payload.events
            ]
            self.repository.finish_event_run(
                run_id,
                status="complete",
                response_id=research.response_id,
                usage=research.usage,
            )
        except OpenAIQuotaExceeded as error:
            self.repository.finish_event_run(
                run_id,
                status="quota",
                error=str(error),
            )
            raise
        except Exception as error:
            self.repository.finish_event_run(
                run_id,
                status="failed",
                error=str(error),
            )
            raise
        return {
            "run_id": run_id,
            "status": "complete",
            "event_count": len(event_ids),
            "events": [
                event
                for event_id in event_ids
                if (event := self.repository.get_research_event(event_id))
            ],
        }

    def refresh_company_events(
        self,
        *,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> dict:
        self._require_ai_provider()
        assert self.ai_provider is not None
        ticker = symbol.strip().upper()
        if ticker not in self.repository.list_symbols():
            raise ValueError(f"No stored market data for {ticker}")
        if start_date >= end_date:
            raise ValueError("Start date must precede end date")
        if (end_date - start_date).days > 366:
            raise ValueError("A company event window cannot exceed 366 days")
        run_id = self.repository.begin_event_run(
            scope="company",
            symbols=[ticker],
            window_start=start_date.isoformat(),
            window_end=end_date.isoformat(),
            provider=self.ai_provider.name,
            model=self.ai_provider.model,
            prompt_version=PROMPT_VERSION,
        )
        try:
            research = self.ai_provider.company_events(
                symbol=ticker,
                start_date=start_date,
                end_date=end_date,
                as_of=date.today(),
            )
            event_ids = [
                self._store_company_event(
                    item.model_dump(mode="json"),
                    run_id=run_id,
                    model=research.model,
                    sources=research.sources,
                )
                for item in research.payload.events
                if item.symbol.upper() == ticker
            ]
            self.repository.finish_event_run(
                run_id,
                status="complete",
                response_id=research.response_id,
                usage=research.usage,
            )
        except OpenAIQuotaExceeded as error:
            self.repository.finish_event_run(
                run_id,
                status="quota",
                error=str(error),
            )
            raise
        except Exception as error:
            self.repository.finish_event_run(
                run_id,
                status="failed",
                error=str(error),
            )
            raise
        return {
            "run_id": run_id,
            "status": "complete",
            "symbol": ticker,
            "event_count": len(event_ids),
            "events": [
                event
                for event_id in event_ids
                if (event := self.repository.get_research_event(event_id))
            ],
        }

    def resolve_event(self, event_id: str) -> dict:
        self._require_ai_provider()
        assert self.ai_provider is not None
        event = self.repository.get_research_event(event_id)
        if not event:
            raise ValueError("Unknown event")
        run_id = self.repository.begin_event_run(
            scope="resolution",
            symbols=[event["symbol"]] if event["symbol"] else [],
            window_start=event["event_date_start"],
            window_end=date.today().isoformat(),
            provider=self.ai_provider.name,
            model=self.ai_provider.model,
            prompt_version=PROMPT_VERSION,
        )
        try:
            research = self.ai_provider.event_outcome(
                event=event,
                as_of=date.today(),
            )
            outcome = research.payload.model_dump(mode="json")
            sources = _sources_for_urls(outcome["source_urls"], research.sources)
            self.repository.append_event_observation(
                event_id=event_id,
                phase="post_event",
                run_id=run_id,
                payload=outcome,
                sources=sources,
            )
            if outcome["event_status"] != "not_yet_available":
                event_for_reaction = {
                    **event,
                    "event_date_start": (
                        outcome["actual_event_date"]
                        or event["event_date_start"]
                    ),
                }
                reaction = compute_event_reaction(
                    self.repository,
                    event_for_reaction,
                )
                self.repository.update_event_outcome(
                    event_id,
                    status=outcome["event_status"],
                    actual_event_date=outcome["actual_event_date"],
                    actual={**outcome, "sources": sources},
                    reaction=reaction,
                    run_id=run_id,
                )
            self.repository.finish_event_run(
                run_id,
                status="complete",
                response_id=research.response_id,
                usage=research.usage,
            )
        except OpenAIQuotaExceeded as error:
            self.repository.finish_event_run(
                run_id,
                status="quota",
                error=str(error),
            )
            raise
        except Exception as error:
            self.repository.finish_event_run(
                run_id,
                status="failed",
                error=str(error),
            )
            raise
        return {
            "run_id": run_id,
            "status": "complete",
            "event": self.repository.get_research_event(event_id),
            "resolution": outcome,
        }

    def resolve_due_events(self, *, limit: int = 5) -> dict:
        self._require_ai_provider()
        if limit < 1 or limit > 20:
            raise ValueError("limit must be between 1 and 20")
        today = date.today()
        due = [
            event
            for event in self.repository.list_research_events(
                scope="company",
                statuses=["scheduled", "date_uncertain"],
                prompt_version=PROMPT_VERSION,
            )
            if event["event_date_start"]
            and date.fromisoformat(event["event_date_start"]) <= today
        ][:limit]
        completed: list[str] = []
        quota_stopped = False
        for event in due:
            try:
                self.resolve_event(event["event_id"])
                completed.append(event["event_id"])
            except OpenAIQuotaExceeded:
                quota_stopped = True
                break
        return {
            "status": "quota" if quota_stopped else "complete",
            "attempted": len(completed) + int(quota_stopped),
            "completed": completed,
            "not_attempted": [
                event["event_id"] for event in due[len(completed) + int(quota_stopped) :]
            ],
        }

    def recompute_event_reactions(self) -> dict:
        events = self.repository.list_research_events(
            scope="company",
            statuses=["occurred"],
            prompt_version=PROMPT_VERSION,
        )
        run_id = self.repository.begin_event_run(
            scope="reaction",
            symbols=sorted(
                {event["symbol"] for event in events if event["symbol"]}
            ),
            window_start=None,
            window_end=date.today().isoformat(),
            provider="prism",
            model=REACTION_VERSION,
            prompt_version=REACTION_VERSION,
        )
        updated: list[str] = []
        try:
            for event in events:
                reaction = compute_event_reaction(self.repository, event)
                self.repository.update_event_outcome(
                    event["event_id"],
                    status=event["status"],
                    actual_event_date=event["event_date_start"],
                    actual=event["actual"],
                    reaction=reaction,
                    run_id=run_id,
                )
                self.repository.append_event_observation(
                    event_id=event["event_id"],
                    phase="market_reaction",
                    run_id=run_id,
                    payload=reaction,
                    sources=[],
                )
                updated.append(event["event_id"])
            self.repository.finish_event_run(run_id, status="complete")
        except Exception as error:
            self.repository.finish_event_run(
                run_id,
                status="failed",
                error=str(error),
            )
            raise
        return {
            "run_id": run_id,
            "status": "complete",
            "updated": updated,
        }

    def _store_world_event(
        self,
        item: dict,
        *,
        run_id: str,
        model: str,
        sources: list[dict[str, str]],
    ) -> str:
        event = {
            "dedupe_key": _event_dedupe_key("world", None, item),
            "scope": "world",
            "symbol": None,
            "event_type": item["event_type"],
            "status": item["status"],
            "title": item["title"],
            "summary": item["summary"],
            "event_date_start": item["event_date_start"],
            "event_date_end": item["event_date_end"],
            "release_timing": None,
            "importance": item["importance"],
            "confidence": item["confidence"],
            "regions": item["regions"],
            "affected_assets": item["affected_assets"],
            "watch_items": item["watch_items"],
            "expectations": {
                "why_markets_care": item["why_markets_care"],
                "impact_assessment": item["impact"],
                "translation_zh": item["translation_zh"],
            },
            "actual": {},
            "reaction": {},
            "sources": _sources_for_references(
                item["source_references"],
                sources,
            ),
            "provider": self.ai_provider.name,
            "model": model,
            "prompt_version": PROMPT_VERSION,
        }
        event_id = self.repository.upsert_research_event(event, run_id=run_id)
        self.repository.append_event_observation(
            event_id=event_id,
            phase="world_snapshot",
            run_id=run_id,
            payload=item,
            sources=event["sources"],
        )
        return event_id

    def _store_company_event(
        self,
        item: dict,
        *,
        run_id: str,
        model: str,
        sources: list[dict[str, str]],
    ) -> str:
        ticker = item["symbol"].upper()
        event = {
            "dedupe_key": _event_dedupe_key("company", ticker, item),
            "scope": "company",
            "symbol": ticker,
            "event_type": item["event_type"],
            "status": item["status"],
            "title": item["title"],
            "summary": item["summary"],
            "event_date_start": item["event_date_start"],
            "event_date_end": item["event_date_end"],
            "release_timing": item["release_timing"],
            "importance": item["importance"],
            "confidence": item["confidence"],
            "regions": [],
            "affected_assets": [ticker],
            "watch_items": item["watch_items"],
            "expectations": {
                "market_expectations": item["market_expectations"],
                "bullish_scenario": item["bullish_scenario"],
                "bearish_scenario": item["bearish_scenario"],
                "impact_assessment": item["impact"],
                "translation_zh": item["translation_zh"],
            },
            "actual": {},
            "reaction": {},
            "sources": _sources_for_references(
                item["source_references"],
                sources,
            ),
            "provider": self.ai_provider.name,
            "model": model,
            "prompt_version": PROMPT_VERSION,
        }
        event_id = self.repository.upsert_research_event(event, run_id=run_id)
        self.repository.append_event_observation(
            event_id=event_id,
            phase=(
                "scheduled"
                if item["status"] in {"scheduled", "date_uncertain"}
                else "current"
            ),
            run_id=run_id,
            payload=item,
            sources=event["sources"],
        )
        return event_id

    def _raw_snapshots(self) -> list[dict]:
        snapshots: list[dict] = []
        for symbol in self.repository.list_symbols():
            bars = self.repository.list_bars(symbol)
            if len(bars) < 21:
                continue
            cutoff = max(bar.available_at for bar in bars)
            snapshot = compute_price_metrics(bars, cutoff)
            latest = bars[-1]
            previous = bars[-2] if len(bars) > 1 else None
            change = (
                (latest.close / previous.close - 1.0) * 100
                if previous and previous.close
                else None
            )
            snapshots.append(
                {
                    "symbol": symbol,
                    "price": latest.close,
                    "change": change,
                    "bars": _normalized_path([bar.close for bar in bars[-22:]]),
                    "bar_count": len(bars),
                    "first_observation": bars[0].timestamp.astimezone(UTC).isoformat(),
                    "last_observation": latest.timestamp.astimezone(UTC).isoformat(),
                    "data_cutoff": cutoff.astimezone(UTC).isoformat(),
                    "metrics": snapshot.values,
                    "metric_version": snapshot.metric_version,
                    "source": latest.source,
                }
            )
        return snapshots

    def scan(self, horizon: str = "30D", search: str = "") -> list[dict]:
        snapshots = self._raw_snapshots()
        if not snapshots:
            return []
        momentum_values = [
            float(item["metrics"]["return_20d"]) for item in snapshots
        ]
        trend_values = [
            float(item["metrics"]["distance_ma20"]) for item in snapshots
        ]
        volume_values = [
            float(item["metrics"]["volume_zscore_20d"]) for item in snapshots
        ]
        volatility_values = [
            float(item["metrics"]["realized_volatility_20d"]) for item in snapshots
        ]
        benchmark = next(
            (
                float(item["metrics"]["return_20d"])
                for item in snapshots
                if item["symbol"] == "SPY"
            ),
            0.0,
        )
        relative_values = [
            float(item["metrics"]["return_20d"]) - benchmark for item in snapshots
        ]
        needle = search.strip().upper()
        results: list[dict] = []
        for item, relative_value in zip(snapshots, relative_values, strict=True):
            if needle and needle not in item["symbol"]:
                continue
            metrics = item["metrics"]
            momentum = _percentile(momentum_values, float(metrics["return_20d"]))
            relative = _percentile(relative_values, relative_value)
            trend = _percentile(trend_values, float(metrics["distance_ma20"]))
            volume = _percentile(volume_values, float(metrics["volume_zscore_20d"]))
            volatility = _percentile(
                volatility_values,
                float(metrics["realized_volatility_20d"]),
            )
            base_score = (
                0.30 * momentum
                + 0.25 * relative
                + 0.20 * trend
                + 0.15 * volume
                + 0.10 * (100 - volatility)
            )
            horizon_adjustment = {
                "10D": 4.0 * math.tanh(float(metrics["return_5d"]) * 10),
                "30D": 0.0,
                "90D": 4.0 * math.tanh(-float(metrics["drawdown_60d"]) * -3),
            }[horizon]
            score = round(max(0.0, min(100.0, base_score + horizon_adjustment)), 1)
            if score >= 65:
                signal = "Positive relative setup"
            elif score <= 35:
                signal = "Weak relative setup"
            else:
                signal = "No strong relative edge"
            results.append(
                {
                    **item,
                    "name": item["symbol"],
                    "sector": None,
                    "momentum": momentum,
                    "relativeStrength": relative,
                    "trendQuality": trend,
                    "volumeConfirmation": volume,
                    "volatility": volatility,
                    "score10": round(
                        max(
                            0.0,
                            min(
                                100.0,
                                base_score
                                + 4.0
                                * math.tanh(float(metrics["return_5d"]) * 10),
                            ),
                        ),
                        1,
                    ),
                    "score30": round(base_score, 1),
                    "score90": round(
                        max(
                            0.0,
                            min(
                                100.0,
                                base_score
                                + 4.0
                                * math.tanh(
                                    -float(metrics["drawdown_60d"]) * -3
                                ),
                            ),
                        ),
                        1,
                    ),
                    "score": score,
                    "signal": signal,
                    "signalCopy": (
                        "Computed only from stored Massive bars available by the "
                        "displayed cutoff. No demo fallback is used."
                    ),
                    "dataQuality": round(min(100.0, item["bar_count"] / 252 * 100), 1),
                }
            )
        return sorted(results, key=lambda item: item["score"], reverse=True)

    def stock_detail(self, symbol: str) -> dict | None:
        return next(
            (item for item in self.scan() if item["symbol"] == symbol.upper()),
            None,
        )

    def overview(self) -> dict:
        items = self.scan()
        summary = self.repository.market_summary()
        positive = sum(
            float(item["metrics"]["return_20d"]) > 0 for item in items
        )
        breadth = positive / len(items) if items else None
        if breadth is None:
            regime = None
        elif breadth >= 0.65:
            regime = "Broad positive breadth"
        elif breadth <= 0.35:
            regime = "Broad negative breadth"
        else:
            regime = "Mixed breadth"
        latest_backtest = self.repository.list_backtests(limit=1)
        return {
            "provider": self.provider_name,
            "provider_configured": self.provider_configured,
            "market": summary,
            "market_regime": {
                "label": regime,
                "breadth": breadth,
            },
            "candidate_coverage": {
                "passing": sum(item["score30"] >= 60 for item in items),
                "universe": len(items),
            },
            "latest_backtest": latest_backtest[0] if latest_backtest else None,
            "ledger": {
                "records": len(self.repository.list_predictions()),
            },
        }

    def metric_catalog(self) -> list[dict]:
        return [
            {
                "name": item.name,
                "description": item.description,
                "formula": item.formula,
                "required_inputs": item.required_inputs,
                "output_type": item.output_type,
                "version": item.version,
            }
            for item in CATALOG
        ]

    def run_backtest(self, horizon_sessions: int) -> dict:
        histories = {
            symbol: self.repository.list_bars(symbol)
            for symbol in self.repository.list_symbols()
        }
        histories = {
            symbol: bars
            for symbol, bars in histories.items()
            if len(bars) >= 61 + horizon_sessions
        }
        result = walk_forward_backtest(
            histories,
            horizon_sessions=horizon_sessions,
        )
        backtest_id = self.repository.append_backtest(
            metric_version=METRIC_VERSION,
            horizon_sessions=horizon_sessions,
            symbols=sorted(histories),
            parameters={
                "rebalance_every_sessions": 5,
                "execution": "signal close to future close",
                "version": BACKTEST_VERSION,
            },
            result=result,
        )
        return {"backtest_id": backtest_id, **result}

    def predictions(
        self,
        horizon: str | None = None,
        outcome: str | None = None,
    ) -> list[dict]:
        return self.repository.list_predictions(horizon=horizon, outcome=outcome)

    def seal_prediction(
        self,
        symbol: str,
        horizon: Literal["10D", "30D", "90D"],
        formula_version: str,
    ) -> dict:
        detail = self.stock_detail(symbol)
        if detail is None:
            raise ValueError("No stored market data exists for this symbol")
        score = detail[{"10D": "score10", "30D": "score30", "90D": "score90"}[horizon]]
        direction = "Bullish" if score >= 60 else "Bearish" if score < 40 else "Neutral"
        created_at = datetime.now(UTC)
        return self.repository.append_prediction(
            {
                "created_at": created_at.isoformat(),
                "data_cutoff": detail["data_cutoff"],
                "symbol": symbol,
                "horizon": horizon,
                "direction": direction,
                "confidence": abs(score - 50) * 2,
                "expected_range": "Not calibrated",
                "actual_outcome": "Pending",
                "outcome": "Pending",
                "formula_version": formula_version,
                "metric_version": detail["metric_version"],
                "input_snapshot": {
                    "metrics": detail["metrics"],
                    "scores": {
                        "10D": detail["score10"],
                        "30D": detail["score30"],
                        "90D": detail["score90"],
                    },
                    "data_cutoff": detail["data_cutoff"],
                    "provider": detail["source"],
                },
            }
        )

    def pipeline_status(self) -> dict:
        summary = self.repository.market_summary()
        return {
            "status": "ready" if summary["bar_count"] else "empty",
            "provider": self.provider_name,
            "provider_configured": self.provider_configured,
            "market": summary,
            "sync_runs": self.repository.list_sync_runs(),
            "backtests": self.repository.list_backtests(),
            "analyses": self.repository.list_range_analyses(),
            "metric_version": METRIC_VERSION,
        }


def _event_dedupe_key(
    scope: str,
    symbol: str | None,
    item: dict,
) -> str:
    raw = "|".join(
        [
            scope,
            symbol or "",
            str(item.get("event_type") or ""),
            str(item.get("event_date_start") or ""),
            " ".join(str(item.get("title") or "").lower().split()),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sources_for_urls(
    urls: list[str],
    sources: list[dict[str, str]],
) -> list[dict[str, str]]:
    requested = set(urls)
    return [
        source
        for source in sources
        if source.get("url") in requested
    ]


def _sources_for_references(
    references: list[dict[str, str]],
    sources: list[dict[str, str]],
) -> list[dict[str, str]]:
    source_map = {
        source.get("url"): source
        for source in sources
        if source.get("url")
    }
    matched: list[dict[str, str]] = []
    for reference in references:
        url = reference.get("url")
        source = source_map.get(url)
        if not source:
            continue
        matched.append(
            {
                "url": source["url"],
                "title": source.get("title", ""),
                "language": reference.get("language", "UNKNOWN"),
            }
        )
    return matched


def _classification_coverage(
    symbols: list[str],
    classifications: list[dict[str, Any]],
) -> dict[str, Any]:
    tracked = sorted({symbol.upper() for symbol in symbols})
    classified = {
        item["symbol"].upper()
        for item in classifications
    }
    return {
        "tracked_count": len(tracked),
        "classified_count": len(classified.intersection(tracked)),
        "unclassified_symbols": [
            symbol for symbol in tracked if symbol not in classified
        ],
    }


def _event_with_portfolio_matches(
    event: dict[str, Any],
    classifications: list[dict[str, Any]],
) -> dict[str, Any]:
    impact = event.get("expectations", {}).get("impact_assessment", {})
    impact_categories = {
        str(category)
        for category in impact.get("categories", [])
        if category
    }
    matches: list[dict[str, Any]] = []
    for classification in classifications:
        ticker = classification["symbol"].upper()
        profile_categories = {
            str(category)
            for category in classification.get("categories", [])
            if category
        }
        shared = sorted(impact_categories.intersection(profile_categories))
        direct = bool(event.get("symbol") == ticker)
        if shared or direct:
            matches.append(
                {
                    "symbol": ticker,
                    "display_name": classification["display_name"],
                    "matched_categories": shared,
                    "direct_company_match": direct,
                }
            )
    matches.sort(
        key=lambda item: (
            not item["direct_company_match"],
            -len(item["matched_categories"]),
            item["symbol"],
        )
    )
    return {
        **event,
        "portfolio_matches": matches,
    }


def _evidence_confidence_score(evidence: list[dict[str, Any]]) -> float:
    total_weight = sum(max(float(item["confidence"]), 0.05) for item in evidence)
    weighted_stance = sum(
        int(item["stance"]) * max(float(item["confidence"]), 0.05)
        for item in evidence
    ) / total_weight
    return round(max(0.0, min(100.0, 50.0 + 25.0 * weighted_stance)), 1)


def _long_term_market_component(bars: list[Any]) -> dict[str, Any]:
    if len(bars) < 127:
        return {
            "score": None,
            "coverage_status": "unavailable",
            "reason": "At least 127 stored sessions are required",
            "data_cutoff": bars[-1].available_at.isoformat() if bars else None,
        }
    closes = [float(bar.close) for bar in bars]
    return_126 = closes[-1] / closes[-127] - 1.0
    return_252 = closes[-1] / closes[-253] - 1.0 if len(closes) >= 253 else None
    trailing = closes[-253:] if len(closes) >= 253 else closes[-127:]
    drawdown = closes[-1] / max(trailing) - 1.0
    scores = {
        "momentum_6m": 50.0 + 50.0 * math.tanh(return_126 / 0.30),
        "momentum_12m": (
            50.0 + 50.0 * math.tanh(return_252 / 0.45)
            if return_252 is not None
            else None
        ),
        "drawdown_resilience": 100.0 * max(0.0, 1.0 + drawdown),
    }
    weights = {"momentum_6m": 0.45, "momentum_12m": 0.35, "drawdown_resilience": 0.20}
    available_weight = sum(
        weights[key] for key, value in scores.items() if value is not None
    )
    score = sum(
        float(value) * weights[key]
        for key, value in scores.items()
        if value is not None
    ) / available_weight
    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "coverage_status": "complete" if return_252 is not None else "partial",
        "return_126": return_126,
        "return_252": return_252,
        "drawdown": drawdown,
        "component_scores": {
            key: round(value, 1) if value is not None else None
            for key, value in scores.items()
        },
        "formula_weights": weights,
        "data_cutoff": bars[-1].available_at.isoformat(),
    }


def _confidence_snapshot(
    *,
    symbol: str,
    dimension: str,
    entity: str,
    frequency: str,
    period_start: str,
    score: float | None,
    coverage_status: str,
    evidence: list[dict[str, Any]],
    components: dict[str, Any],
    data_cutoff: str | None,
    provider: str,
    model: str,
    run_id: str,
) -> dict[str, Any]:
    identity = "|".join(
        [symbol.upper(), dimension, entity, frequency, period_start]
    )
    sources: dict[str, dict[str, str]] = {}
    for item in evidence:
        for source in item.get("sources", []):
            if source.get("url"):
                sources[source["url"]] = source
    return {
        "snapshot_key": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "symbol": symbol.upper(),
        "dimension": dimension,
        "entity": entity,
        "frequency": frequency,
        "period_start": period_start,
        "score": round(score, 1) if score is not None else None,
        "coverage_status": coverage_status,
        "evidence_count": len(evidence),
        "components": {
            **components,
            "evidence": [
                {
                    key: item.get(key)
                    for key in (
                        "institution",
                        "category",
                        "stance",
                        "statement",
                        "rationale",
                        "published_date",
                        "confidence",
                    )
                }
                for item in evidence
            ],
        },
        "sources": list(sources.values()),
        "data_cutoff": data_cutoff,
        "provider": provider,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "run_id": run_id,
    }
