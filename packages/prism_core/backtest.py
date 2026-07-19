from __future__ import annotations

import hashlib
import math
import statistics
from dataclasses import dataclass
from datetime import UTC
from typing import Mapping, Sequence

from .metrics import METRIC_VERSION, compute_price_metrics
from .models import Bar
from .scoring import SCORE_VERSION, score_cross_section


BACKTEST_VERSION = "walk-forward-price-v0.2.1"
LABEL_VERSION = "next-open-spy-excess-v0.2.1"
UNIVERSE_VERSION = "stored-research-universe-v0.2"


@dataclass(frozen=True)
class Observation:
    symbol: str
    date: str
    alpha_score: float
    risk_score: float | None
    alpha_factors: Mapping[str, float | None]
    diagnostic_return: float
    executable_return: float
    benchmark_executable_return: float
    excess_return: float
    future_max_drawdown: float
    future_max_gain: float
    forward_realized_volatility: float | None


def _midranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        rank = (position + end - 1) / 2.0
        for ordered_position in range(position, end):
            ranks[order[ordered_position]] = rank
        position = end
    return ranks


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 3 or len(set(left)) < 2 or len(set(right)) < 2:
        return None
    left_ranks = _midranks(left)
    right_ranks = _midranks(right)
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


def _forward_realized_volatility(bars: Sequence[Bar]) -> float | None:
    if len(bars) < 3:
        return None
    returns = [
        math.log(current.close / previous.close)
        for previous, current in zip(bars[:-1], bars[1:], strict=True)
        if previous.close > 0 and current.close > 0
    ]
    return (
        statistics.stdev(returns) * math.sqrt(252)
        if len(returns) > 1
        else None
    )


def _future_close_max_drawdown(
    entry_open: float,
    bars: Sequence[Bar],
) -> float:
    """Maximum close-to-running-peak drawdown after a next-open entry."""
    running_peak = entry_open
    maximum_drawdown = 0.0
    for bar in bars:
        running_peak = max(running_peak, bar.close)
        if running_peak > 0:
            maximum_drawdown = min(
                maximum_drawdown,
                bar.close / running_peak - 1.0,
            )
    return maximum_drawdown


def _mean_or_none(values: Sequence[float]) -> float | None:
    return statistics.mean(values) if values else None


def _median_or_none(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def _universe_hash(symbols: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(sorted(symbols)).encode()).hexdigest()


def _factor_ablation(
    per_date: Mapping[str, Sequence[Observation]],
) -> list[dict]:
    factor_keys = sorted(
        {
            key
            for observations in per_date.values()
            for observation in observations
            for key in observation.alpha_factors
        }
    )
    result: list[dict] = []
    for omitted in factor_keys:
        daily_ics: list[float] = []
        observation_count = 0
        for observations in per_date.values():
            usable: list[tuple[float, float]] = []
            for observation in observations:
                kept = [
                    float(value)
                    for key, value in observation.alpha_factors.items()
                    if key != omitted and value is not None
                ]
                if not kept:
                    continue
                usable.append(
                    (
                        statistics.mean(kept),
                        observation.excess_return,
                    )
                )
            if len(usable) < 3:
                continue
            ic = _spearman(
                [item[0] for item in usable],
                [item[1] for item in usable],
            )
            if ic is not None:
                daily_ics.append(ic)
                observation_count += len(usable)
        result.append(
            {
                "omitted_factor": omitted,
                "mean_spearman_ic": _mean_or_none(daily_ics),
                "evaluation_dates": len(daily_ics),
                "observation_count": observation_count,
            }
        )
    return result


def _factor_correlations(
    per_date: Mapping[str, Sequence[Observation]],
) -> list[dict]:
    factor_keys = sorted(
        {
            key
            for observations in per_date.values()
            for observation in observations
            for key in observation.alpha_factors
        }
    )
    result: list[dict] = []
    for left_index, left in enumerate(factor_keys):
        for right in factor_keys[left_index + 1 :]:
            daily_correlations: list[float] = []
            for observations in per_date.values():
                usable = [
                    (
                        observation.alpha_factors.get(left),
                        observation.alpha_factors.get(right),
                    )
                    for observation in observations
                    if observation.alpha_factors.get(left) is not None
                    and observation.alpha_factors.get(right) is not None
                ]
                if len(usable) < 3:
                    continue
                correlation = _spearman(
                    [float(item[0]) for item in usable if item[0] is not None],
                    [float(item[1]) for item in usable if item[1] is not None],
                )
                if correlation is not None:
                    daily_correlations.append(correlation)
            result.append(
                {
                    "left_factor": left,
                    "right_factor": right,
                    "mean_spearman_correlation": _mean_or_none(
                        daily_correlations
                    ),
                    "evaluation_dates": len(daily_correlations),
                }
            )
    return result


def _label_contract(horizon_sessions: int) -> dict:
    return {
        "version": LABEL_VERSION,
        "horizon_sessions": horizon_sessions,
        "diagnostic": "close[t+h] / close[t] - 1",
        "executable": "close[t+h] / open[t+1] - 1",
        "primary": "executable_stock_return - executable_SPY_return",
        "risk": {
            "max_drawdown": (
                "min(close_i / running_max(open[t+1], close[t+1:i]) - 1)"
            ),
            "max_gain": "max(high[t+1:t+h] / open[t+1] - 1)",
            "forward_realized_volatility": (
                "stdev(log close returns t+1:t+h, ddof=1) * sqrt(252)"
            ),
        },
        "return_basis": "split-adjusted price return; dividends are not included",
    }


def walk_forward_backtest(
    histories: dict[str, list[Bar]],
    *,
    horizon_sessions: int,
    rebalance_every: int = 5,
    benchmark_symbol: str = "SPY",
) -> dict:
    if horizon_sessions not in {10, 30, 90}:
        raise ValueError("Horizon must be 10, 30, or 90 sessions")
    if rebalance_every < 1:
        raise ValueError("Rebalance interval must be positive")

    ordered_histories = {
        symbol: sorted(bars, key=lambda bar: bar.timestamp)
        for symbol, bars in histories.items()
        if bars
    }
    benchmark = ordered_histories.get(benchmark_symbol, [])
    requested_symbols = sorted(
        symbol for symbol in ordered_histories if symbol != benchmark_symbol
    )
    universe = {
        "definition_version": UNIVERSE_VERSION,
        "benchmark_symbols": [benchmark_symbol],
        "requested_symbols": requested_symbols,
        "requested_count": len(requested_symbols),
        "symbol_list_hash": _universe_hash(requested_symbols),
    }
    if len(benchmark) < 61 + horizon_sessions or len(requested_symbols) < 3:
        return {
            "status": "insufficient_data",
            "version": BACKTEST_VERSION,
            "metric_version": METRIC_VERSION,
            "score_version": SCORE_VERSION,
            "label_version": LABEL_VERSION,
            "horizon_sessions": horizon_sessions,
            "rebalance_every_sessions": rebalance_every,
            "symbol_count": len(requested_symbols),
            "observation_count": 0,
            "evaluation_dates": 0,
            "ic_evaluation_dates": 0,
            "candidate_evaluation_dates": 0,
            "mean_spearman_ic": None,
            "median_spearman_ic": None,
            "positive_ic_date_rate": None,
            "mean_top_bottom_spread": None,
            "direction_accuracy": None,
            "direction_baseline": None,
            "direction_accuracy_delta": None,
            "risk_forward_volatility_ic": None,
            "risk_drawdown_severity_ic": None,
            "universe": universe,
            "factor_ablation": [],
            "factor_correlations": [],
            "labels": _label_contract(horizon_sessions),
            "warnings": [
                "SPY plus at least three candidate symbols with sufficient history are required."
            ],
        }

    benchmark_by_date = {
        bar.timestamp.astimezone(UTC).date().isoformat(): bar for bar in benchmark
    }
    candidate_by_date = {
        symbol: {
            bar.timestamp.astimezone(UTC).date().isoformat(): bar
            for bar in bars
        }
        for symbol, bars in ordered_histories.items()
        if symbol != benchmark_symbol
    }
    benchmark_dates = [
        bar.timestamp.astimezone(UTC).date().isoformat() for bar in benchmark
    ]

    observations: list[Observation] = []
    per_date: dict[str, list[Observation]] = {}
    eligible_counts: list[int] = []
    excluded_reason_counts: dict[str, int] = {}
    candidate_evaluation_dates = 0

    first_index = 60
    final_index = len(benchmark_dates) - horizon_sessions
    for index in range(first_index, final_index, rebalance_every):
        candidate_evaluation_dates += 1
        evaluation_date = benchmark_dates[index]
        entry_date = benchmark_dates[index + 1]
        target_date = benchmark_dates[index + horizon_sessions]
        benchmark_current = benchmark_by_date[evaluation_date]
        benchmark_entry = benchmark_by_date[entry_date]
        benchmark_target = benchmark_by_date[target_date]
        forward_dates = benchmark_dates[
            index + 1 : index + horizon_sessions + 1
        ]
        if benchmark_current.available_at >= benchmark_entry.timestamp:
            excluded_reason_counts["benchmark_signal_late_for_next_session"] = (
                excluded_reason_counts.get(
                    "benchmark_signal_late_for_next_session",
                    0,
                )
                + 1
            )
            continue

        endpoint_candidates = [
            symbol
            for symbol in requested_symbols
            if evaluation_date in candidate_by_date[symbol]
            and entry_date in candidate_by_date[symbol]
            and target_date in candidate_by_date[symbol]
        ]
        complete_path_candidates = [
            symbol
            for symbol in endpoint_candidates
            if all(
                session in candidate_by_date[symbol]
                for session in forward_dates
            )
        ]
        missing_path_count = len(endpoint_candidates) - len(
            complete_path_candidates
        )
        if missing_path_count:
            excluded_reason_counts["incomplete_forward_path"] = (
                excluded_reason_counts.get("incomplete_forward_path", 0)
                + missing_path_count
            )
        date_candidates = [
            symbol
            for symbol in complete_path_candidates
            if candidate_by_date[symbol][evaluation_date].available_at
            < candidate_by_date[symbol][entry_date].timestamp
        ]
        late_count = len(complete_path_candidates) - len(date_candidates)
        if late_count:
            excluded_reason_counts["signal_late_for_next_session"] = (
                excluded_reason_counts.get("signal_late_for_next_session", 0)
                + late_count
            )
        if len(date_candidates) < 3:
            excluded_reason_counts["missing_aligned_label_sessions"] = (
                excluded_reason_counts.get("missing_aligned_label_sessions", 0) + 1
            )
            continue

        cutoff = max(
            [benchmark_current.available_at]
            + [
                candidate_by_date[symbol][evaluation_date].available_at
                for symbol in date_candidates
            ]
        )
        benchmark_prefix = [
            bar
            for bar in benchmark[: index + 1]
            if bar.available_at <= cutoff
        ]
        metrics_by_symbol: dict[str, Mapping[str, float | None]] = {}
        for symbol in date_candidates:
            prefix = [
                bar
                for bar in ordered_histories[symbol]
                if bar.timestamp <= candidate_by_date[symbol][evaluation_date].timestamp
                and bar.available_at <= cutoff
            ]
            if len(prefix) < 61:
                excluded_reason_counts["insufficient_metric_history"] = (
                    excluded_reason_counts.get("insufficient_metric_history", 0) + 1
                )
                continue
            snapshot = compute_price_metrics(
                prefix,
                cutoff,
                benchmark_bars=benchmark_prefix,
            )
            metrics_by_symbol[symbol] = snapshot.values

        scored = score_cross_section(metrics_by_symbol)
        horizon = f"{horizon_sessions}D"
        date_observations: list[Observation] = []
        for symbol in sorted(metrics_by_symbol):
            score = scored[symbol]["horizons"][horizon]
            alpha_score = score["alpha_score"]
            if alpha_score is None:
                continue
            current = candidate_by_date[symbol][evaluation_date]
            entry = candidate_by_date[symbol][entry_date]
            target = candidate_by_date[symbol][target_date]
            if current.close <= 0 or entry.open <= 0 or benchmark_entry.open <= 0:
                continue
            forward_path = [
                candidate_by_date[symbol][session]
                for session in forward_dates
            ]
            diagnostic_return = target.close / current.close - 1.0
            executable_return = target.close / entry.open - 1.0
            benchmark_executable = (
                benchmark_target.close / benchmark_entry.open - 1.0
            )
            observation = Observation(
                symbol=symbol,
                date=evaluation_date,
                alpha_score=float(alpha_score),
                risk_score=(
                    float(score["risk_score"])
                    if score["risk_score"] is not None
                    else None
                ),
                alpha_factors=score["alpha_factors"],
                diagnostic_return=diagnostic_return,
                executable_return=executable_return,
                benchmark_executable_return=benchmark_executable,
                excess_return=executable_return - benchmark_executable,
                future_max_drawdown=_future_close_max_drawdown(
                    entry.open,
                    forward_path,
                ),
                future_max_gain=max(
                    bar.high / entry.open - 1.0 for bar in forward_path
                ),
                forward_realized_volatility=_forward_realized_volatility(
                    forward_path
                ),
            )
            date_observations.append(observation)
        if len(date_observations) >= 3:
            per_date[evaluation_date] = date_observations
            eligible_counts.append(len(date_observations))
            observations.extend(date_observations)

    daily_ics: list[float] = []
    spreads: list[float] = []
    spread_bucket_sizes: list[int] = []
    risk_volatility_ics: list[float] = []
    risk_drawdown_ics: list[float] = []
    directional_hits = 0
    direction_count = 0
    positive_excess = 0
    for date_observations in per_date.values():
        alpha_scores = [item.alpha_score for item in date_observations]
        excess_returns = [item.excess_return for item in date_observations]
        ic = _spearman(alpha_scores, excess_returns)
        if ic is not None:
            daily_ics.append(ic)

        ordered = sorted(
            date_observations,
            key=lambda item: (item.alpha_score, item.symbol),
        )
        bucket = max(1, len(ordered) // 5)
        spreads.append(
            statistics.mean(item.excess_return for item in ordered[-bucket:])
            - statistics.mean(item.excess_return for item in ordered[:bucket])
        )
        spread_bucket_sizes.append(bucket)

        risk_usable = [
            item
            for item in date_observations
            if item.risk_score is not None
        ]
        risk_vol_usable = [
            item
            for item in risk_usable
            if item.forward_realized_volatility is not None
        ]
        if len(risk_vol_usable) >= 3:
            risk_vol_ic = _spearman(
                [float(item.risk_score) for item in risk_vol_usable],
                [
                    float(item.forward_realized_volatility)
                    for item in risk_vol_usable
                ],
            )
            if risk_vol_ic is not None:
                risk_volatility_ics.append(risk_vol_ic)
        if len(risk_usable) >= 3:
            risk_dd_ic = _spearman(
                [float(item.risk_score) for item in risk_usable],
                [-item.future_max_drawdown for item in risk_usable],
            )
            if risk_dd_ic is not None:
                risk_drawdown_ics.append(risk_dd_ic)

        for item in date_observations:
            predicted_positive = item.alpha_score >= 0
            realized_positive = item.excess_return >= 0
            directional_hits += int(predicted_positive == realized_positive)
            positive_excess += int(realized_positive)
            direction_count += 1

    direction_accuracy = (
        directional_hits / direction_count if direction_count else None
    )
    positive_rate = positive_excess / direction_count if direction_count else None
    direction_baseline = (
        max(positive_rate, 1.0 - positive_rate)
        if positive_rate is not None
        else None
    )
    complete = bool(daily_ics)
    warnings = [
        (
            "The primary label is next-session open to horizon close, minus the "
            "same-period SPY price return."
        ),
        (
            "Overlapping forward labels are not independent; observation count "
            "must not be interpreted as an independent sample size."
        ),
        (
            "Results exclude fees, slippage, taxes, borrow costs, dividends, and "
            "survivorship corrections."
        ),
        "This is a research diagnostic, not a recommendation or trading instruction.",
    ]
    return {
        "status": "complete" if complete else "insufficient_data",
        "version": BACKTEST_VERSION,
        "metric_version": METRIC_VERSION,
        "score_version": SCORE_VERSION,
        "label_version": LABEL_VERSION,
        "horizon_sessions": horizon_sessions,
        "rebalance_every_sessions": rebalance_every,
        "symbol_count": len(requested_symbols),
        "observation_count": len(observations),
        "evaluation_dates": len(per_date),
        "ic_evaluation_dates": len(daily_ics),
        "candidate_evaluation_dates": candidate_evaluation_dates,
        "mean_spearman_ic": _mean_or_none(daily_ics),
        "median_spearman_ic": _median_or_none(daily_ics),
        "positive_ic_date_rate": (
            sum(value > 0 for value in daily_ics) / len(daily_ics)
            if daily_ics
            else None
        ),
        "mean_top_bottom_spread": _mean_or_none(spreads),
        "mean_spread_bucket_size": _mean_or_none(spread_bucket_sizes),
        "direction_accuracy": direction_accuracy,
        "direction_baseline": direction_baseline,
        "direction_accuracy_delta": (
            direction_accuracy - direction_baseline
            if direction_accuracy is not None and direction_baseline is not None
            else None
        ),
        "risk_forward_volatility_ic": _mean_or_none(risk_volatility_ics),
        "risk_drawdown_severity_ic": _mean_or_none(risk_drawdown_ics),
        "mean_diagnostic_return": _mean_or_none(
            [item.diagnostic_return for item in observations]
        ),
        "mean_executable_return": _mean_or_none(
            [item.executable_return for item in observations]
        ),
        "mean_excess_return_vs_spy": _mean_or_none(
            [item.excess_return for item in observations]
        ),
        "mean_future_max_drawdown": _mean_or_none(
            [item.future_max_drawdown for item in observations]
        ),
        "mean_future_max_gain": _mean_or_none(
            [item.future_max_gain for item in observations]
        ),
        "factor_ablation": _factor_ablation(per_date),
        "factor_correlations": _factor_correlations(per_date),
        "labels": _label_contract(horizon_sessions),
        "universe": {
            **universe,
            "eligible_evaluation_dates": len(per_date),
            "coverage_ratio": (
                len(per_date) / candidate_evaluation_dates
                if candidate_evaluation_dates
                else 0.0
            ),
            "eligible_count_min": min(eligible_counts) if eligible_counts else 0,
            "eligible_count_median": (
                statistics.median(eligible_counts) if eligible_counts else 0
            ),
            "eligible_count_max": max(eligible_counts) if eligible_counts else 0,
            "excluded_reason_counts": excluded_reason_counts,
        },
        "warnings": warnings,
    }
