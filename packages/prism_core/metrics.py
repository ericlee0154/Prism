from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Sequence

from .models import Bar, MetricDefinition, MetricSnapshot


METRIC_VERSION = "price-core-v0.2"


def _definition(
    *,
    name: str,
    display_name: str,
    display_name_zh: str,
    description: str,
    description_zh: str,
    formula: str,
    required_inputs: tuple[str, ...],
    unit: str,
    minimum_observations: int,
    ddof: int | None = None,
    includes_current_session: bool = True,
    zero_denominator_policy: str = "null",
) -> MetricDefinition:
    return MetricDefinition(
        name=name,
        display_name=display_name,
        display_name_zh=display_name_zh,
        description=description,
        description_zh=description_zh,
        formula=formula,
        required_inputs=required_inputs,
        output_type="nullable_float",
        unit=unit,
        window_basis="TRADING_SESSIONS",
        price_basis="SPLIT_ADJUSTED_CLOSE",
        includes_current_session=includes_current_session,
        minimum_observations=minimum_observations,
        ddof=ddof,
        null_policy="null_if_insufficient_history_or_missing_benchmark",
        zero_denominator_policy=zero_denominator_policy,
        calculation_cutoff="bar.available_at <= prediction_cutoff",
        version=METRIC_VERSION,
    )


CATALOG = (
    _definition(
        name="return_5d",
        display_name="5-session return",
        display_name_zh="5 日報酬",
        description="Close-to-close price return over five trading sessions.",
        description_zh="最新收盤價相對五個交易日前收盤價的價格報酬。",
        formula="close_t / close_t-5 - 1",
        required_inputs=("close",),
        unit="decimal_return",
        minimum_observations=6,
    ),
    _definition(
        name="return_20d",
        display_name="20-session return",
        display_name_zh="20 日報酬",
        description="Close-to-close price return over twenty trading sessions.",
        description_zh="最新收盤價相對二十個交易日前收盤價的價格報酬。",
        formula="close_t / close_t-20 - 1",
        required_inputs=("close",),
        unit="decimal_return",
        minimum_observations=21,
    ),
    _definition(
        name="return_60d",
        display_name="60-session return",
        display_name_zh="60 日報酬",
        description="Close-to-close price return over sixty trading sessions.",
        description_zh="最新收盤價相對六十個交易日前收盤價的價格報酬。",
        formula="close_t / close_t-60 - 1",
        required_inputs=("close",),
        unit="decimal_return",
        minimum_observations=61,
    ),
    _definition(
        name="realized_volatility_20d",
        display_name="20-session realized volatility",
        display_name_zh="20 日年化已實現波動",
        description="Sample standard deviation of twenty daily log returns, annualized.",
        description_zh="二十個每日對數報酬的樣本標準差，以 252 個交易日年化。",
        formula="stdev(log_return_t-19:t, ddof=1) * sqrt(252)",
        required_inputs=("close",),
        unit="annualized_decimal",
        minimum_observations=21,
        ddof=1,
        zero_denominator_policy="zero",
    ),
    _definition(
        name="realized_volatility_60d",
        display_name="60-session realized volatility",
        display_name_zh="60 日年化已實現波動",
        description="Sample standard deviation of sixty daily log returns, annualized.",
        description_zh="六十個每日對數報酬的樣本標準差，以 252 個交易日年化。",
        formula="stdev(log_return_t-59:t, ddof=1) * sqrt(252)",
        required_inputs=("close",),
        unit="annualized_decimal",
        minimum_observations=61,
        ddof=1,
        zero_denominator_policy="zero",
    ),
    _definition(
        name="downside_semivolatility_20d",
        display_name="20-session downside semivolatility",
        display_name_zh="20 日下行半波動",
        description="Root mean square of negative daily log returns, annualized.",
        description_zh="負每日對數報酬的均方根，以 252 個交易日年化。",
        formula="sqrt(mean(min(log_return, 0)^2, 20)) * sqrt(252)",
        required_inputs=("close",),
        unit="annualized_decimal",
        minimum_observations=21,
        ddof=0,
        zero_denominator_policy="zero",
    ),
    _definition(
        name="downside_semivolatility_60d",
        display_name="60-session downside semivolatility",
        display_name_zh="60 日下行半波動",
        description="Root mean square of sixty negative daily log returns, annualized.",
        description_zh="六十個負每日對數報酬的均方根，以 252 個交易日年化。",
        formula="sqrt(mean(min(log_return, 0)^2, 60)) * sqrt(252)",
        required_inputs=("close",),
        unit="annualized_decimal",
        minimum_observations=61,
        ddof=0,
        zero_denominator_policy="zero",
    ),
    _definition(
        name="volatility_ratio_20d_60d",
        display_name="20D / 60D volatility ratio",
        display_name_zh="20D／60D 波動比",
        description="Recent realized volatility divided by medium-term volatility.",
        description_zh="20 日已實現波動除以 60 日已實現波動，用於辨認波動擴張或收縮。",
        formula="realized_volatility_20d / realized_volatility_60d",
        required_inputs=("close",),
        unit="ratio",
        minimum_observations=61,
    ),
    _definition(
        name="volume_zscore_20d",
        display_name="Inclusive 20-session volume z-score",
        display_name_zh="含當日 20 日成交量 z-score",
        description="Latest volume standardized by the inclusive trailing 20-session sample.",
        description_zh="最新成交量相對包含當日在內之 20 日樣本分布的標準化距離。",
        formula="(volume_t - mean(volume_t-19:t)) / stdev(volume_t-19:t, ddof=1)",
        required_inputs=("volume",),
        unit="standard_deviation",
        minimum_observations=20,
        ddof=1,
        zero_denominator_policy="null",
    ),
    _definition(
        name="volume_surprise_prev20d",
        display_name="Volume surprise vs previous 20 sessions",
        display_name_zh="相對前 20 日成交量驚奇",
        description="Latest volume standardized against the preceding twenty sessions.",
        description_zh="最新成交量相對不包含當日的前二十個交易日樣本分布。",
        formula="(volume_t - mean(volume_t-20:t-1)) / stdev(volume_t-20:t-1, ddof=1)",
        required_inputs=("volume",),
        unit="standard_deviation",
        minimum_observations=21,
        ddof=1,
        includes_current_session=False,
        zero_denominator_policy="null",
    ),
    _definition(
        name="up_down_volume_balance_20d",
        display_name="20-session up/down volume balance",
        display_name_zh="20 日漲跌成交量平衡",
        description="Up-day volume minus down-day volume, divided by total volume.",
        description_zh="上漲日成交量減下跌日成交量，再除以二十日總成交量。",
        formula="sum(sign(close_i-close_i-1) * volume_i, 20) / sum(volume_i, 20)",
        required_inputs=("close", "volume"),
        unit="bounded_ratio",
        minimum_observations=21,
        zero_denominator_policy="null",
    ),
    _definition(
        name="distance_ma20",
        display_name="Distance from MA20",
        display_name_zh="距 20 日均線",
        description="Latest close divided by the trailing twenty-session mean minus one.",
        description_zh="最新收盤價相對二十日移動平均的距離。",
        formula="close_t / mean(close_t-19:t) - 1",
        required_inputs=("close",),
        unit="decimal_return",
        minimum_observations=20,
    ),
    _definition(
        name="distance_ma50",
        display_name="Distance from MA50",
        display_name_zh="距 50 日均線",
        description="Latest close divided by the trailing fifty-session mean minus one.",
        description_zh="最新收盤價相對五十日移動平均的距離。",
        formula="close_t / mean(close_t-49:t) - 1",
        required_inputs=("close",),
        unit="decimal_return",
        minimum_observations=50,
    ),
    _definition(
        name="drawdown_60d",
        display_name="60-session drawdown",
        display_name_zh="60 日回撤",
        description="Latest close relative to the trailing sixty-session high.",
        description_zh="最新收盤價相對六十日最高收盤價的跌幅。",
        formula="close_t / max(close_t-59:t) - 1",
        required_inputs=("close",),
        unit="decimal_return",
        minimum_observations=60,
    ),
    _definition(
        name="trend_efficiency_20d",
        display_name="20-session trend efficiency",
        display_name_zh="20 日趨勢效率",
        description="Net price change divided by total absolute path length.",
        description_zh="二十日淨價格變化除以逐日絕對變動總和，衡量單向路徑與反覆震盪。",
        formula="(close_t-close_t-20) / sum(abs(close_i-close_i-1), 20)",
        required_inputs=("close",),
        unit="bounded_ratio",
        minimum_observations=21,
        zero_denominator_policy="zero",
    ),
    _definition(
        name="trend_efficiency_60d",
        display_name="60-session trend efficiency",
        display_name_zh="60 日趨勢效率",
        description="Sixty-session net price change divided by total absolute path length.",
        description_zh="六十日淨價格變化除以逐日絕對變動總和。",
        formula="(close_t-close_t-60) / sum(abs(close_i-close_i-1), 60)",
        required_inputs=("close",),
        unit="bounded_ratio",
        minimum_observations=61,
        zero_denominator_policy="zero",
    ),
    _definition(
        name="range_position_60d",
        display_name="Position in 60-session range",
        display_name_zh="60 日區間位置",
        description="Latest close mapped to the trailing 60-session low/high range.",
        description_zh="最新收盤價位於六十日最低與最高收盤價之間的相對位置。",
        formula="(close_t-min(close,60)) / (max(close,60)-min(close,60))",
        required_inputs=("close",),
        unit="zero_to_one",
        minimum_observations=60,
    ),
    _definition(
        name="median_dollar_volume_20d",
        display_name="Median dollar volume, 20 sessions",
        display_name_zh="20 日成交金額中位數",
        description="Median of split-adjusted close multiplied by daily volume.",
        description_zh="二十日每日調整後收盤價乘成交量之中位數；僅作流動性診斷。",
        formula="median(close_i * volume_i, 20)",
        required_inputs=("close", "volume"),
        unit="usd",
        minimum_observations=20,
        zero_denominator_policy="not_applicable",
    ),
    _definition(
        name="beta_60d",
        display_name="60-session beta vs SPY",
        display_name_zh="相對 SPY 的 60 日 Beta",
        description="Sample covariance with SPY log returns divided by SPY variance.",
        description_zh="六十個每日對數報酬與 SPY 的樣本共變異數，除以 SPY 樣本變異數。",
        formula="cov(log_return, spy_log_return, 60, ddof=1) / var(spy_log_return, 60, ddof=1)",
        required_inputs=("close", "SPY.close"),
        unit="beta",
        minimum_observations=61,
        ddof=1,
    ),
    _definition(
        name="beta_adjusted_return_20d",
        display_name="20-session beta-adjusted return",
        display_name_zh="20 日 Beta 調整報酬",
        description="Stock return minus beta times SPY return over twenty sessions.",
        description_zh="股票二十日報酬減去 60 日 Beta 乘 SPY 二十日報酬。",
        formula="return_20d - beta_60d * spy_return_20d",
        required_inputs=("close", "SPY.close"),
        unit="decimal_return",
        minimum_observations=61,
    ),
    _definition(
        name="beta_adjusted_return_60d",
        display_name="60-session beta-adjusted return",
        display_name_zh="60 日 Beta 調整報酬",
        description="Stock return minus beta times SPY return over sixty sessions.",
        description_zh="股票六十日報酬減去 60 日 Beta 乘 SPY 六十日報酬。",
        formula="return_60d - beta_60d * spy_return_60d",
        required_inputs=("close", "SPY.close"),
        unit="decimal_return",
        minimum_observations=61,
    ),
)


@dataclass(frozen=True)
class _MetricContext:
    closes: list[float]
    volumes: list[float]
    benchmark_closes: list[float | None]


MetricCalculator = Callable[[_MetricContext], float | None]


def _return(values: Sequence[float], sessions: int) -> float | None:
    if len(values) <= sessions or values[-sessions - 1] <= 0:
        return None
    return values[-1] / values[-sessions - 1] - 1.0


def _log_returns(values: Sequence[float], sessions: int) -> list[float] | None:
    if len(values) <= sessions:
        return None
    window = values[-sessions - 1 :]
    if any(value <= 0 for value in window):
        return None
    return [
        math.log(current / previous)
        for previous, current in zip(window[:-1], window[1:], strict=True)
    ]


def _realized_volatility(context: _MetricContext, sessions: int) -> float | None:
    returns = _log_returns(context.closes, sessions)
    if returns is None:
        return None
    return statistics.stdev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0


def _downside_semivolatility(
    context: _MetricContext,
    sessions: int,
) -> float | None:
    returns = _log_returns(context.closes, sessions)
    if returns is None:
        return None
    return math.sqrt(
        statistics.mean(min(value, 0.0) ** 2 for value in returns)
    ) * math.sqrt(252)


def _volume_zscore(context: _MetricContext, *, include_current: bool) -> float | None:
    required = 20 if include_current else 21
    if len(context.volumes) < required:
        return None
    baseline = (
        context.volumes[-20:]
        if include_current
        else context.volumes[-21:-1]
    )
    deviation = statistics.stdev(baseline)
    return (
        (context.volumes[-1] - statistics.mean(baseline)) / deviation
        if deviation > 0
        else None
    )


def _distance_ma(context: _MetricContext, sessions: int) -> float | None:
    if len(context.closes) < sessions:
        return None
    average = statistics.mean(context.closes[-sessions:])
    return context.closes[-1] / average - 1.0 if average > 0 else None


def _drawdown_60d(context: _MetricContext) -> float | None:
    if len(context.closes) < 60:
        return None
    high = max(context.closes[-60:])
    return context.closes[-1] / high - 1.0 if high > 0 else None


def _trend_efficiency(context: _MetricContext, sessions: int) -> float | None:
    if len(context.closes) <= sessions:
        return None
    window = context.closes[-sessions - 1 :]
    path = sum(
        abs(current - previous)
        for previous, current in zip(window[:-1], window[1:], strict=True)
    )
    return (window[-1] - window[0]) / path if path > 0 else 0.0


def _range_position_60d(context: _MetricContext) -> float | None:
    if len(context.closes) < 60:
        return None
    window = context.closes[-60:]
    low, high = min(window), max(window)
    return (window[-1] - low) / (high - low) if high > low else None


def _up_down_volume_balance_20d(context: _MetricContext) -> float | None:
    if len(context.closes) < 21 or len(context.volumes) < 21:
        return None
    closes = context.closes[-21:]
    volumes = context.volumes[-20:]
    total = sum(volumes)
    if total <= 0:
        return None
    signed = sum(
        (1.0 if current > previous else -1.0 if current < previous else 0.0)
        * volume
        for previous, current, volume in zip(
            closes[:-1],
            closes[1:],
            volumes,
            strict=True,
        )
    )
    return signed / total


def _median_dollar_volume_20d(context: _MetricContext) -> float | None:
    if len(context.closes) < 20 or len(context.volumes) < 20:
        return None
    return statistics.median(
        close * volume
        for close, volume in zip(
            context.closes[-20:],
            context.volumes[-20:],
            strict=True,
        )
    )


def _benchmark_window(
    context: _MetricContext,
    sessions: int,
) -> tuple[list[float], list[float]] | None:
    if len(context.closes) <= sessions or len(context.benchmark_closes) <= sessions:
        return None
    stock = context.closes[-sessions - 1 :]
    benchmark_optional = context.benchmark_closes[-sessions - 1 :]
    if any(value is None for value in benchmark_optional):
        return None
    benchmark = [float(value) for value in benchmark_optional if value is not None]
    if any(value <= 0 for value in stock) or any(value <= 0 for value in benchmark):
        return None
    return stock, benchmark


def _beta_60d(context: _MetricContext) -> float | None:
    window = _benchmark_window(context, 60)
    if window is None:
        return None
    stock, benchmark = window
    stock_returns = [
        math.log(current / previous)
        for previous, current in zip(stock[:-1], stock[1:], strict=True)
    ]
    benchmark_returns = [
        math.log(current / previous)
        for previous, current in zip(
            benchmark[:-1],
            benchmark[1:],
            strict=True,
        )
    ]
    benchmark_variance = statistics.variance(benchmark_returns)
    if benchmark_variance <= 0:
        return None
    return statistics.covariance(stock_returns, benchmark_returns) / benchmark_variance


def _beta_adjusted_return(
    context: _MetricContext,
    sessions: int,
) -> float | None:
    beta = _beta_60d(context)
    window = _benchmark_window(context, sessions)
    stock_return = _return(context.closes, sessions)
    if beta is None or window is None or stock_return is None:
        return None
    _, benchmark = window
    benchmark_return = benchmark[-1] / benchmark[0] - 1.0
    return stock_return - beta * benchmark_return


def _volatility_ratio(context: _MetricContext) -> float | None:
    recent = _realized_volatility(context, 20)
    medium = _realized_volatility(context, 60)
    if recent is None or medium is None or medium <= 0:
        return None
    return recent / medium


METRIC_CALCULATORS: dict[str, MetricCalculator] = {
    "return_5d": lambda context: _return(context.closes, 5),
    "return_20d": lambda context: _return(context.closes, 20),
    "return_60d": lambda context: _return(context.closes, 60),
    "realized_volatility_20d": lambda context: _realized_volatility(context, 20),
    "realized_volatility_60d": lambda context: _realized_volatility(context, 60),
    "downside_semivolatility_20d": lambda context: _downside_semivolatility(context, 20),
    "downside_semivolatility_60d": lambda context: _downside_semivolatility(context, 60),
    "volatility_ratio_20d_60d": _volatility_ratio,
    "volume_zscore_20d": lambda context: _volume_zscore(
        context,
        include_current=True,
    ),
    "volume_surprise_prev20d": lambda context: _volume_zscore(
        context,
        include_current=False,
    ),
    "up_down_volume_balance_20d": _up_down_volume_balance_20d,
    "distance_ma20": lambda context: _distance_ma(context, 20),
    "distance_ma50": lambda context: _distance_ma(context, 50),
    "drawdown_60d": _drawdown_60d,
    "trend_efficiency_20d": lambda context: _trend_efficiency(context, 20),
    "trend_efficiency_60d": lambda context: _trend_efficiency(context, 60),
    "range_position_60d": _range_position_60d,
    "median_dollar_volume_20d": _median_dollar_volume_20d,
    "beta_60d": _beta_60d,
    "beta_adjusted_return_20d": lambda context: _beta_adjusted_return(context, 20),
    "beta_adjusted_return_60d": lambda context: _beta_adjusted_return(context, 60),
}


def _validate_metric_registry() -> None:
    names = [definition.name for definition in CATALOG]
    duplicate_names = sorted(
        {name for name in names if names.count(name) > 1}
    )
    missing_calculators = sorted(set(names) - set(METRIC_CALCULATORS))
    unregistered_calculators = sorted(set(METRIC_CALCULATORS) - set(names))
    if duplicate_names or missing_calculators or unregistered_calculators:
        raise RuntimeError(
            "Invalid metric registry: "
            f"duplicates={duplicate_names}, "
            f"missing_calculators={missing_calculators}, "
            f"unregistered_calculators={unregistered_calculators}"
        )


_validate_metric_registry()


def compute_price_metrics(
    bars: Sequence[Bar],
    cutoff: datetime,
    *,
    benchmark_bars: Sequence[Bar] | None = None,
) -> MetricSnapshot:
    if not bars:
        raise ValueError("At least one bar is required")

    eligible = [bar for bar in bars if bar.timestamp <= cutoff]
    if not eligible:
        raise ValueError("No bars are eligible at the requested cutoff")
    for bar in eligible:
        bar.assert_available(cutoff)
    eligible = sorted(eligible, key=lambda bar: bar.timestamp)

    benchmark_by_date: dict[str, float] = {}
    used_benchmark_bars: list[Bar] = []
    for bar in benchmark_bars or ():
        if bar.timestamp <= cutoff and bar.available_at <= cutoff:
            benchmark_by_date[
                bar.timestamp.astimezone(UTC).date().isoformat()
            ] = bar.close
            used_benchmark_bars.append(bar)

    context = _MetricContext(
        closes=[bar.close for bar in eligible],
        volumes=[float(bar.volume) for bar in eligible],
        benchmark_closes=[
            benchmark_by_date.get(
                bar.timestamp.astimezone(UTC).date().isoformat()
            )
            for bar in eligible
        ],
    )
    values = {
        definition.name: METRIC_CALCULATORS[definition.name](context)
        for definition in CATALOG
    }

    snapshot = MetricSnapshot(
        symbol=eligible[-1].symbol,
        observation_time=eligible[-1].timestamp,
        prediction_cutoff=cutoff,
        max_source_available_at=max(
            bar.available_at for bar in [*eligible, *used_benchmark_bars]
        ),
        metric_version=METRIC_VERSION,
        values=values,
    )
    snapshot.assert_temporal_integrity()
    return snapshot
