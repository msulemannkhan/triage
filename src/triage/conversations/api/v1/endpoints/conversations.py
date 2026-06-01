"""Conversation endpoints.

`POST .../messages` is async when `TRIAGE_EXECUTION=queue` (enqueue -> 202 +
job_id, poll via `GET /v1/jobs/{id}`); otherwise it runs the graph in-request and
returns the decision directly. All routes require the static API key.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from triage.conversations.api.v1.schemas import (
    ConversationResponse,
    CreateConversationRequest,
    CreateConversationResponse,
    MessageRequest,
    MessageResponse,
)
from triage.conversations.dependencies import get_service
from triage.conversations.models.enums import ConversationStatus
from triage.conversations.models.schemas import AuditEntry
from triage.conversations.orchestration.graph import to_packet
from triage.conversations.services.conversation_service import ConversationService
from triage.core.config import get_settings
from triage.core.dependencies import require_api_key
from triage.core.errors import NotFoundError, PayloadTooLargeError

ServiceDep = Annotated[ConversationService, Depends(get_service)]

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", status_code=201)
async def create_conversation(
    body: CreateConversationRequest, service: ServiceDep
) -> CreateConversationResponse:
    conversation_id = await service.create(body.customer_id)
    return CreateConversationResponse(
        conversation_id=conversation_id, status=ConversationStatus.active
    )


async def _handle_turn(
    request: Request,
    service: ConversationService,
    conversation_id: str,
    text: str,
    idempotency_key: str | None,
) -> MessageResponse | JSONResponse:
    """Queue mode → enqueue (202 + job_id); inline mode → run the graph now (200)."""
    settings = get_settings()
    if len(text) > settings.max_message_chars:
        raise PayloadTooLargeError(
            f"Message exceeds the {settings.max_message_chars}-character limit"
        )
    submitter = request.app.state.submitter
    if settings.execution == "queue" and submitter is not None:
        job_id = await submitter.enqueue(conversation_id, text, idempotency_key)
        return JSONResponse(
            status_code=202,
            content={"conversation_id": conversation_id, "job_id": job_id, "status": "queued"},
        )
    state = await service.submit(conversation_id, text)
    return MessageResponse(
        conversation_id=conversation_id,
        status=state.status,
        clarification=state.clarification,
        decision=to_packet(state),
    )


@router.post("/{conversation_id}/messages", response_model=None)
async def post_message(
    conversation_id: str,
    body: MessageRequest,
    service: ServiceDep,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MessageResponse | JSONResponse:
    return await _handle_turn(request, service, conversation_id, body.text, idempotency_key)


@router.post("/{conversation_id}/voice", response_model=None)
async def post_voice(
    conversation_id: str,
    service: ServiceDep,
    request: Request,
    audio: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MessageResponse | JSONResponse:
    """Voice input: transcribe the upload (Deepgram, or the fake transcriber
    key-less), then feed the text through the identical pipeline."""
    max_bytes = get_settings().max_voice_bytes
    # Read one byte past the cap so we can reject oversized uploads without
    # buffering an unbounded payload into the transcription provider.
    payload = await audio.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise PayloadTooLargeError(f"Audio exceeds the {max_bytes}-byte limit")
    text = await request.app.state.transcriber.transcribe(payload)
    return await _handle_turn(request, service, conversation_id, text, idempotency_key)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str, service: ServiceDep
) -> ConversationResponse:
    state = await service.get(conversation_id)
    return ConversationResponse(
        conversation_id=conversation_id,
        status=state.status,
        clarification=state.clarification,
        decision=to_packet(state),
    )


@router.get("/{conversation_id}/audit")
async def get_audit(conversation_id: str, service: ServiceDep) -> list[AuditEntry]:
    return await service.audit_log(conversation_id)


@router.get("/{conversation_id}/stream")
async def stream_progress(conversation_id: str, request: Request) -> EventSourceResponse:
    """Server-Sent Events: relays node-by-node progress for a turn (queue mode).
    Subscribe before submitting; poll `GET /v1/jobs/{id}` for the authoritative result."""
    bus = request.app.state.progress_bus
    if bus is None:
        raise NotFoundError("Progress streaming is only available in queue execution mode")

    async def events():
        async for event in bus.subscribe(conversation_id):
            yield {"data": json.dumps(event)}
            if event.get("event") in ("completed", "failed"):
                break

    return EventSourceResponse(events(), ping=15)
