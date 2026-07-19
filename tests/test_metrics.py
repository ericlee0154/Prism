from __future__ import annotations

import math
import statistics
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from packages.prism_core.metrics import (
    CATALOG,
    METRIC_CALCULATORS,
    METRIC_VERSION,
    compute_price_metrics,
)
from packages.prism_core.models import Bar
from packages.prism_core.providers.massive import (
    MassiveMarketDataProvider,
    MassiveQuotaExceeded,
)


START = datetime(2025, 1, 2, 21, 0, tzinfo=UTC)


def make_bars(
    closes: list[float],
    *,
    volumes: list[int] | None = None,
    symbol: str = "TEST",
    start: datetime = START,
) -> list[Bar]:
    volumes = volumes or [1_000_000 + index for index in range(len(closes))]
    assert len(volumes) == len(closes)
    result: list[Bar] = []
    for index, (close, volume) in enumerate(zip(closes, volumes, strict=True)):
        timestamp = start + timedelta(days=index)
        previous = closes[index - 1] if index else close
        result.append(
            Bar(
                symbol=symbol,
                timestamp=timestamp,
                available_at=timestamp,
                open=previous,
                high=max(previous, close) * 1.01,
                low=min(previous, close) * 0.99,
                close=close,
                volume=volume,
                source="test",
            )
        )
    return result


def snapshot_values(
    closes: list[float],
    *,
    volumes: list[int] | None = None,
    benchmark_closes: list[float] | None = None,
) -> dict[str, float | None]:
    bars = make_bars(closes, volumes=volumes)
    benchmark = (
        make_bars(benchmark_closes, symbol="SPY")
        if benchmark_closes is not None
        else None
    )
    return compute_price_metrics(
        bars,
        bars[-1].available_at,
        benchmark_bars=benchmark,
    ).values


def test_catalog_and_calculator_registry_are_exactly_in_sync() -> None:
    names = [definition.name for definition in CATALOG]
    assert len(names) == len(set(names))
    assert set(names) == set(METRIC_CALCULATORS)
    assert "return_60d" in names


def test_catalog_carries_explicit_point_in_time_metadata() -> None:
    for definition in CATALOG:
        assert definition.version == METRIC_VERSION
        assert definition.output_type == "nullable_float"
        assert definition.window_basis == "TRADING_SESSIONS"
        assert definition.price_basis == "SPLIT_ADJUSTED_CLOSE"
        assert definition.minimum_observations > 0
        assert definition.null_policy == (
            "null_if_insufficient_history_or_missing_benchmark"
        )
        assert definition.calculation_cutoff == (
            "bar.available_at <= prediction_cutoff"
        )
        assert definition.required_inputs
        assert definition.formula
        assert definition.unit

    previous_volume = next(
        item for item in CATALOG if item.name == "volume_surprise_prev20d"
    )
    assert previous_volume.includes_current_session is False
    assert previous_volume.ddof == 1
    assert previous_volume.zero_denominator_policy == "null"


def test_insufficient_history_is_null_instead_of_a_default_value() -> None:
    values = snapshot_values([100.0, 101.0, 99.0, 102.0, 100.0])
    assert values
    assert all(value is None for value in values.values())


def test_return60_trend_efficiency_range_position_and_ma50_formulas() -> None:
    closes = [100.0 + index for index in range(61)]
    values = snapshot_values(closes)

    assert values["return_60d"] == pytest.approx(closes[-1] / closes[-61] - 1)
    assert values["trend_efficiency_20d"] == pytest.approx(1.0)
    assert values["trend_efficiency_60d"] == pytest.approx(1.0)
    assert values["range_position_60d"] == pytest.approx(1.0)
    assert values["distance_ma50"] == pytest.approx(
        closes[-1] / statistics.mean(closes[-50:]) - 1
    )

    choppy = [100.0 + (index % 2) for index in range(21)]
    assert snapshot_values(choppy)["trend_efficiency_20d"] == pytest.approx(0.0)


def test_volume_surprise_uses_previous20_not_the_inclusive_window() -> None:
    closes = [100.0 + index for index in range(21)]
    volumes = list(range(1, 21)) + [100]
    values = snapshot_values(closes, volumes=volumes)

    previous = volumes[-21:-1]
    inclusive = volumes[-20:]
    assert values["volume_surprise_prev20d"] == pytest.approx(
        (volumes[-1] - statistics.mean(previous)) / statistics.stdev(previous)
    )
    assert values["volume_zscore_20d"] == pytest.approx(
        (volumes[-1] - statistics.mean(inclusive)) / statistics.stdev(inclusive)
    )
    assert values["volume_surprise_prev20d"] != values["volume_zscore_20d"]


def test_volume_surprise_is_null_when_reference_variance_is_zero() -> None:
    values = snapshot_values([100.0] * 21, volumes=[1_000] * 21)
    assert values["volume_surprise_prev20d"] is None
    assert values["volume_zscore_20d"] is None


def test_up_down_volume_balance_weights_each_session_by_its_volume() -> None:
    signs = [1 if index % 2 == 0 else -1 for index in range(20)]
    closes = [100.0]
    for sign in signs:
        closes.append(closes[-1] + sign)
    signed_volumes = list(range(10, 30))
    values = snapshot_values(closes, volumes=[999, *signed_volumes])

    expected = sum(
        sign * volume
        for sign, volume in zip(signs, signed_volumes, strict=True)
    ) / sum(signed_volumes)
    assert values["up_down_volume_balance_20d"] == pytest.approx(expected)


def test_downside_semivolatility_only_penalizes_negative_log_returns() -> None:
    log_returns = [0.01, -0.02, 0.03, -0.04] * 5
    closes = [100.0]
    for value in log_returns:
        closes.append(closes[-1] * math.exp(value))

    expected = math.sqrt(
        statistics.mean(min(value, 0.0) ** 2 for value in log_returns)
    ) * math.sqrt(252)
    values = snapshot_values(closes)
    assert values["downside_semivolatility_20d"] == pytest.approx(expected)


def test_volatility_ratio_compares_recent20_with_full60() -> None:
    log_returns = (
        [-0.004, 0.002, 0.005, -0.001] * 10
        + [-0.03, 0.02, 0.04, -0.025] * 5
    )
    closes = [100.0]
    for value in log_returns:
        closes.append(closes[-1] * math.exp(value))

    expected = statistics.stdev(log_returns[-20:]) / statistics.stdev(log_returns)
    values = snapshot_values(closes)
    assert values["volatility_ratio_20d_60d"] == pytest.approx(expected)


def test_beta_and_beta_adjusted_returns_use_date_aligned_spy() -> None:
    benchmark_log_returns = [
        0.003 + ((index % 7) - 3) * 0.001 for index in range(60)
    ]
    benchmark = [100.0]
    stock = [80.0]
    for value in benchmark_log_returns:
        benchmark.append(benchmark[-1] * math.exp(value))
        stock.append(stock[-1] * math.exp(2.0 * value))

    values = snapshot_values(stock, benchmark_closes=benchmark)
    assert values["beta_60d"] == pytest.approx(2.0)
    for sessions in (20, 60):
        stock_return = stock[-1] / stock[-sessions - 1] - 1.0
        benchmark_return = benchmark[-1] / benchmark[-sessions - 1] - 1.0
        assert values[f"beta_adjusted_return_{sessions}d"] == pytest.approx(
            stock_return - 2.0 * benchmark_return
        )

    shifted_benchmark = make_bars(
        benchmark,
        symbol="SPY",
        start=START + timedelta(days=1),
    )
    stock_bars = make_bars(stock)
    shifted = compute_price_metrics(
        stock_bars,
        stock_bars[-1].available_at,
        benchmark_bars=shifted_benchmark,
    ).values
    assert shifted["beta_60d"] is None
    assert shifted["beta_adjusted_return_20d"] is None
    assert shifted["beta_adjusted_return_60d"] is None


def test_future_bar_is_excluded_from_snapshot() -> None:
    bars = make_bars([100.0 + index for index in range(22)])
    cutoff = bars[-2].timestamp
    snapshot = compute_price_metrics(bars, cutoff)
    assert snapshot.observation_time == cutoff
    assert snapshot.max_source_available_at <= cutoff


def test_late_available_source_fails_temporal_integrity() -> None:
    bars = make_bars([100.0 + index for index in range(20)])
    late = bars[-1]
    bars[-1] = Bar(
        **{
            **late.__dict__,
            "available_at": late.available_at + timedelta(days=1),
        }
    )
    with pytest.raises(ValueError, match="Temporal integrity violation"):
        compute_price_metrics(bars, late.timestamp)


def test_massive_adapter_maps_daily_aggregates_without_leaking_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/AAPL/range/1/day/2026-01-01/2026-01-31")
        assert request.url.params["apiKey"] == "test-secret"
        return httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {
                        "t": 1767330000000,
                        "o": 100.0,
                        "h": 103.0,
                        "l": 99.0,
                        "c": 102.0,
                        "v": 1_250_000,
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = MassiveMarketDataProvider(api_key="test-secret", client=client)
    bars = provider.bars(
        "AAPL",
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 31, 23, 59, tzinfo=UTC),
    )
    client.close()

    assert len(bars) == 1
    assert bars[0].symbol == "AAPL"
    assert bars[0].close == 102.0
    assert bars[0].available_at.hour == 21


def test_massive_adapter_stops_immediately_on_quota() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(429, headers={"Retry-After": "60"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = MassiveMarketDataProvider(api_key="test-secret", client=client)

    with pytest.raises(MassiveQuotaExceeded, match="sync stopped"):
        provider.bars(
            "GOOG",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, tzinfo=UTC),
        )

    client.close()
    assert request_count == 1
