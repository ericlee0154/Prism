from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from packages.prism_core.models import Bar


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "prism-test.duckdb")
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    with TestClient(main.app) as test_client:
        yield test_client


def test_empty_database_never_returns_default_market_data(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "empty"
    assert health.json()["data_cutoff"] is None

    scanner = client.get("/api/v1/scanner?horizon=30D")
    assert scanner.status_code == 200
    assert scanner.json()["items"] == []


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


def test_every_prediction_cutoff_precedes_its_creation(client: TestClient) -> None:
    response = client.get("/api/v1/predictions")
    assert response.status_code == 200
    for row in response.json()["items"]:
        assert datetime.fromisoformat(row["data_cutoff"]) <= datetime.fromisoformat(row["created_at"])
