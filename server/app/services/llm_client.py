from typing import Any
from uuid import UUID

import litellm
from sqlalchemy import select

from app.core.encryption import decrypt
from app.db.session import async_session_factory
from app.models.settings import UserLLMSettings


class LLMError(Exception):
    """Base exception for safe, provider-independent LLM failures."""


class LLMNotConfiguredError(LLMError):
    pass


class LLMAuthError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMProviderError(LLMError):
    pass


def provider_model(provider: str, model: str) -> str:
    if "/" in model:
        return model
    prefix = {"google": "gemini"}.get(provider.strip().lower(), provider.strip().lower())
    return f"{prefix}/{model.strip()}"


async def _settings_for_user(user_id: UUID) -> UserLLMSettings | None:
    async with async_session_factory() as session:
        return await session.scalar(
            select(UserLLMSettings).where(UserLLMSettings.user_id == user_id)
        )


async def ensure_configured(user_id: UUID) -> None:
    if await _settings_for_user(user_id) is None:
        raise LLMNotConfiguredError("No LLM provider configured")


async def get_completion(user_id: UUID, messages: list[dict[str, str]], **kwargs: Any) -> str:
    settings = await _settings_for_user(user_id)
    if settings is None:
        raise LLMNotConfiguredError("No LLM provider configured")

    try:
        response = await litellm.acompletion(
            model=provider_model(settings.provider, settings.model),
            api_key=decrypt(settings.encrypted_api_key),
            messages=messages,
            **kwargs,
        )
    except (litellm.AuthenticationError, litellm.PermissionDeniedError):
        raise LLMAuthError("The provider rejected the configured credentials") from None
    except litellm.RateLimitError:
        raise LLMRateLimitError("The provider rate limit was reached") from None
    except (
        litellm.APIError,
        litellm.APIConnectionError,
        litellm.BadRequestError,
        litellm.NotFoundError,
        litellm.ServiceUnavailableError,
        litellm.Timeout,
    ):
        raise LLMProviderError("The LLM provider could not complete the request") from None

    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise LLMProviderError("The LLM provider returned an empty response")
    return content
