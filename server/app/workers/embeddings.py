import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.services import embeddings as embedding_service
from app.services import llm_client, vector_store


async def _finish(
    job_id: UUID,
    user_id: UUID,
    record_id: UUID,
    result_key: str,
    dense_stored: bool,
    sparse_stored: bool,
    error: str | None,
) -> None:
    async with async_session_factory() as session:
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id, BackgroundJob.user_id == user_id
            )
        )
        if job is None:
            return
        job.status = "done" if dense_stored and sparse_stored else "failed"
        job.error = error
        job.result = {
            result_key: str(record_id),
            "dense_stored": dense_stored,
            "sparse_stored": sparse_stored,
        }
        await session.commit()


async def _embed_record(
    user_id: UUID,
    record_id: UUID,
    text: str,
    metadata: dict,
    level: str,
) -> tuple[bool, bool, str | None]:
    dense_embedding, sparse_values = await asyncio.gather(
        llm_client.get_embedding(user_id, text),
        asyncio.to_thread(vector_store.sparse_embedding, text, "passage"),
        return_exceptions=True,
    )
    errors: list[str] = []
    dense_stored = False
    sparse_stored = False

    if isinstance(dense_embedding, BaseException):
        if isinstance(dense_embedding, llm_client.LLMNotConfiguredError):
            errors.append("No embedding provider configured")
        elif isinstance(dense_embedding, llm_client.EmbeddingProviderUnsupportedError):
            errors.append(str(dense_embedding))
        else:
            errors.append("The embedding provider could not process this evidence")
    else:
        try:
            await asyncio.to_thread(
                vector_store.upsert_dense_vector,
                user_id,
                record_id,
                dense_embedding,
                metadata,
                level,
            )
            dense_stored = True
        except Exception:
            errors.append("Pinecone could not store the dense embedding")

    if isinstance(sparse_values, BaseException):
        errors.append("Pinecone could not create the sparse embedding")
    else:
        try:
            await asyncio.to_thread(
                vector_store.upsert_sparse_vector,
                user_id,
                record_id,
                sparse_values,
                metadata,
                level,
            )
            sparse_stored = True
        except Exception:
            errors.append("Pinecone could not store the sparse embedding")

    return dense_stored, sparse_stored, "; ".join(errors) or None


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

    dense_stored, sparse_stored, error = await _embed_record(
        parsed_user_id,
        parsed_bullet_id,
        text,
        metadata,
        "bullet",
    )

    await _finish(
        parsed_job_id,
        parsed_user_id,
        parsed_bullet_id,
        "bullet_id",
        dense_stored,
        sparse_stored,
        error,
    )


async def embed_item_task(
    context: dict[str, Any], item_id: str, background_job_id: str, user_id: str
) -> None:
    del context
    parsed_item_id = UUID(item_id)
    parsed_job_id = UUID(background_job_id)
    parsed_user_id = UUID(user_id)
    async with async_session_factory() as session:
        item = await session.scalar(
            select(SkillBankItem).where(
                SkillBankItem.id == parsed_item_id,
                SkillBankItem.user_id == parsed_user_id,
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == parsed_job_id,
                BackgroundJob.user_id == parsed_user_id,
            )
        )
        if item is None or job is None:
            return
        job.status = "running"
        await session.commit()
        text = embedding_service.item_text(item)
        metadata = {"item_id": str(item.id), "item_type": item.type}

    dense_stored, sparse_stored, error = await _embed_record(
        parsed_user_id,
        parsed_item_id,
        text,
        metadata,
        "item",
    )
    await _finish(
        parsed_job_id,
        parsed_user_id,
        parsed_item_id,
        "item_id",
        dense_stored,
        sparse_stored,
        error,
    )
