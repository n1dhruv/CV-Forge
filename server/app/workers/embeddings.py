import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.services import llm_client, vector_store


async def _fail(job_id: UUID, user_id: UUID, error: str) -> None:
    async with async_session_factory() as session:
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id, BackgroundJob.user_id == user_id
            )
        )
        if job is None:
            return
        job.status = "failed"
        job.error = error
        await session.commit()


async def embed_bullet_task(
    context: dict[str, Any], bullet_id: str, background_job_id: str, user_id: str
) -> None:
    del context
    parsed_bullet_id = UUID(bullet_id)
    parsed_job_id = UUID(background_job_id)
    parsed_user_id = UUID(user_id)
    async with async_session_factory() as session:
        bullet = await session.scalar(
            select(BulletPoint)
            .join(SkillBankItem)
            .options(selectinload(BulletPoint.item))
            .where(BulletPoint.id == parsed_bullet_id, SkillBankItem.user_id == parsed_user_id)
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == parsed_job_id,
                BackgroundJob.user_id == parsed_user_id,
            )
        )
        if bullet is None or job is None:
            return
        job.status = "running"
        await session.commit()
        text = bullet.text
        metadata = {"item_id": str(bullet.item_id), "item_type": bullet.item.type}

    try:
        embedding = await llm_client.get_embedding(parsed_user_id, text)
        await asyncio.to_thread(
            vector_store.upsert_vector,
            parsed_user_id,
            parsed_bullet_id,
            embedding,
            metadata,
        )
    except llm_client.LLMNotConfiguredError:
        await _fail(parsed_job_id, parsed_user_id, "No embedding provider configured")
        return
    except llm_client.EmbeddingProviderUnsupportedError as exc:
        await _fail(parsed_job_id, parsed_user_id, str(exc))
        return
    except llm_client.LLMError:
        await _fail(
            parsed_job_id, parsed_user_id, "The embedding provider could not process this bullet"
        )
        return
    except Exception:
        await _fail(parsed_job_id, parsed_user_id, "Pinecone could not store this embedding")
        return

    async with async_session_factory() as session:
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == parsed_job_id,
                BackgroundJob.user_id == parsed_user_id,
            )
        )
        if job is None:
            return
        job.status = "done"
        job.error = None
        job.result = {"bullet_id": str(parsed_bullet_id)}
        await session.commit()
