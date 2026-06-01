"""M7: the conversation endpoints end-to-end (graph in-request, scripted LLM)."""

from fastapi.testclient import TestClient

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import Issue, Understanding
from triage.conversations.orchestration.graph import build_graph
from triage.conversations.repositories.seeded_customer_repository import (
    SeededCustomerRepository,
)
from triage.conversations.services.conversation_service import ConversationService
from triage.conversations.services.enrichment import make_enricher
from triage.main import create_app
from triage.providers.llm.fake import FakeLLMProvider

API_KEY = {"X-API-Key": "dev-key"}

BILLING = Understanding(
    issues=[Issue(category=IssueCategory.billing_payments)],
    sentiment=Sentiment.frustrated,
    urgency=Urgency.high,
    business_impact=BusinessImpact.high,
)
VAGUE = Understanding(
    issues=[Issue(category=IssueCategory.other)],
    sentiment=Sentiment.neutral,
    urgency=Urgency.normal,
    business_impact=BusinessImpact.none,
)


def _client(fake: FakeLLMProvider) -> TestClient:
    graph = build_graph(fake, make_enricher(SeededCustomerRepository()))
    return TestClient(create_app(ConversationService.in_memory(graph)))


def _create(client: TestClient, customer_id: str = "cust_4821") -> str:
    resp = client.post("/v1/conversations", json={"customer_id": customer_id}, headers=API_KEY)
    assert resp.status_code == 201
    return resp.json()["conversation_id"]


def test_message_resolves_and_returns_decision_packet():
    client = _client(FakeLLMProvider(understanding=BILLING))
    cid = _create(client)

    resp = client.post(
        f"/v1/conversations/{cid}/messages",
        json={"text": "billing reports are down"},
        headers=API_KEY,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["decision"] is not None
    assert body["decision"]["schema_version"] == "1.0"
    assert body["decision"]["routing"]["primary_owner"] == "billing_ops"
    # enterprise (cust_4821) + high urgency -> R2 fired
    assert "R2" in body["decision"]["routing"]["rules_fired"]


def test_get_conversation_reflects_status():
    client = _client(FakeLLMProvider(understanding=BILLING))
    cid = _create(client)
    client.post(f"/v1/conversations/{cid}/messages", json={"text": "x"}, headers=API_KEY)

    resp = client.get(f"/v1/conversations/{cid}", headers=API_KEY)
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_audit_endpoint_records_the_decision():
    client = _client(FakeLLMProvider(understanding=BILLING))
    cid = _create(client)
    client.post(f"/v1/conversations/{cid}/messages", json={"text": "x"}, headers=API_KEY)

    resp = client.get(f"/v1/conversations/{cid}/audit", headers=API_KEY)
    assert resp.status_code == 200
    log = resp.json()
    assert len(log) == 1
    assert log[0]["status"] == "resolved"
    assert log[0]["decision"]["primary_owner"] == "billing_ops"


def test_oversized_message_is_rejected_with_413():
    from triage.core.config import get_settings

    client = _client(FakeLLMProvider(understanding=BILLING))
    cid = _create(client)
    too_long = "x" * (get_settings().max_message_chars + 1)

    resp = client.post(
        f"/v1/conversations/{cid}/messages", json={"text": too_long}, headers=API_KEY
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"


def test_unknown_conversation_is_404_with_envelope():
    client = _client(FakeLLMProvider(understanding=BILLING))
    resp = client.post(
        "/v1/conversations/does-not-exist/messages", json={"text": "x"}, headers=API_KEY
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_multi_turn_over_http_clarifies_then_resolves():
    client = _client(FakeLLMProvider(understandings=[VAGUE, BILLING], clarification="Which area?"))
    cid = _create(client)

    first = client.post(
        f"/v1/conversations/{cid}/messages", json={"text": "it broke"}, headers=API_KEY
    ).json()
    assert first["status"] == "awaiting_customer"
    assert first["clarification"] == "Which area?"
    assert first["decision"] is None

    second = client.post(
        f"/v1/conversations/{cid}/messages",
        json={"text": "billing reports are down"},
        headers=API_KEY,
    ).json()
    assert second["status"] == "resolved"
    assert second["decision"] is not None
