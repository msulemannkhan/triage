"""The turn job: acquire the per-conversation lock, run the graph via the
service (publishing node-by-node progress to the bus) while a heartbeat keeps the
lease alive, release. On failure it retries; after the last try it dead-letters.

The return value (a plain dict) is what arq stores as the job result and what
`GET /jobs/{id}` returns.
"""

import uuid

import structlog
from arq import Retry

from triage.conversations.orchestration.graph import to_packet
from triage.conversations.services.conversation_service import ConversationService
from triage.core.config import get_settings
from triage.core.logging import get_logger
from triage.core.pubsub import ProgressBus
from triage.worker.concurrency.lock import ConversationLock
from triage.worker.handlers.dlq import dead_letter

_log = get_logger("worker")


async def run_turn_job(ctx: dict, conversation_id: str, text: str) -> dict:
    service: ConversationService = ctx["service"]
    lock: ConversationLock = ctx["lock"]
    bus = ProgressBus(ctx["redis_client"])
    job_id = ctx.get("job_id", "")
    job_try = ctx.get("job_try", 1)
    max_tries = get_settings().worker_max_tries

    with structlog.contextvars.bound_contextvars(
        conversation_id=conversation_id, job_id=job_id, job_try=job_try
    ):
        token = uuid.uuid4().hex
        if not await lock.acquire(conversation_id, token):
            _log.info("turn_contended", reason="another turn in flight")
            raise Retry(defer=1.0)  # another turn in flight — back off and retry

        _log.info("turn_job_started")

        async def on_node(node: str) -> None:
            await bus.publish(conversation_id, {"node": node})

        try:
            async with lock.heartbeat(conversation_id, token):
                state = await service.submit(conversation_id, text, on_node=on_node)
        except Exception as exc:  # noqa: BLE001 — terminal handling below
            if job_try >= max_tries:
                _log.error(
                    "turn_dead_lettered",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    tries=job_try,
                )
                await dead_letter(ctx["redis_client"], conversation_id, str(exc))
                await bus.publish(conversation_id, {"event": "failed", "error": str(exc)})
                return {
                    "conversation_id": conversation_id,
                    "status": "dead_letter",
                    "error": str(exc),
                }
            _log.warning(
                "turn_retry",
                error=str(exc),
                error_type=type(exc).__name__,
                tries=job_try,
            )
            raise
        finally:
            await lock.release(conversation_id, token)

        await bus.publish(conversation_id, {"event": "completed", "status": state.status.value})
        packet = to_packet(state)
        _log.info("turn_job_completed", status=state.status.value, decided=packet is not None)
        return {
            "conversation_id": conversation_id,
            "status": state.status.value,
            "clarification": state.clarification,
            "decision": packet.model_dump(mode="json") if packet else None,
        }
