"""M7: static API-key auth + error envelope."""

from fastapi.testclient import TestClient

from triage.main import create_app

API_KEY = {"X-API-Key": "dev-key"}  # matches the default settings value


def test_missing_key_is_401_with_envelope():
    client = TestClient(create_app())
    resp = client.post("/v1/conversations", json={"customer_id": "cust_4821"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "unauthorized"


def test_wrong_key_is_401():
    client = TestClient(create_app())
    resp = client.post(
        "/v1/conversations", json={"customer_id": "cust_4821"}, headers={"X-API-Key": "nope"}
    )
    assert resp.status_code == 401


def test_correct_key_is_accepted():
    client = TestClient(create_app())
    resp = client.post("/v1/conversations", json={"customer_id": "cust_4821"}, headers=API_KEY)
    assert resp.status_code == 201
    assert "conversation_id" in resp.json()
