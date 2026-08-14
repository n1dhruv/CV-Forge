import asyncio
from io import BytesIO
from typing import Any
from uuid import UUID

from pypdf import PdfReader
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.resume import ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.services.latex import LatexItem, LatexProfile, render_resume
from app.services.latex_compiler import compile_latex


def latex_items_from_rows(
    rows: list[tuple[ResumeBulletSelection, SkillBankItem]],
    selected_skills: list[dict] | None = None,
    mandatory_education: SkillBankItem | None = None,
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
    items = list(grouped.values())
    items.extend(
        LatexItem(
            type="skill",
            title=str(snapshot["name"]),
            org=None,
            start_date=None,
            end_date=None,
            bullets=[],
            category=snapshot.get("category"),
        )
        for snapshot in sorted(
            selected_skills or [], key=lambda snapshot: snapshot["selection_order"]
        )
    )
    if mandatory_education is not None:
        items.append(
            LatexItem(
                type="education",
                title=mandatory_education.title,
                org=mandatory_education.org,
                start_date=mandatory_education.start_date,
                end_date=mandatory_education.end_date,
                bullets=[],
            )
        )
    return items


async def render_one_page_resume(
    rows: list[tuple[ResumeBulletSelection, SkillBankItem]],
    selected_skills: list[dict],
    mandatory_education: SkillBankItem | None,
    profile: LatexProfile | None,
    tectonic_binary_path: str,
    timeout_seconds: int,
) -> str:
    active_rows = list(rows)
    active_skills = list(selected_skills)
    optional_units = sorted(
        [
            *((selection.section_order, "bullet", selection.id) for selection, _ in rows),
            *(
                (int(skill["selection_order"]), "skill", str(skill["item_id"]))
                for skill in selected_skills
            ),
        ],
        reverse=True,
    )
    while True:
        latest_education = mandatory_education
        if latest_education is not None and any(
            item.id == latest_education.id for _, item in active_rows
        ):
            latest_education = None
        source = render_resume(
            latex_items_from_rows(active_rows, active_skills, latest_education), profile
        )
        pdf = await asyncio.to_thread(
            compile_latex, source, tectonic_binary_path, timeout_seconds, False
        )
        if len(PdfReader(BytesIO(pdf)).pages) == 1:
            return source
        if not optional_units:
            raise ValueError("Mandatory resume content does not fit on one page")
        _, kind, identifier = optional_units.pop(0)
        if kind == "bullet":
            active_rows = [row for row in active_rows if row[0].id != identifier]
        else:
            active_skills = [
                skill for skill in active_skills if str(skill["item_id"]) != identifier
            ]


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
            profile_row = await session.scalar(select(User).where(User.id == owner_id))
            education = await session.scalar(
                select(SkillBankItem)
                .where(SkillBankItem.user_id == owner_id, SkillBankItem.type == "education")
                .order_by(
                    SkillBankItem.end_date.desc().nullslast(),
                    SkillBankItem.start_date.desc().nullslast(),
                    SkillBankItem.created_at.desc(),
                )
            )
            profile = (
                LatexProfile(
                    full_name=profile_row.full_name,
                    contact_email=profile_row.contact_email or profile_row.email,
                    phone=profile_row.phone,
                    location=profile_row.location,
                    linkedin_url=profile_row.linkedin_url,
                    github_url=profile_row.github_url,
                    leetcode_url=profile_row.leetcode_url,
                    portfolio_url=profile_row.portfolio_url,
                )
                if profile_row is not None
                else None
            )
            selected_skills = [
                skill for skill in (version.selected_skills or []) if isinstance(skill, dict)
            ]
            version.tex_source = await render_one_page_resume(
                rows,
                selected_skills,
                education,
                profile,
                get_settings().tectonic_binary_path,
                get_settings().latex_compile_timeout_seconds,
            )
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
