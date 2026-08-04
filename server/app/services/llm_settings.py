from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt, encrypt
from app.models.settings import UserLLMSettings
from app.schemas.llm_settings import LLMSettingsCreate


async def get_for_user(session: AsyncSession, user_id: UUID) -> UserLLMSettings | None:
    return await session.scalar(select(UserLLMSettings).where(UserLLMSettings.user_id == user_id))


async def save_for_user(
    session: AsyncSession, user_id: UUID, payload: LLMSettingsCreate
) -> UserLLMSettings:
    settings = await get_for_user(session, user_id)
    if settings is None:
        settings = UserLLMSettings(user_id=user_id)
        session.add(settings)
    settings.provider = payload.provider
    settings.model = payload.model
    settings.encrypted_api_key = encrypt(payload.api_key.get_secret_value())
    await session.commit()
    await session.refresh(settings)
    return settings


async def delete_for_user(session: AsyncSession, user_id: UUID) -> bool:
    settings = await get_for_user(session, user_id)
    if settings is None:
        return False
    await session.delete(settings)
    await session.commit()
    return True


def masked_key(settings: UserLLMSettings) -> str:
    api_key = decrypt(settings.encrypted_api_key)
    return f"••••{api_key[-4:] if len(api_key) > 4 else ''}"
