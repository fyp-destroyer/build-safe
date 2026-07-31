"""Chat transcript persistence: append_messages, list_messages.

The transcript is a record of what was said, not an input to anything. No
risk decision, follow-up gate or rule evaluation reads this table — losing
or corrupting it degrades the UI, never the safety pipeline. That separation
is deliberate: it means transcript writes can be best-effort on the client
without ever putting an assessment at risk.

Ordering is by explicit `position`, assigned server-side by continuing from
the highest position already stored for the job. Client-supplied ordering
would be wrong the moment two requests overlapped, and `created_at` alone
ties within a batch.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ChatMessage, Job
from schemas.chat import ChatMessageIn


async def append_messages(
    db: AsyncSession, job: Job, messages: list[ChatMessageIn]
) -> list[ChatMessage]:
    """Append `messages` to `job`'s transcript, preserving their order.

    Idempotency is NOT attempted here: the client appends only messages it
    has just produced, and a duplicate transcript row is a cosmetic problem,
    not a safety one. Adding a dedupe key would be complexity paid for
    nothing (and see the module docstring — nothing downstream reads this).
    """
    result = await db.execute(
        select(func.max(ChatMessage.position)).where(ChatMessage.job_id == job.id)
    )
    next_position = (result.scalar() or 0) + 1

    rows = [
        ChatMessage(
            user_id=job.user_id,
            job_id=job.id,
            role=message.role,
            kind=message.kind,
            text=message.text,
            position=next_position + offset,
        )
        for offset, message in enumerate(messages)
    ]
    db.add_all(rows)
    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows


async def list_messages(db: AsyncSession, job_id: UUID) -> list[ChatMessage]:
    """A job's transcript in conversation order.

    Callers must have already established ownership of `job_id` (via
    job_service.get_owned_job) — this function does not re-check it.
    """
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.job_id == job_id)
        .order_by(ChatMessage.position, ChatMessage.created_at)
    )
    return list(result.scalars().all())
