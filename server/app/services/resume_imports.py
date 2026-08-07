from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.jobs import BackgroundJob
from app.models.resume import ResumeImport
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.schemas.resume_import import ResumeImportCommit


class ResumeImportNotReadyError(Exception):
    pass


class ResumeImportAlreadyCommittedError(Exception):
    pass


async def create_submission(
    session: AsyncSession, user_id: UUID, source_file_path: str
) -> tuple[ResumeImport, BackgroundJob]:
    resume_import = ResumeImport(user_id=user_id, source_file_url=source_file_path, status="queued")
    job = BackgroundJob(user_id=user_id, job_type="resume_import", status="queued")
    session.add_all([resume_import, job])
    await session.commit()
    await session.refresh(resume_import)
    await session.refresh(job)
    return resume_import, job


async def fail_submission_enqueue(
    session: AsyncSession, resume_import: ResumeImport, job: BackgroundJob
) -> None:
    resume_import.status = "failed"
    job.status = "failed"
    job.error = "Unable to enqueue resume import — try again"
    await session.commit()


async def get_owned(
    session: AsyncSession, user_id: UUID, resume_import_id: UUID
) -> ResumeImport | None:
    return await session.scalar(
        select(ResumeImport).where(
            ResumeImport.id == resume_import_id, ResumeImport.user_id == user_id
        )
    )


async def list_owned(session: AsyncSession, user_id: UUID) -> list[ResumeImport]:
    return list(
        (
            await session.scalars(
                select(ResumeImport)
                .where(ResumeImport.user_id == user_id)
                .order_by(ResumeImport.created_at.desc())
            )
        ).all()
    )


async def commit_import(
    session: AsyncSession,
    user_id: UUID,
    resume_import_id: UUID,
    payload: ResumeImportCommit,
) -> list[SkillBankItem] | None:
    resume_import = await session.scalar(
        select(ResumeImport)
        .where(ResumeImport.id == resume_import_id, ResumeImport.user_id == user_id)
        .with_for_update()
    )
    if resume_import is None:
        return None
    if resume_import.status != "done":
        raise ResumeImportNotReadyError
    if resume_import.committed_at is not None:
        raise ResumeImportAlreadyCommittedError

    items = [
        SkillBankItem(
            id=uuid4(),
            user_id=user_id,
            type=item.type,
            title=item.title,
            org=item.org,
            start_date=item.start_date,
            end_date=item.end_date,
            source="resume_import",
            bullet_points=[
                BulletPoint(id=uuid4(), text=text, display_order=index)
                for index, text in enumerate(item.bullets)
            ],
        )
        for item in payload.items
    ] + [
        SkillBankItem(
            id=uuid4(),
            user_id=user_id,
            type="skill",
            title=skill,
            source="resume_import",
        )
        for skill in dict.fromkeys(payload.skills)
    ]
    session.add_all(items)
    resume_import.committed_at = datetime.now(timezone.utc)
    await session.commit()
    return list(
        (
            await session.scalars(
                select(SkillBankItem)
                .options(selectinload(SkillBankItem.bullet_points))
                .where(SkillBankItem.id.in_([item.id for item in items]))
            )
        ).all()
    )
