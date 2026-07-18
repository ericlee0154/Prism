from __future__ import annotations

import math
from datetime import UTC, date
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .repository import PrismRepository


REACTION_VERSION = "event-reaction-v0.1"


def compute_event_reaction(
    repository: PrismRepository,
    event: dict[str, Any],
) -> dict[str, Any]:
    symbol = str(event.get("symbol") or "").upper()
    event_date_value = event.get("event_date_start")
    if not symbol or not event_date_value:
        return {
            "status": "unavailable",
            "version": REACTION_VERSION,
            "reason": "A symbol and confirmed event date are required",
        }

    event_date = date.fromisoformat(str(event_date_value))
    bars = repository.list_bars(symbol)
    if len(bars) < 2:
        return {
            "status": "unavailable",
            "version": REACTION_VERSION,
            "reason": "Insufficient stored price history",
        }

    release_timing = event.get("release_timing") or "unknown"
    anchor_index = next(
        (
            index
            for index, bar in enumerate(bars)
            if (
                bar.timestamp.astimezone(UTC).date() > event_date
                if release_timing == "after_market"
                else bar.timestamp.astimezone(UTC).date() >= event_date
            )
        ),
        None,
    )
    if anchor_index is None or anchor_index == 0:
        return {
            "status": "pending",
            "version": REACTION_VERSION,
            "reason": "No post-event trading session is stored yet",
        }

    previous = bars[anchor_index - 1]
    anchor = bars[anchor_index]
    benchmark = {
        bar.timestamp.astimezone(UTC).date(): bar.close
        for bar in repository.list_bars("SPY")
    }
    returns: dict[str, Any] = {}
    for sessions in (1, 5, 20):
        target_index = anchor_index + sessions - 1
        key = f"{sessions}_session"
        if target_index >= len(bars):
            returns[key] = {
                "status": "pending",
                "symbol_return": None,
                "benchmark_return": None,
                "excess_return": None,
                "target_date": None,
            }
            continue
        target = bars[target_index]
        symbol_return = target.close / previous.close - 1.0
        benchmark_previous = benchmark.get(previous.timestamp.astimezone(UTC).date())
        benchmark_target = benchmark.get(target.timestamp.astimezone(UTC).date())
        benchmark_return = (
            benchmark_target / benchmark_previous - 1.0
            if benchmark_previous and benchmark_target
            else None
        )
        returns[key] = {
            "status": "complete",
            "symbol_return": symbol_return,
            "benchmark_return": benchmark_return,
            "excess_return": (
                symbol_return - benchmark_return
                if benchmark_return is not None
                else None
            ),
            "target_date": target.timestamp.astimezone(UTC).date().isoformat(),
        }

    prior_volumes = [bar.volume for bar in bars[max(0, anchor_index - 20) : anchor_index]]
    volume_zscore = None
    if len(prior_volumes) >= 2:
        average = sum(prior_volumes) / len(prior_volumes)
        variance = sum((value - average) ** 2 for value in prior_volumes) / len(
            prior_volumes
        )
        deviation = math.sqrt(variance)
        volume_zscore = (anchor.volume - average) / deviation if deviation else 0.0

    complete_horizons = sum(
        item["status"] == "complete" for item in returns.values()
    )
    return {
        "status": "complete" if complete_horizons == 3 else "partial",
        "version": REACTION_VERSION,
        "symbol": symbol,
        "benchmark": "SPY",
        "event_date": event_date.isoformat(),
        "release_timing": release_timing,
        "reaction_session": anchor.timestamp.astimezone(UTC).date().isoformat(),
        "prior_session": previous.timestamp.astimezone(UTC).date().isoformat(),
        "prior_close": previous.close,
        "reaction_close": anchor.close,
        "reaction_volume_zscore_20": volume_zscore,
        "returns": returns,
        "data_cutoff": bars[-1].available_at.isoformat(),
    }
