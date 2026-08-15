from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.resume import (
    JDActionVerb,
    JDRequirement,
    JobDescription,
    ResumeBulletSelection,
    ResumeVersion,
)
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.services import llm_client, rewriter


async def _fail(version_id: UUID, job_id: UUID, user_id: UUID, message: str) -> None:
    async with async_session_factory() as session:
        version = await session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id, ResumeVersion.user_id == user_id
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id, BackgroundJob.user_id == user_id
            )
        )
        if version is None or job is None:
            return
        version.status = "draft"
        job.status = "failed"
        job.error = message
        await session.commit()


async def rewrite_bullets_task(
    context: dict[str, Any],
    resume_version_id: str,
    background_job_id: str,
    user_id: str,
    bullet_point_ids: list[str],
) -> None:
    del context
    version_id, job_id, owner_id = map(UUID, (resume_version_id, background_job_id, user_id))
    bullet_ids = [UUID(value) for value in bullet_point_ids]

    async with async_session_factory() as session:
        version = await session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id,
                ResumeVersion.user_id == owner_id,
                ResumeVersion.status == "rewriting",
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id,
                BackgroundJob.user_id == owner_id,
                BackgroundJob.status == "queued",
            )
        )
        if version is None or version.jd_id is None or job is None:
            return
        description = await session.scalar(
            select(JobDescription).where(JobDescription.id == version.jd_id)
        )
        parsed_json = description.parsed_json if description and description.parsed_json else {}
        ats_keywords = list(parsed_json.get("ats_keywords") or [])
        bullets = list(
            (
                await session.scalars(
                    select(BulletPoint)
                    .join(SkillBankItem, SkillBankItem.id == BulletPoint.item_id)
                    .where(BulletPoint.id.in_(bullet_ids), SkillBankItem.user_id == owner_id)
                )
            ).all()
        )
        if {bullet.id for bullet in bullets} != set(bullet_ids):
            await _fail(version_id, job_id, owner_id, "A selected bullet is no longer available")
            return
        requirement_rows = (
            await session.execute(
                select(
                    JDRequirement.skill,
                    JDRequirement.importance,
                    JDRequirement.named_technologies,
                ).where(JDRequirement.jd_id == version.jd_id)
            )
        ).all()
        required_skills = [
            skill for skill, importance, _ in requirement_rows if importance == "required"
        ]
        known_technologies = list(
            dict.fromkeys(term for _, _, terms in requirement_rows for term in (terms or []))
        )
        action_verbs = list(
            (
                await session.scalars(
                    select(JDActionVerb.verb).where(JDActionVerb.jd_id == version.jd_id)
                )
            ).all()
        )
        item_tag_rows = (
            await session.scalars(
                select(SkillBankItem.tags).where(SkillBankItem.user_id == owner_id)
            )
        ).all()
        bullet_tag_rows = (
            await session.scalars(
                select(BulletPoint.tags)
                .join(SkillBankItem, SkillBankItem.id == BulletPoint.item_id)
                .where(SkillBankItem.user_id == owner_id)
            )
        ).all()
        allowed_skills = list(
            dict.fromkeys(
                term for tags in [*item_tag_rows, *bullet_tag_rows] for term in (tags or [])
            )
        )
        job.status = "running"
        await session.commit()

    try:
        by_id = {bullet.id: bullet for bullet in bullets}
        rewrites = await rewriter.rewrite_bullets(
            owner_id,
            [by_id[bullet_id].text for bullet_id in bullet_ids],
            required_skills,
            action_verbs,
            ats_keywords,
            allowed_skills,
            known_technologies,
        )
        results = [
            (
                by_id[bullet_id],
                int((job.result or {}).get("section_orders", {}).get(str(bullet_id), order)),
                rewritten,
                flags,
                low_effort,
            )
            for order, (bullet_id, (rewritten, flags, low_effort)) in enumerate(
                zip(bullet_ids, rewrites, strict=True)
            )
        ]
    except llm_client.LLMNotConfiguredError:
        await _fail(version_id, job_id, owner_id, "No LLM provider configured")
        return
    except llm_client.LLMAuthError:
        await _fail(version_id, job_id, owner_id, "Your API key was rejected by the provider")
        return
    except llm_client.LLMRateLimitError:
        await _fail(version_id, job_id, owner_id, "Your provider rate limit was reached")
        return
    except llm_client.LLMError:
        await _fail(
            version_id, job_id, owner_id, "The LLM provider could not rewrite these bullets"
        )
        return
    except Exception:
        await _fail(version_id, job_id, owner_id, "The rewrite could not be completed safely")
        return

    async with async_session_factory() as session:
        version = await session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id,
                ResumeVersion.user_id == owner_id,
                ResumeVersion.status == "rewriting",
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id,
                BackgroundJob.user_id == owner_id,
                BackgroundJob.status == "running",
            )
        )
        if version is None or job is None:
            return
        current_bullets = {
            bullet.id: bullet
            for bullet in (
                await session.scalars(
                    select(BulletPoint)
                    .join(SkillBankItem, SkillBankItem.id == BulletPoint.item_id)
                    .where(BulletPoint.id.in_(bullet_ids), SkillBankItem.user_id == owner_id)
                )
            ).all()
        }
        if len(current_bullets) != len(bullet_ids) or any(
            current_bullets[bullet.id].text != bullet.text
            for bullet, _, _, _, _ in results
            if bullet.id in current_bullets
        ):
            version.status = "draft"
            job.status = "failed"
            job.error = "A selected bullet changed while it was being rewritten — try again"
            await session.commit()
            return
        session.add_all(
            [
                ResumeBulletSelection(
                    resume_version_id=version_id,
                    bullet_point_id=bullet.id,
                    original_text=bullet.text,
                    rewritten_text=rewritten,
                    approved=False,
                    resolved=False,
                    flagged_terms=flags,
                    low_effort_rewrite=low_effort,
                    section_order=order,
                )
                for bullet, order, rewritten, flags, low_effort in results
            ]
        )
        version.status = "reviewing"
        job.status = "done"
        job.error = None
        job.result = {"resume_version_id": str(version_id), "bullets": len(results)}
        await session.commit()
