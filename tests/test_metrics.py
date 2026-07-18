from datetime import UTC, datetime

import pytest

from packages.prism_core.metrics import compute_price_metrics
from packages.prism_core.models import Bar
from packages.prism_core.providers.massive import (
    MassiveMarketDataProvider,
    MassiveQuotaExceeded,
)
import httpx


def make_bar(day: int, available_day: int | None = None) -> Bar:
    timestamp = datetime(2026, 1, day, 20, 0, tzinfo=UTC)
    available = datetime(2026, 1, available_day or day, 20, 0, tzinfo=UTC)
    return Bar(
        symbol="TEST",
        timestamp=timestamp,
        available_at=available,
        open=100 + day,
        high=102 + day,
        low=99 + day,
        close=101 + day,
        volume=1_000_000 + day * 100,
        source="test",
    )


def test_future_bar_is_excluded_from_snapshot() -> None:
    cutoff = datetime(2026, 1, 20, 20, 0, tzinfo=UTC)
    bars = [make_bar(day) for day in range(1, 22)]
    snapshot = compute_price_metrics(bars, cutoff)
    assert snapshot.observation_time == cutoff
    assert snapshot.max_source_available_at <= cutoff


def test_late_available_source_fails_temporal_integrity() -> None:
    cutoff = datetime(2026, 1, 20, 20, 0, tzinfo=UTC)
    bars = [make_bar(day) for day in range(1, 20)]
    bars.append(make_bar(20, available_day=21))
    with pytest.raises(ValueError, match="Temporal integrity violation"):
        compute_price_metrics(bars, cutoff)


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
