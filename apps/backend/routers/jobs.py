"""Jobs router — task submission and follow-up flow (architecture.md §4):
  1. POST /jobs                     — create a job from task submission
  2. PATCH /jobs/{id}/followup      — answer missing safety-critical follow-ups
  3. POST /jobs/{id}/assess         — trigger classifier + rule engine -> final_risk
  4. GET /jobs                      — list the caller's jobs, most recent first
  5. GET/POST /jobs/{id}/messages   — the chat transcript for a job, so a page
                                      refresh doesn't lose the conversation
  6. DELETE /jobs/{id}              — remove a job and its transcript/assessment

All ownership-scoped: a job not owned by the caller 404s (never leaks
existence). Missing safety-critical follow-up answers are never silently
skipped — see services/job_service.py.

`JobOut.next_followup` is computed at request time (not a DB column) via
`job_service.build_job_out` — see that function's docstring.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.security import get_current_user
from models import User
from schemas.chat import ChatMessagesAppendRequest, ChatMessagesOut
from schemas.job import AssessJobResponse, JobCreateRequest, JobFollowupRequest, JobOut
from services import chat_service, job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobOut:
    job = await job_service.create_job(db, current_user.id, payload)
    return await job_service.build_job_out(job)


@router.get("", response_model=list[JobOut])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobOut]:
    jobs = await job_service.list_jobs(db, current_user.id)
    return [await job_service.build_job_out(job) for job in jobs]


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete one of the caller's jobs and its transcript/assessment/logs.

    Same ownership rule as every other route here: someone else's job 404s.
    """
    job = await job_service.get_owned_job(db, job_id, current_user.id)
    await job_service.delete_job(db, job)


@router.patch("/{job_id}/followup", response_model=JobOut)
async def submit_followup(
    job_id: UUID,
    payload: JobFollowupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobOut:
    job = await job_service.get_owned_job(db, job_id, current_user.id)
    job = await job_service.submit_followup(db, job, payload)
    return await job_service.build_job_out(job)


@router.get("/{job_id}/messages", response_model=ChatMessagesOut)
async def list_messages(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessagesOut:
    # Ownership first: a transcript is user content, and 404-on-not-yours is
    # the same rule the rest of this router follows.
    await job_service.get_owned_job(db, job_id, current_user.id)
    return ChatMessagesOut(messages=await chat_service.list_messages(db, job_id))


@router.post("/{job_id}/messages", response_model=ChatMessagesOut, status_code=status.HTTP_201_CREATED)
async def append_messages(
    job_id: UUID,
    payload: ChatMessagesAppendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessagesOut:
    job = await job_service.get_owned_job(db, job_id, current_user.id)
    rows = await chat_service.append_messages(db, job, payload.messages)
    return ChatMessagesOut(messages=rows)


@router.post("/{job_id}/assess", response_model=AssessJobResponse)
async def assess_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessJobResponse:
    job = await job_service.get_owned_job(db, job_id, current_user.id)
    assessment = await job_service.assess_job(db, job)
    return AssessJobResponse(
        job_id=job.id, status=assessment.status, risk_level=assessment.risk_level
    )
