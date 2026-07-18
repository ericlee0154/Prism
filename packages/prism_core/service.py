from __future__ import annotations

import math
import os
from datetime import UTC, datetime, timedelta
from typing import Literal

from .backtest import BACKTEST_VERSION, walk_forward_backtest
from .metrics import CATALOG, METRIC_VERSION, compute_price_metrics
from .providers.massive import MassiveMarketDataProvider
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

    @property
    def provider_name(self) -> str | None:
        return self.provider.name if self.provider else None

    @property
    def provider_configured(self) -> bool:
        return self.provider is not None

    def sync_market_data(self, symbols: list[str], years: int) -> dict:
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

        end = datetime.now(UTC)
        start = end - timedelta(days=366 * years)
        sync_id = self.repository.begin_sync(self.provider.name, cleaned)
        rows_written = 0
        failures: list[dict[str, str]] = []
        for symbol in cleaned:
            try:
                bars = self.provider.bars(symbol, start, end)
                rows_written += self.repository.upsert_bars(bars)
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
        return {
            "sync_id": sync_id,
            "status": status,
            "provider": self.provider.name,
            "symbols": cleaned,
            "rows_written": rows_written,
            "failures": failures,
            "market": summary,
        }

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
                    "first_observation": bars[0].timestamp.isoformat(),
                    "last_observation": latest.timestamp.isoformat(),
                    "data_cutoff": cutoff.isoformat(),
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
            "metric_version": METRIC_VERSION,
        }
