from collections.abc import Iterable
from uuid import UUID

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import BackgroundJob


async def enqueue_bullets(
    session: AsyncSession,
    queue: ArqRedis,
    user_id: UUID,
    bullet_ids: Iterable[UUID],
) -> None:
    jobs = [
        (bullet_id, BackgroundJob(user_id=user_id, job_type="embedding", status="queued"))
        for bullet_id in dict.fromkeys(bullet_ids)
    ]
    if not jobs:
        return
    session.add_all([job for _, job in jobs])
    await session.commit()
    for _, job in jobs:
        await session.refresh(job)
    for bullet_id, job in jobs:
        try:
            queued = await queue.enqueue_job(
                "embed_bullet_task",
                str(bullet_id),
                str(job.id),
                str(user_id),
                _job_id=str(job.id),
            )
            if queued is None:
                raise RuntimeError("Job ID already exists")
        except Exception:
            job.status = "failed"
            job.error = "Unable to enqueue embedding — edit the bullet to retry"
    await session.commit()
