from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.resume import ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.services.latex import LatexItem, render_resume


def latex_items_from_rows(
    rows: list[tuple[ResumeBulletSelection, SkillBankItem]],
) -> list[LatexItem]:
    grouped: dict[UUID, LatexItem] = {}
    for selection, item in rows:
        if not selection.resolved:
            raise ValueError("Every bullet must be resolved before assembly")
        if item.id not in grouped:
            grouped[item.id] = LatexItem(
                type=item.type,
                title=item.title,
                org=item.org,
                start_date=item.start_date,
                end_date=item.end_date,
                bullets=[],
            )
        grouped[item.id].bullets.append(
            selection.rewritten_text if selection.approved else selection.original_text
        )
    if not grouped:
        raise ValueError("The resume has no resolved bullets to assemble")
    return list(grouped.values())


async def assemble_resume_task(
    context: dict[str, Any], resume_version_id: str, background_job_id: str, user_id: str
) -> None:
    del context
    version_id, job_id, owner_id = map(UUID, (resume_version_id, background_job_id, user_id))
    async with async_session_factory() as session:
        version = await session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id,
                ResumeVersion.user_id == owner_id,
                ResumeVersion.status == "assembling",
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id,
                BackgroundJob.user_id == owner_id,
                BackgroundJob.status == "queued",
            )
        )
        if version is None or job is None:
            return
        job.status = "running"
        await session.commit()
        try:
            rows = list(
                (
                    await session.execute(
                        select(ResumeBulletSelection, SkillBankItem)
                        .join(
                            BulletPoint,
                            BulletPoint.id == ResumeBulletSelection.bullet_point_id,
                        )
                        .join(SkillBankItem, SkillBankItem.id == BulletPoint.item_id)
                        .where(
                            ResumeBulletSelection.resume_version_id == version_id,
                            SkillBankItem.user_id == owner_id,
                        )
                        .order_by(
                            ResumeBulletSelection.section_order,
                            ResumeBulletSelection.id,
                        )
                    )
                ).all()
            )
            version.tex_source = render_resume(latex_items_from_rows(rows))
            version.pdf_storage_path = None
            version.status = "assembled"
            job.status = "done"
            job.error = None
            job.result = {"resume_version_id": str(version_id), "status": "assembled"}
        except Exception:
            version.status = "finalized"
            job.status = "failed"
            job.error = "The resume could not be assembled safely"
        await session.commit()
