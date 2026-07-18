from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

from .models import Bar


BACKTEST_VERSION = "walk-forward-price-v1.0"


@dataclass(frozen=True)
class Observation:
    symbol: str
    score: float
    forward_return: float


def _rank(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    for rank, index in enumerate(order):
        ranks[index] = float(rank)
    return ranks


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 3 or len(set(left)) < 2 or len(set(right)) < 2:
        return None
    left_ranks = _rank(left)
    right_ranks = _rank(right)
    left_mean = statistics.mean(left_ranks)
    right_mean = statistics.mean(right_ranks)
    numerator = sum(
        (a - left_mean) * (b - right_mean)
        for a, b in zip(left_ranks, right_ranks, strict=True)
    )
    denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left_ranks)
        * sum((value - right_mean) ** 2 for value in right_ranks)
    )
    return numerator / denominator if denominator else None


def _feature_score(bars: Sequence[Bar], index: int) -> float | None:
    if index < 60:
        return None
    closes = [bar.close for bar in bars]
    volumes = [float(bar.volume) for bar in bars]
    close = closes[index]
    return_20 = close / closes[index - 20] - 1.0
    return_60 = close / closes[index - 60] - 1.0
    trailing = closes[index - 19 : index + 1]
    distance_ma20 = close / statistics.mean(trailing) - 1.0
    volatility = _realized_volatility(bars, index)
    if volatility is None:
        return None
    volume_window = volumes[index - 19 : index + 1]
    volume_std = statistics.stdev(volume_window) if len(volume_window) > 1 else 0.0
    volume_z = (
        (volumes[index] - statistics.mean(volume_window)) / volume_std
        if volume_std
        else 0.0
    )
    return (
        0.30 * return_20
        + 0.25 * return_60
        + 0.20 * distance_ma20
        + 0.05 * max(-3.0, min(3.0, volume_z))
        - 0.10 * volatility
    )


def _realized_volatility(
    bars: Sequence[Bar],
    index: int,
    *,
    lookback_sessions: int = 20,
) -> float | None:
    if index < lookback_sessions:
        return None
    closes = [bar.close for bar in bars]
    daily_returns = [
        math.log(closes[position] / closes[position - 1])
        for position in range(index - lookback_sessions + 1, index + 1)
        if closes[position - 1] > 0 and closes[position] > 0
    ]
    return (
        statistics.stdev(daily_returns) * math.sqrt(252)
        if len(daily_returns) > 1
        else 0.0
    )


def walk_forward_backtest(
    histories: dict[str, list[Bar]],
    *,
    horizon_sessions: int,
    rebalance_every: int = 5,
) -> dict:
    if horizon_sessions not in {10, 30, 90}:
        raise ValueError("Horizon must be 10, 30, or 90 sessions")
    observations: list[Observation] = []
    per_date: dict[str, list[Observation]] = {}
    volatility_by_symbol: dict[str, dict[str, float]] = {}

    for symbol, bars in histories.items():
        ordered = sorted(bars, key=lambda bar: bar.timestamp)
        for index in range(60, len(ordered) - horizon_sessions, rebalance_every):
            score = _feature_score(ordered, index)
            if score is None:
                continue
            forward_return = (
                ordered[index + horizon_sessions].close / ordered[index].close - 1.0
            )
            observation = Observation(symbol, score, forward_return)
            observations.append(observation)
            date_key = ordered[index].timestamp.date().isoformat()
            per_date.setdefault(date_key, []).append(observation)
            volatility = _realized_volatility(ordered, index)
            if volatility is not None:
                volatility_by_symbol.setdefault(symbol, {})[date_key] = volatility

    daily_ics: list[float] = []
    spreads: list[float] = []
    directional_hits = 0
    direction_count = 0
    for date_observations in per_date.values():
        if len(date_observations) < 3:
            continue
        scores = [item.score for item in date_observations]
        returns = [item.forward_return for item in date_observations]
        ic = _spearman(scores, returns)
        if ic is not None:
            daily_ics.append(ic)
        ordered = sorted(date_observations, key=lambda item: item.score)
        bucket = max(1, len(ordered) // 5)
        spreads.append(
            statistics.mean(item.forward_return for item in ordered[-bucket:])
            - statistics.mean(item.forward_return for item in ordered[:bucket])
        )
        for item in date_observations:
            directional_hits += int((item.score >= 0) == (item.forward_return >= 0))
            direction_count += 1

    surface_dates = sorted(
        {
            date_key
            for values in volatility_by_symbol.values()
            for date_key in values
        }
    )[-80:]
    surface_symbols = sorted(volatility_by_symbol)
    volatility_surface = {
        "dates": surface_dates,
        "symbols": surface_symbols,
        "values": [
            [
                volatility_by_symbol[symbol].get(date_key)
                for date_key in surface_dates
            ]
            for symbol in surface_symbols
        ],
        "unit": "annualized_decimal",
        "lookback_sessions": 20,
    }

    return {
        "status": "complete" if observations else "insufficient_data",
        "version": BACKTEST_VERSION,
        "horizon_sessions": horizon_sessions,
        "rebalance_every_sessions": rebalance_every,
        "symbol_count": len(histories),
        "observation_count": len(observations),
        "evaluation_dates": len(per_date),
        "mean_spearman_ic": statistics.mean(daily_ics) if daily_ics else None,
        "mean_top_bottom_spread": statistics.mean(spreads) if spreads else None,
        "direction_accuracy": (
            directional_hits / direction_count if direction_count else None
        ),
        "volatility_surface": volatility_surface,
        "warnings": [
            "Results exclude fees, slippage, taxes, borrow costs, and survivorship corrections.",
            "This is a research diagnostic, not a recommendation or trading instruction.",
        ],
    }
