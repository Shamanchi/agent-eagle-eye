"""API-тесты без сети: TestClient."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.watch import get_watcher


@pytest.fixture()
def client() -> TestClient:
    get_watcher().clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_watcher().clear()


def test_health(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_rule_and_ingest_flow(client: TestClient) -> None:
    assert client.post("/api/v1/rules", json={"metric": "cpu", "op": "gt", "threshold": 90}).status_code == 200
    resp = client.post("/api/v1/metrics", json={"metric": "cpu", "value": 95})
    assert resp.status_code == 200
    assert len(resp.json()["alerts"]) == 1
    stats = client.get("/api/v1/metrics?name=cpu").json()
    assert stats["count"] == 1
    assert stats["max"] == 95


def test_unknown_metric_stats(client: TestClient) -> None:
    assert client.get("/api/v1/metrics?name=ghost").status_code == 404


def test_bad_op_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/rules", json={"metric": "cpu", "op": "ne", "threshold": 1}).status_code == 422


@pytest.mark.integration()
def test_digest_shape(client: TestClient) -> None:
    """Интеграционный по маркеру: дайджест, без сети."""
    client.post("/api/v1/rules", json={"metric": "cpu", "op": "gt", "threshold": 90})
    client.post("/api/v1/metrics", json={"metric": "cpu", "value": 95})
    resp = client.get("/api/v1/digest")
    assert resp.status_code == 200
    assert "Eagle-eye digest" in resp.json()["digest_md"]
