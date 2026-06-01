"""Job polling endpoint (queue execution mode). Returns the arq job's status and,
once complete, its result. All routes require the static API key."""

from fastapi import APIRouter, Depends, Request

from triage.core.dependencies import require_api_key
from triage.core.errors import NotFoundError

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])


@router.get("/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    submitter = request.app.state.submitter
    if submitter is None:
        raise NotFoundError("Job polling is only available in queue execution mode")
    status = await submitter.status(job_id)
    if status["job_status"] == "not_found":
        raise NotFoundError(f"Unknown job: {job_id}")
    return status
