from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from packages.prism_core.models import Bar
from packages.prism_core.providers.massive import MassiveQuotaExceeded


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "prism-test.duckdb")
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PRISM_AI_PROVIDER", "disabled")
    with TestClient(main.app) as test_client:
        yield test_client


def test_empty_database_never_returns_default_market_data(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "empty"
    assert health.json()["data_cutoff"] is None
    assert health.json()["ai_provider_configured"] is False

    scanner = client.get("/api/v1/scanner?horizon=30D")
    assert scanner.status_code == 200
    assert scanner.json()["items"] == []

    catalog = client.get("/api/v1/metrics/catalog")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["items"]
    assert body["score_models"]
    assert all(item["display_name_zh"] for item in body["items"])
    scanner_model = next(
        item
        for item in body["score_models"]
        if item["id"] == "scanner_relative_score"
    )
    assert sum(term["weight"] for term in scanner_model["terms"]) == pytest.approx(1)


def test_missing_ai_key_never_returns_default_events(client: TestClient) -> None:
    events = client.get("/api/v1/events")
    assert events.status_code == 200
    assert events.json()["provider_configured"] is False
    assert events.json()["events"] == []

    refresh = client.post("/api/v1/events/world/refresh", json={})
    assert refresh.status_code == 503

    events_after_failure = client.get("/api/v1/events")
    assert events_after_failure.json()["events"] == []

    confidence = client.get("/api/v1/confidence")
    assert confidence.status_code == 200
    assert confidence.json()["snapshots"] == []
    confidence_refresh = client.post(
        "/api/v1/confidence/refresh",
        json={"symbol": "AAPL"},
    )
    assert confidence_refresh.status_code == 503


def test_duckdb_repository_serializes_concurrent_reads(client: TestClient) -> None:
    repository = client.app.state.repository

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: repository.market_summary(), range(40)))

    assert all(result["bar_count"] == 0 for result in results)


def test_sync_stops_remaining_symbols_after_quota(client: TestClient) -> None:
    class QuotaProvider:
        name = "massive"

        def __init__(self) -> None:
            self.calls: list[str] = []

        def bars(self, symbol, start, end):
            self.calls.append(symbol)
            if symbol == "TEAM":
                raise MassiveQuotaExceeded("quota reached; sync stopped")
            return []

    provider = QuotaProvider()
    client.app.state.service.provider = provider
    response = client.post(
        "/api/v1/sync",
        json={"symbols": ["GOOG", "TEAM", "VOO", "VTI"], "years": 2},
    )

    assert response.status_code == 200
    assert provider.calls == ["GOOG", "TEAM"]
    assert response.json()["not_attempted"] == ["VOO", "VTI"]


def test_seal_requires_real_stored_market_data(client: TestClient) -> None:
    response = client.post(
        "/api/v1/predictions/seal",
        json={"symbol": "NVDA", "horizon": "30D", "formula_version": "test-v1"},
    )
    assert response.status_code == 404
    assert "No stored market data" in response.json()["detail"]


def test_scanner_is_derived_from_stored_bars(client: TestClient) -> None:
    start = datetime(2025, 1, 2, 21, 5, tzinfo=UTC)
    bars = [
        Bar(
            symbol="REAL",
            timestamp=start + timedelta(days=index),
            available_at=start + timedelta(days=index),
            open=100 + index,
            high=102 + index,
            low=99 + index,
            close=101 + index,
            volume=1_000_000 + index * 1_000,
            source="massive",
        )
        for index in range(100)
    ]
    client.app.state.repository.upsert_bars(bars)
    response = client.get("/api/v1/scanner?horizon=30D")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["symbol"] == "REAL"
    assert items[0]["source"] == "massive"
    assert items[0]["price"] == 200

    analysis = client.post(
        "/api/v1/analyses",
        json={
            "symbol": "REAL",
            "start_date": "2025-01-02",
            "end_date": "2025-04-12",
        },
    )
    assert analysis.status_code == 201
    body = analysis.json()
    assert body["bar_count"] == 100
    assert body["metrics"]["return_20d"] > 0
    assert body["forecasts"]["10"]["status"] == "complete"
    assert body["forecasts"]["10"]["sample_count"] > 0

    backtest = client.post(
        "/api/v1/backtests",
        json={"horizon_sessions": 10},
    )
    assert backtest.status_code == 201
    surface = backtest.json()["volatility_surface"]
    assert surface["symbols"] == ["REAL"]
    assert surface["dates"]
    assert len(surface["values"]) == 1
    assert len(surface["values"][0]) == len(surface["dates"])


def test_forecast_actuals_are_the_only_out_of_range_analysis_data(
    client: TestClient,
) -> None:
    start = datetime(2025, 1, 2, 21, 5, tzinfo=UTC)
    bars = [
        Bar(
            symbol="HIST",
            timestamp=start + timedelta(days=index),
            available_at=start + timedelta(days=index),
            open=(100 + index if index < 120 else 9_900 + index),
            high=(102 + index if index < 120 else 9_902 + index),
            low=(99 + index if index < 120 else 9_899 + index),
            close=(101 + index if index < 120 else 9_901 + index),
            volume=1_000_000 + index * 1_000,
            source="massive",
        )
        for index in range(160)
    ]
    client.app.state.repository.upsert_bars(bars)
    selected_end = bars[119].timestamp.date().isoformat()
    response = client.post(
        "/api/v1/analyses",
        json={
            "symbol": "HIST",
            "start_date": bars[0].timestamp.date().isoformat(),
            "end_date": selected_end,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["bar_count"] == 120
    assert body["actual_end"] == selected_end
    assert body["series"][-1]["date"] == selected_end
    assert max(point["close"] for point in body["series"]) < 1_000
    assert datetime.fromisoformat(body["data_cutoff"]).date().isoformat() == selected_end

    forecast_10 = body["forecasts"]["10"]
    assert forecast_10["status"] == "complete"
    assert forecast_10["p50_return"] == forecast_10["median_return"]
    assert forecast_10["p50_price"] == pytest.approx(
        forecast_10["origin_price"] * (1 + forecast_10["p50_return"])
    )
    assert forecast_10["actual_status"] == "complete"
    assert forecast_10["actual_window_complete"] is True
    assert [item["session_offset"] for item in forecast_10["actual_window"]] == list(
        range(-5, 6)
    )
    assert all(
        item["date"] > selected_end for item in forecast_10["actual_window"]
    )

    assert body["forecasts"]["30"]["actual_status"] == "complete"
    assert body["forecasts"]["90"]["actual_status"] == "pending"


def test_analysis_never_fills_a_missing_range(client: TestClient) -> None:
    response = client.post(
        "/api/v1/analyses",
        json={
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",
        },
    )
    assert response.status_code == 400
    assert "No stored bars" in response.json()["detail"]


def test_every_prediction_cutoff_precedes_its_creation(client: TestClient) -> None:
    response = client.get("/api/v1/predictions")
    assert response.status_code == 200
    for row in response.json()["items"]:
        assert datetime.fromisoformat(row["data_cutoff"]) <= datetime.fromisoformat(row["created_at"])
