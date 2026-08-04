from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import BackgroundJob
from app.models.resume import JDRequirement, JobDescription


async def create_submission(
    session: AsyncSession, user_id: UUID, raw_text: str | None, source_file_path: str | None
) -> tuple[JobDescription, BackgroundJob]:
    jd = JobDescription(
        user_id=user_id,
        raw_text=raw_text,
        source_file_url=source_file_path,
        status="queued",
    )
    job = BackgroundJob(user_id=user_id, job_type="jd_parse", status="queued")
    session.add_all([jd, job])
    await session.commit()
    await session.refresh(jd)
    await session.refresh(job)
    return jd, job


async def fail_submission_enqueue(
    session: AsyncSession, jd: JobDescription, job: BackgroundJob
) -> None:
    jd.status = "failed"
    job.status = "failed"
    job.error = "Unable to enqueue JD parsing — try again"
    await session.commit()


async def get_owned_jd(session: AsyncSession, user_id: UUID, jd_id: UUID) -> JobDescription | None:
    return await session.scalar(
        select(JobDescription).where(JobDescription.id == jd_id, JobDescription.user_id == user_id)
    )


async def get_requirements(session: AsyncSession, jd_id: UUID) -> list[JDRequirement]:
    return list(
        (
            await session.scalars(
                select(JDRequirement)
                .where(JDRequirement.jd_id == jd_id)
                .order_by(JDRequirement.skill)
            )
        ).all()
    )


async def list_owned_jds(session: AsyncSession, user_id: UUID) -> list[JobDescription]:
    return list(
        (
            await session.scalars(
                select(JobDescription)
                .where(JobDescription.user_id == user_id)
                .order_by(JobDescription.created_at.desc())
            )
        ).all()
    )
