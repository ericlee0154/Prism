from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Sequence

from .models import Bar, MetricDefinition, MetricSnapshot


METRIC_VERSION = "price-core-v0.1"

CATALOG = (
    MetricDefinition(
        name="return_5d",
        description="Close-to-close total price return over five sessions.",
        formula="close_t / close_t-5 - 1",
        required_inputs=("close",),
        output_type="float",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="return_20d",
        description="Close-to-close price return over twenty sessions.",
        formula="close_t / close_t-20 - 1",
        required_inputs=("close",),
        output_type="float",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="realized_volatility_20d",
        description="Annualized standard deviation of twenty daily log returns.",
        formula="std(log_return, 20) * sqrt(252)",
        required_inputs=("close",),
        output_type="float",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="volume_zscore_20d",
        description="Latest volume measured against the trailing twenty-session distribution.",
        formula="(volume_t - mean(volume, 20)) / std(volume, 20)",
        required_inputs=("volume",),
        output_type="float",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="distance_ma20",
        description="Distance between the latest close and the twenty-session moving average.",
        formula="close_t / mean(close, 20) - 1",
        required_inputs=("close",),
        output_type="float",
        version=METRIC_VERSION,
    ),
    MetricDefinition(
        name="drawdown_60d",
        description="Latest close relative to the trailing sixty-session high.",
        formula="close_t / max(close, 60) - 1",
        required_inputs=("close",),
        output_type="float",
        version=METRIC_VERSION,
    ),
)


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
    close_20 = closes[-20:]
    volume_20 = volumes[-20:]
    returns_20 = log_returns[-20:]
    volume_std = _safe_stdev(volume_20)

    values = {
        "return_5d": _return(closes, 5),
        "return_20d": _return(closes, 20),
        "realized_volatility_20d": _safe_stdev(returns_20) * math.sqrt(252),
        "volume_zscore_20d": (
            (volumes[-1] - statistics.mean(volume_20)) / volume_std
            if volume_std > 0
            else 0.0
        ),
        "distance_ma20": closes[-1] / statistics.mean(close_20) - 1.0,
        "drawdown_60d": closes[-1] / max(closes[-60:]) - 1.0,
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
