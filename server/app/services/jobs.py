from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import BackgroundJob


async def get_owned_job(session: AsyncSession, user_id: UUID, job_id: UUID) -> BackgroundJob | None:
    return await session.scalar(
        select(BackgroundJob).where(BackgroundJob.id == job_id, BackgroundJob.user_id == user_id)
    )
