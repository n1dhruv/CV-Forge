from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.security import CurrentUser
from app.schemas.match import MatchResult
from app.services import llm_client, matcher, vector_store

router = APIRouter(prefix="/api/match", tags=["matching"])


@router.post("/{jd_id}", response_model=MatchResult)
async def match_job_description(
    jd_id: UUID, current_user: CurrentUser
) -> MatchResult:
    try:
        result = await matcher.match_jd(current_user.id, jd_id)
    except llm_client.EmbeddingProviderUnsupportedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except llm_client.LLMNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail="No embedding provider configured") from exc
    except llm_client.LLMError as exc:
        raise HTTPException(status_code=502, detail="Embedding provider unavailable") from exc
    except vector_store.VectorStoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Completed job description not found")
    return result
