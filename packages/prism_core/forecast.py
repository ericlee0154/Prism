from __future__ import annotations

import math
import statistics
from datetime import UTC
from typing import Sequence

from .models import Bar


FORECAST_VERSION = "historical-analog-v1.2"


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


def _percentile_rank(values: Sequence[float], value: float) -> float | None:
    if not values:
        return None
    below = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    return round(100.0 * (below + 0.5 * equal) / len(values), 1)


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
    origin = ordered[-1]
    p10_return = _quantile(returns, 0.1)
    p50_return = _quantile(returns, 0.5)
    p90_return = _quantile(returns, 0.9)
    return {
        "status": "complete",
        "version": FORECAST_VERSION,
        "horizon_sessions": horizon_sessions,
        "sample_count": len(returns),
        "origin_date": origin.timestamp.astimezone(UTC).date().isoformat(),
        "origin_price": origin.close,
        "median_return": p50_return,
        "p10_return": p10_return,
        "p50_return": p50_return,
        "p90_return": p90_return,
        "p10_price": (
            origin.close * (1.0 + p10_return)
            if p10_return is not None
            else None
        ),
        "p50_price": (
            origin.close * (1.0 + p50_return)
            if p50_return is not None
            else None
        ),
        "p90_price": (
            origin.close * (1.0 + p90_return)
            if p90_return is not None
            else None
        ),
        "positive_probability": sum(value > 0 for value in returns) / len(returns),
        "analog_dates": [item[2] for item in nearest[:10]],
        # Removed by attach_historical_actuals before the API response. Keeping
        # the exact distribution here lets realized validation use the same
        # analog sample without allowing future bars into forecast generation.
        "_analog_forward_returns": returns,
    }


def attach_historical_actuals(
    forecast: dict,
    *,
    future_bars: Sequence[Bar],
) -> dict:
    """Attach realized prices without exposing them to forecast generation."""
    horizon_sessions = int(forecast["horizon_sessions"])
    analog_returns = forecast.get("_analog_forward_returns", [])
    public_forecast = {
        key: value
        for key, value in forecast.items()
        if key != "_analog_forward_returns"
    }
    ordered = sorted(future_bars, key=lambda bar: bar.timestamp)
    target_index = horizon_sessions - 1
    if target_index < 0 or target_index >= len(ordered):
        return {
            **public_forecast,
            "actual_status": "pending",
            "actual_target": None,
            "actual_window": [],
            "actual_window_complete": False,
            "actual_data_cutoff": None,
        }

    target = ordered[target_index]
    origin_price = forecast.get("origin_price")
    actual_return = (
        target.close / float(origin_price) - 1.0
        if origin_price
        else None
    )
    window_start = max(0, target_index - 5)
    window_end = min(len(ordered), target_index + 6)
    actual_window = [
        {
            "session_offset": index - target_index,
            "date": bar.timestamp.astimezone(UTC).date().isoformat(),
            "close": bar.close,
        }
        for index, bar in enumerate(
            ordered[window_start:window_end],
            start=window_start,
        )
    ]
    return {
        **public_forecast,
        "actual_status": "complete",
        "actual_target": {
            "date": target.timestamp.astimezone(UTC).date().isoformat(),
            "close": target.close,
            "return": actual_return,
            "forecast_percentile": (
                _percentile_rank(analog_returns, actual_return)
                if actual_return is not None
                else None
            ),
        },
        "actual_window": actual_window,
        "actual_window_complete": (
            target_index >= 5 and target_index + 5 < len(ordered)
        ),
        "actual_data_cutoff": max(
            bar.available_at for bar in ordered[window_start:window_end]
        ).isoformat(),
    }
