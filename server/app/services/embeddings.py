from collections.abc import Iterable
from uuid import UUID

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import BackgroundJob
from app.models.skill_bank import SkillBankItem


def item_text(item: SkillBankItem) -> str:
    return "\n".join(
        part
        for part in (
            item.title.strip(),
            f"Tags: {', '.join(item.tags)}" if item.tags else "",
            item.raw_text.strip() if item.raw_text else "",
        )
        if part
    )


async def _enqueue(
    session: AsyncSession,
    queue: ArqRedis,
    user_id: UUID,
    record_ids: Iterable[UUID],
    task_name: str,
) -> int:
    jobs = [
        (record_id, BackgroundJob(user_id=user_id, job_type="embedding", status="queued"))
        for record_id in dict.fromkeys(record_ids)
    ]
    if not jobs:
        return 0
    session.add_all([job for _, job in jobs])
    await session.commit()
    for _, job in jobs:
        await session.refresh(job)
    queued_count = 0
    for record_id, job in jobs:
        try:
            queued = await queue.enqueue_job(
                task_name,
                str(record_id),
                str(job.id),
                str(user_id),
                _job_id=str(job.id),
            )
            if queued is None:
                raise RuntimeError("Job ID already exists")
            queued_count += 1
        except Exception:
            job.status = "failed"
            job.error = "Unable to enqueue embedding — edit the source to retry"
    await session.commit()
    return queued_count


async def enqueue_bullets(
    session: AsyncSession,
    queue: ArqRedis,
    user_id: UUID,
    bullet_ids: Iterable[UUID],
) -> int:
    return await _enqueue(session, queue, user_id, bullet_ids, "embed_bullet_task")


async def enqueue_items(
    session: AsyncSession,
    queue: ArqRedis,
    user_id: UUID,
    item_ids: Iterable[UUID],
) -> int:
    return await _enqueue(session, queue, user_id, item_ids, "embed_item_task")
