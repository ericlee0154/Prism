import asyncio
from datetime import UTC, datetime, timedelta

from packages.prism_core.forecast_surface import (
    ForecastSurfaceJobManager,
    compute_forecast_surface,
    required_surface_sessions,
)
from packages.prism_core.models import Bar


def make_bars(count: int) -> list[Bar]:
    start = datetime(2024, 1, 2, 21, 0, tzinfo=UTC)
    return [
        Bar(
            symbol="AAPL",
            timestamp=start + timedelta(days=index),
            available_at=start + timedelta(days=index),
            open=100 + index * 0.2,
            high=102 + index * 0.2,
            low=99 + index * 0.2,
            close=101 + index * 0.2 + (index % 7) * 0.15,
            volume=1_000_000 + (index % 13) * 10_000,
            source="massive",
        )
        for index in range(count)
    ]


def test_surface_minimums_require_full_analogs_and_five_targets() -> None:
    assert required_surface_sessions(10) == 114
    assert required_surface_sessions(30) == 154
    assert required_surface_sessions(90) == 274


def test_surface_forecasts_each_target_from_horizon_earlier_data() -> None:
    bars = make_bars(120)
    progress: list[int] = []
    result = asyncio.run(
        compute_forecast_surface(
            bars,
            horizon_sessions=10,
            progress=progress.append,
        )
    )

    assert result["status"] == "complete"
    assert result["point_count"] == 11
    assert progress[-1] == 100
    first = result["points"][0]
    origin_index = next(
        index
        for index, bar in enumerate(bars)
        if bar.timestamp.date().isoformat() == first["origin_date"]
    )
    target_index = next(
        index
        for index, bar in enumerate(bars)
        if bar.timestamp.date().isoformat() == first["target_date"]
    )
    assert target_index - origin_index == 10
    assert first["sample_count"] == 30
    assert first["actual_price"] == bars[target_index].close


def test_surface_job_can_be_cancelled_before_stale_work_runs() -> None:
    async def scenario() -> None:
        manager = ForecastSurfaceJobManager()
        bars = make_bars(320)
        job = manager.submit(
            symbol="AAPL",
            start_date="2024-01-02",
            end_date="2024-11-17",
            horizon_sessions=30,
            bars=bars,
        )
        cancelled = manager.cancel(job["job_id"])
        assert cancelled["status"] == "cancelled"
        await asyncio.sleep(0)
        assert manager.get(job["job_id"])["status"] == "cancelled"
        await manager.shutdown()

    asyncio.run(scenario())
