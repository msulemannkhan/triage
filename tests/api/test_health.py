"""M7: health endpoint (no auth)."""

from fastapi.testclient import TestClient

from triage.main import create_app


def test_health_ok():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
