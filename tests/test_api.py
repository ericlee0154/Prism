from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from apps.api import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "prism-test.duckdb")
    with TestClient(main.app) as test_client:
        yield test_client


def test_health_and_scanner(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "demo"

    scanner = client.get("/api/v1/scanner?horizon=30D")
    assert scanner.status_code == 200
    items = scanner.json()["items"]
    assert items[0]["active_score"] >= items[-1]["active_score"]
    assert all(item["provider"] == "demo-seed" for item in items)


def test_sealed_prediction_is_append_only_record(client: TestClient) -> None:
    response = client.post(
        "/api/v1/predictions/seal",
        json={"symbol": "NVDA", "horizon": "30D", "formula_version": "test-v1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["record_hash"]
    assert body["outcome"] == "Pending"


def test_every_prediction_cutoff_precedes_its_creation(client: TestClient) -> None:
    response = client.get("/api/v1/predictions")
    assert response.status_code == 200
    for row in response.json()["items"]:
        assert datetime.fromisoformat(row["data_cutoff"]) <= datetime.fromisoformat(row["created_at"])
