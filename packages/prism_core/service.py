from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from .metrics import CATALOG, compute_price_metrics
from .providers.demo import DemoMarketDataProvider
from .repository import PrismRepository
from .seed import DEMO_CUTOFF, DEMO_STOCKS


class FormulaWeights(BaseModel):
    momentum: float = Field(default=0.30, ge=-1, le=1)
    relative_strength: float = Field(default=0.25, ge=-1, le=1)
    trend_quality: float = Field(default=0.20, ge=-1, le=1)
    volume_confirmation: float = Field(default=0.15, ge=-1, le=1)
    volatility: float = Field(default=-0.10, ge=-1, le=1)


class PrismService:
    def __init__(self, repository: PrismRepository) -> None:
        self.repository = repository
        self.provider = DemoMarketDataProvider()
        self.data_cutoff = DEMO_CUTOFF

    @property
    def provider_name(self) -> str:
        return self.provider.name

    @property
    def is_demo(self) -> bool:
        return self.provider.is_demo

    def ensure_demo_data(self, force: bool = False) -> None:
        self.repository.seed_ledger(force=force)

    def overview(self) -> dict:
        ledger = self.repository.list_predictions()
        matured = [item for item in ledger if item["outcome"] != "Pending"]
        correct = [item for item in matured if item["outcome"] == "Correct"]
        return {
            "mode": "demo",
            "market_regime": {
                "label": "Selective risk-on",
                "confidence": 0.68,
            },
            "candidate_coverage": {
                "passing": 24,
                "universe": 100,
            },
            "direction_hit_rate_30d": 0.578,
            "ledger": {
                "matured": len(matured),
                "correct": len(correct),
                "pending": len(ledger) - len(matured),
            },
            "data_cutoff": self.data_cutoff.isoformat(),
        }

    def scan(self, horizon: str, search: str = "") -> list[dict]:
        score_key = {
            "10D": "score_10d",
            "30D": "score_30d",
            "90D": "score_90d",
        }[horizon]
        needle = search.lower().strip()
        items = []
        for symbol, stock in DEMO_STOCKS.items():
            searchable = f"{symbol} {stock['name']} {stock['sector']}".lower()
            if needle and needle not in searchable:
                continue
            items.append(
                {
                    "symbol": symbol,
                    **stock,
                    "active_score": stock[score_key],
                    "horizon": horizon,
                    "data_cutoff": self.data_cutoff.isoformat(),
                    "provider": self.provider_name,
                }
            )
        return sorted(items, key=lambda item: item["active_score"], reverse=True)

    def stock_detail(self, symbol: str) -> dict | None:
        stock = DEMO_STOCKS.get(symbol)
        if stock is None:
            return None
        start = self.data_cutoff - timedelta(days=180)
        bars = self.provider.bars(symbol, start, self.data_cutoff)
        snapshot = compute_price_metrics(bars, self.data_cutoff)
        return {
            "symbol": symbol,
            **stock,
            "metrics": snapshot.values,
            "metric_version": snapshot.metric_version,
            "max_source_available_at": snapshot.max_source_available_at.isoformat(),
            "prediction_cutoff": snapshot.prediction_cutoff.isoformat(),
            "temporal_integrity": "passed",
            "provider": self.provider_name,
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

    def evaluate_formula(
        self,
        horizon: str,
        weights: FormulaWeights,
        formula_version: str,
    ) -> dict:
        weight_map = weights.model_dump()
        quality = (
            weights.momentum * 0.20
            + weights.relative_strength * 0.25
            + weights.trend_quality * 0.14
            + weights.volume_confirmation * 0.08
            - abs(weights.volatility) * 0.05
        )
        direction_accuracy = min(0.648, max(0.491, 0.543 + quality / 28))
        spread = min(0.059, 0.017 + quality / 42)
        information_coefficient = min(0.14, 0.027 + quality / 15)
        result = {
            "status": "complete",
            "scope": "demo-validation",
            "holdout_status": "locked",
            "horizon": horizon,
            "formula_version": formula_version,
            "metrics": {
                "direction_accuracy": direction_accuracy,
                "always_up_baseline": 0.537,
                "top_bottom_relative_spread": spread,
                "spearman_ic": information_coefficient,
                "max_drawdown": -0.081,
                "turnover": 0.22,
            },
            "decile_relative_returns": [
                -0.018,
                -0.012,
                -0.008,
                -0.003,
                0.001,
                0.004,
                0.008,
                0.012,
                0.017,
                0.025,
            ],
            "warnings": [
                "Illustrative demo data is not evidence of a tradeable edge.",
                "The final time holdout remains locked.",
            ],
        }
        experiment_id = self.repository.append_experiment(
            formula_version=formula_version,
            horizon=horizon,
            weights=weight_map,
            result=result,
        )
        return {"experiment_id": experiment_id, **result}

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
        stock = DEMO_STOCKS[symbol]
        score = stock[f"score_{horizon.lower()}"]
        direction = "Bullish" if score >= 60 else "Bearish" if score < 45 else "Neutral"
        expected_range = {
            "Bullish": "+0.8% to +5.0%",
            "Neutral": "-2.0% to +2.0%",
            "Bearish": "-5.0% to +0.8%",
        }[direction]
        detail = self.stock_detail(symbol)
        created_at = datetime.now(UTC)
        return self.repository.append_prediction(
            {
                "created_at": created_at.isoformat(),
                "data_cutoff": self.data_cutoff.isoformat(),
                "symbol": symbol,
                "horizon": horizon,
                "direction": direction,
                "confidence": stock["confidence"],
                "expected_range": expected_range,
                "actual_outcome": "Pending",
                "outcome": "Pending",
                "formula_version": formula_version,
                "metric_version": detail["metric_version"],
                "input_snapshot": {
                    "metrics": detail["metrics"],
                    "max_source_available_at": detail["max_source_available_at"],
                    "prediction_cutoff": detail["prediction_cutoff"],
                    "provider": self.provider_name,
                },
            }
        )

    def pipeline_status(self) -> dict:
        return {
            "status": "healthy",
            "mode": "demo",
            "data_cutoff": self.data_cutoff.isoformat(),
            "steps": [
                {"name": "raw_ingest", "status": "ready", "version": "demo-v0.1"},
                {"name": "temporal_audit", "status": "ready", "version": "v0.1"},
                {"name": "metrics", "status": "ready", "version": "price-core-v0.1"},
                {"name": "labels", "status": "isolated", "version": "v0.1"},
                {"name": "formula", "status": "candidate", "version": "core-v0.1"},
                {"name": "ledger", "status": "append-only", "version": "v0.1"},
            ],
            "guarantees": {
                "source_availability_checked": True,
                "same_close_execution_forbidden": True,
                "predictions_append_only": True,
                "holdout_locked": True,
            },
        }
