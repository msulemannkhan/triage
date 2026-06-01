"""Queue submitter — the API side of the async path: enqueue a turn (honoring
idempotency) and read a job's status/result for polling.
"""

import hashlib
import uuid

from arq import ArqRedis
from arq.jobs import Job

from triage.core.logging import get_logger
from triage.worker.concurrency.idempotency import IdempotencyStore

_log = get_logger("queue")


class QueueSubmitter:
    def __init__(self, arq: ArqRedis, idempotency: IdempotencyStore) -> None:
        self._arq = arq
        self._idem = idempotency

    async def enqueue(self, conversation_id: str, text: str, idempotency_key: str | None) -> str:
        key = idempotency_key or hashlib.sha256(
            f"{conversation_id}:{text}".encode()
        ).hexdigest()
        # The idempotency store returns the original job id on replay; arq's _job_id
        # dedup then prevents a duplicate enqueue for that id.
        job_id = await self._idem.register(key, uuid.uuid4().hex)
        await self._arq.enqueue_job("run_turn_job", conversation_id, text, _job_id=job_id)
        _log.info(
            "turn_enqueued",
            conversation_id=conversation_id,
            job_id=job_id,
            idempotency_key_provided=idempotency_key is not None,
        )
        return job_id

    async def status(self, job_id: str) -> dict:
        job = Job(job_id, self._arq)
        job_status = await job.status()
        info = await job.result_info()
        _log.debug("job_status_polled", job_id=job_id, job_status=job_status.value)
        return {
            "job_id": job_id,
            "job_status": job_status.value,
            "result": info.result if info else None,
        }
