import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.services import llm_client, matcher, vector_store

logger = logging.getLogger(__name__)


async def _finish(
    job_id: UUID,
    user_id: UUID,
    status: str,
    *,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    async with async_session_factory() as session:
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id,
                BackgroundJob.user_id == user_id,
                BackgroundJob.job_type == "match",
            )
        )
        if job is None:
            return
        job.status = status
        job.result = result
        job.error = error
        await session.commit()


async def match_jd_task(
    context: dict[str, Any], jd_id: str, background_job_id: str, user_id: str
) -> None:
    del context
    parsed_jd_id = UUID(jd_id)
    parsed_job_id = UUID(background_job_id)
    parsed_user_id = UUID(user_id)
    await _finish(
        parsed_job_id,
        parsed_user_id,
        "running",
        result={"jd_id": str(parsed_jd_id)},
    )

    try:
        result = await matcher.match_jd(parsed_user_id, parsed_jd_id)
        if result is None:
            await _finish(
                parsed_job_id,
                parsed_user_id,
                "failed",
                error="Job description no longer exists",
            )
            return
    except asyncio.CancelledError:
        await _finish(
            parsed_job_id,
            parsed_user_id,
            "failed",
            error="Matching timed out — try again",
        )
        raise
    except llm_client.EmbeddingProviderUnsupportedError as exc:
        error = str(exc)
    except llm_client.LLMNotConfiguredError:
        error = "No embedding provider configured"
    except llm_client.LLMError:
        error = "Embedding provider unavailable — check Settings and retry"
    except vector_store.VectorStoreError as exc:
        error = str(exc)
    except Exception:
        logger.exception("Unexpected matching failure for JD %s", parsed_jd_id)
        error = "The matching worker could not finish — try again"
    else:
        await _finish(
            parsed_job_id,
            parsed_user_id,
            "done",
            result=result.model_dump(mode="json"),
        )
        return

    logger.warning("Matching failed for JD %s: %s", parsed_jd_id, error)
    await _finish(parsed_job_id, parsed_user_id, "failed", error=error)
