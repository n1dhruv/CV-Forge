from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.session import get_db_session
from app.schemas.llm_settings import (
    LLMSettingsCreate,
    LLMSettingsRead,
    LLMSettingsSaved,
    LLMTestResult,
)
from app.services import llm_client, llm_settings

router = APIRouter(prefix="/api/settings/llm", tags=["llm-settings"])
Session = Annotated[AsyncSession, Depends(get_db_session)]

SUPPORTED_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "anthropic": ["claude-sonnet-4-5", "claude-haiku-4-5"],
    "google": ["gemini-1.5-pro", "gemini-1.5-flash"],
}


@router.get("/supported-models")
async def supported_models() -> dict[str, list[str]]:
    return SUPPORTED_MODELS


@router.post("", response_model=LLMSettingsSaved)
async def save_llm_settings(
    payload: LLMSettingsCreate, session: Session, current_user: CurrentUser
) -> LLMSettingsSaved:
    settings = await llm_settings.save_for_user(session, current_user.id, payload)
    return LLMSettingsSaved(provider=settings.provider, model=settings.model)


@router.get("", response_model=LLMSettingsRead)
async def read_llm_settings(session: Session, current_user: CurrentUser) -> LLMSettingsRead:
    settings = await llm_settings.get_for_user(session, current_user.id)
    if settings is None:
        raise HTTPException(status_code=404, detail="LLM settings not found")
    return LLMSettingsRead(
        provider=settings.provider,
        model=settings.model,
        masked_key=llm_settings.masked_key(settings),
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_settings(session: Session, current_user: CurrentUser) -> Response:
    if not await llm_settings.delete_for_user(session, current_user.id):
        raise HTTPException(status_code=404, detail="LLM settings not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", response_model=LLMTestResult)
async def test_llm_settings(current_user: CurrentUser) -> LLMTestResult:
    try:
        await llm_client.get_completion(
            current_user.id,
            [{"role": "user", "content": "Reply with OK."}],
        )
    except llm_client.LLMError as exc:
        return LLMTestResult(success=False, error=str(exc))
    return LLMTestResult(success=True)
