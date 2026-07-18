from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Sequence

from .models import Bar, MetricDefinition, MetricSnapshot


METRIC_VERSION = "price-core-v0.1"

CATALOG = (
    MetricDefinition(
        name="return_5d",
        display_name="5-session return",
        display_name_zh="5 日報酬",
        description="Close-to-close total price return over five sessions.",
        description_zh="最近收盤價相對五個交易日前收盤價的總價格報酬。",
        formula="close_t / close_t-5 - 1",
        required_inputs=("close",),
        output_type="float",
        unit="decimal_return",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="return_20d",
        display_name="20-session return",
        display_name_zh="20 日報酬",
        description="Close-to-close price return over twenty sessions.",
        description_zh="最近收盤價相對二十個交易日前收盤價的價格報酬。",
        formula="close_t / close_t-20 - 1",
        required_inputs=("close",),
        output_type="float",
        unit="decimal_return",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="realized_volatility_20d",
        display_name="20-session realized volatility",
        display_name_zh="20 日年化已實現波動",
        description="Annualized standard deviation of twenty daily log returns.",
        description_zh="最近二十個每日對數報酬的標準差，再以 252 個交易日年化。",
        formula="std(log_return, 20) * sqrt(252)",
        required_inputs=("close",),
        output_type="float",
        unit="annualized_decimal",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="volume_zscore_20d",
        display_name="20-session volume z-score",
        display_name_zh="20 日成交量 z-score",
        description="Latest volume measured against the trailing twenty-session distribution.",
        description_zh="最新成交量相對過去二十個交易日成交量分布的標準化距離。",
        formula="(volume_t - mean(volume, 20)) / std(volume, 20)",
        required_inputs=("volume",),
        output_type="float",
        unit="standard_deviation",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="distance_ma20",
        display_name="Distance from MA20",
        display_name_zh="距 20 日均線",
        description="Distance between the latest close and the twenty-session moving average.",
        description_zh="最新收盤價相對過去二十個交易日移動平均的距離。",
        formula="close_t / mean(close, 20) - 1",
        required_inputs=("close",),
        output_type="float",
        unit="decimal_return",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="drawdown_60d",
        display_name="60-session drawdown",
        display_name_zh="60 日回撤",
        description="Latest close relative to the trailing sixty-session high.",
        description_zh="最新收盤價相對過去六十個交易日最高收盤價的跌幅。",
        formula="close_t / max(close, 60) - 1",
        required_inputs=("close",),
        output_type="float",
        unit="decimal_return",
        version=METRIC_VERSION,
    ),
)


@dataclass(frozen=True)
class _MetricContext:
    closes: list[float]
    volumes: list[float]
    log_returns: list[float]


def _return_metric(sessions: int) -> Callable[[_MetricContext], float]:
    return lambda context: _return(context.closes, sessions)


def _realized_volatility_20d(context: _MetricContext) -> float:
    return _safe_stdev(context.log_returns[-20:]) * math.sqrt(252)


def _volume_zscore_20d(context: _MetricContext) -> float:
    volume_20 = context.volumes[-20:]
    volume_std = _safe_stdev(volume_20)
    return (
        (context.volumes[-1] - statistics.mean(volume_20)) / volume_std
        if volume_std > 0
        else 0.0
    )


def _distance_ma20(context: _MetricContext) -> float:
    return context.closes[-1] / statistics.mean(context.closes[-20:]) - 1.0


def _drawdown_60d(context: _MetricContext) -> float:
    return context.closes[-1] / max(context.closes[-60:]) - 1.0


METRIC_CALCULATORS: dict[str, Callable[[_MetricContext], float]] = {
    "return_5d": _return_metric(5),
    "return_20d": _return_metric(20),
    "realized_volatility_20d": _realized_volatility_20d,
    "volume_zscore_20d": _volume_zscore_20d,
    "distance_ma20": _distance_ma20,
    "drawdown_60d": _drawdown_60d,
}


def _return(closes: Sequence[float], sessions: int) -> float:
    if len(closes) <= sessions:
        return 0.0
    return closes[-1] / closes[-sessions - 1] - 1.0


def _safe_stdev(values: Sequence[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def compute_price_metrics(
    bars: Sequence[Bar],
    cutoff: datetime,
) -> MetricSnapshot:
    if not bars:
        raise ValueError("At least one bar is required")

    eligible = [bar for bar in bars if bar.timestamp <= cutoff]
    if not eligible:
        raise ValueError("No bars are eligible at the requested cutoff")

    for bar in eligible:
        bar.assert_available(cutoff)

    eligible = sorted(eligible, key=lambda bar: bar.timestamp)
    closes = [bar.close for bar in eligible]
    volumes = [float(bar.volume) for bar in eligible]
    log_returns = [
        math.log(current / previous)
        for previous, current in zip(closes[:-1], closes[1:], strict=False)
        if previous > 0 and current > 0
    ]
    context = _MetricContext(
        closes=closes,
        volumes=volumes,
        log_returns=log_returns,
    )
    values = {
        definition.name: METRIC_CALCULATORS[definition.name](context)
        for definition in CATALOG
    }

    snapshot = MetricSnapshot(
        symbol=eligible[-1].symbol,
        observation_time=eligible[-1].timestamp,
        prediction_cutoff=cutoff,
        max_source_available_at=max(bar.available_at for bar in eligible),
        metric_version=METRIC_VERSION,
        values=values,
    )
    snapshot.assert_temporal_integrity()
    return snapshot
