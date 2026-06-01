"""M11: the voice endpoint transcribes an upload (fake transcriber key-less) and
feeds the text through the same pipeline."""

from fastapi.testclient import TestClient

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import Issue, Understanding
from triage.conversations.orchestration.graph import build_graph
from triage.conversations.repositories.seeded_customer_repository import SeededCustomerRepository
from triage.conversations.services.conversation_service import ConversationService
from triage.conversations.services.enrichment import make_enricher
from triage.main import create_app
from triage.providers.llm.fake import FakeLLMProvider
from triage.providers.transcription.fake import FakeTranscriber

API_KEY = {"X-API-Key": "dev-key"}
BILLING = Understanding(
    issues=[Issue(category=IssueCategory.billing_payments)],
    sentiment=Sentiment.frustrated,
    urgency=Urgency.high,
    business_impact=BusinessImpact.high,
)


def test_voice_endpoint_transcribes_then_routes():
    graph = build_graph(
        FakeLLMProvider(understanding=BILLING), make_enricher(SeededCustomerRepository())
    )
    app = create_app(ConversationService.in_memory(graph))
    app.state.transcriber = FakeTranscriber("billing reports are unavailable")
    client = TestClient(app)

    cid = client.post(
        "/v1/conversations", json={"customer_id": "cust_4821"}, headers=API_KEY
    ).json()["conversation_id"]

    resp = client.post(
        f"/v1/conversations/{cid}/voice",
        files={"audio": ("a.wav", b"RIFF0000WAVEfmt ", "audio/wav")},
        headers=API_KEY,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["decision"]["routing"]["primary_owner"] == "billing_ops"
