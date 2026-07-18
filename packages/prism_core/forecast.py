from __future__ import annotations

import math
import statistics
from datetime import UTC
from typing import Sequence

from .models import Bar


FORECAST_VERSION = "historical-analog-v1.0"


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _features(bars: Sequence[Bar], index: int) -> tuple[float, ...] | None:
    if index < 60:
        return None
    closes = [bar.close for bar in bars]
    volumes = [float(bar.volume) for bar in bars]
    close = closes[index]
    returns = [
        math.log(closes[position] / closes[position - 1])
        for position in range(index - 19, index + 1)
        if closes[position - 1] > 0 and closes[position] > 0
    ]
    volume_window = volumes[index - 19 : index + 1]
    volume_std = statistics.stdev(volume_window) if len(volume_window) > 1 else 0.0
    return (
        close / closes[index - 5] - 1.0,
        close / closes[index - 20] - 1.0,
        statistics.stdev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0,
        close / statistics.mean(closes[index - 19 : index + 1]) - 1.0,
        close / max(closes[index - 59 : index + 1]) - 1.0,
        (
            (volumes[index] - statistics.mean(volume_window)) / volume_std
            if volume_std
            else 0.0
        ),
    )


def historical_analog_forecast(
    bars: Sequence[Bar],
    *,
    horizon_sessions: int,
    analog_count: int = 30,
) -> dict:
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    current = _features(ordered, len(ordered) - 1) if ordered else None
    if current is None:
        return {
            "status": "insufficient_data",
            "version": FORECAST_VERSION,
            "horizon_sessions": horizon_sessions,
            "sample_count": 0,
        }

    candidates: list[tuple[tuple[float, ...], float, str]] = []
    for index in range(60, len(ordered) - horizon_sessions):
        features = _features(ordered, index)
        if features is None:
            continue
        forward_return = (
            ordered[index + horizon_sessions].close / ordered[index].close - 1.0
        )
        candidates.append(
            (
                features,
                forward_return,
                ordered[index].timestamp.astimezone(UTC).date().isoformat(),
            )
        )
    if len(candidates) < 10:
        return {
            "status": "insufficient_data",
            "version": FORECAST_VERSION,
            "horizon_sessions": horizon_sessions,
            "sample_count": len(candidates),
        }

    feature_columns = list(zip(*(item[0] for item in candidates), strict=True))
    means = [statistics.mean(column) for column in feature_columns]
    deviations = [
        statistics.stdev(column) if len(set(column)) > 1 else 1.0
        for column in feature_columns
    ]

    def distance(candidate: tuple[float, ...]) -> float:
        return math.sqrt(
            sum(
                ((candidate[index] - current[index]) / deviations[index]) ** 2
                for index in range(len(current))
            )
        )

    nearest = sorted(candidates, key=lambda item: distance(item[0]))[
        : min(analog_count, len(candidates))
    ]
    returns = [item[1] for item in nearest]
    return {
        "status": "complete",
        "version": FORECAST_VERSION,
        "horizon_sessions": horizon_sessions,
        "sample_count": len(returns),
        "median_return": _quantile(returns, 0.5),
        "p10_return": _quantile(returns, 0.1),
        "p90_return": _quantile(returns, 0.9),
        "positive_probability": sum(value > 0 for value in returns) / len(returns),
        "analog_dates": [item[2] for item in nearest[:10]],
    }
