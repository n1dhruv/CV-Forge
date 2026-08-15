from typing import Any
from uuid import UUID

import litellm
from openai import OpenAIError
from sqlalchemy import select

from app.core.encryption import decrypt
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.settings import UserLLMSettings

COMPLETION_TIMEOUT_SECONDS = 60
COMPLETION_RETRIES = 2
EMBEDDING_DIMENSIONS = 2048
EMBEDDING_MODEL = "openrouter/nvidia/nemotron-3-embed-1b:free"
COMPLETION_RETRY_POLICY = {
    "AuthenticationErrorRetries": 0,
    "BadRequestErrorRetries": 0,
    "ContentPolicyViolationErrorRetries": 0,
    "InternalServerErrorRetries": COMPLETION_RETRIES,
    "RateLimitErrorRetries": COMPLETION_RETRIES,
    "TimeoutErrorRetries": COMPLETION_RETRIES,
}


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


class EmbeddingProviderUnsupportedError(LLMError):
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
    del user_id  # The server-managed OpenRouter fallback is always configured.


async def get_completion(
    user_id: UUID,
    messages: list[dict[str, str]],
    *,
    allow_fallback: bool = True,
    **kwargs: Any,
) -> str:
    settings = await _settings_for_user(user_id)
    app_settings = get_settings()
    kwargs.setdefault("timeout", COMPLETION_TIMEOUT_SECONDS)
    kwargs.setdefault("num_retries", COMPLETION_RETRIES)
    kwargs.setdefault("retry_policy", COMPLETION_RETRY_POLICY)
    attempts = []
    if settings is not None:
        attempts.append(
            (
                provider_model(settings.provider, settings.model),
                decrypt(settings.encrypted_api_key),
            )
        )
    if allow_fallback:
        fallback = (
            f"openrouter/{app_settings.openrouter_fallback_model}",
            app_settings.openrouter_api_key.get_secret_value(),
        )
        if fallback not in attempts:
            attempts.append(fallback)
    elif not attempts:
        raise LLMNotConfiguredError("No user completion model is configured")

    for model, api_key in attempts:
        try:
            response = await litellm.acompletion(
                model=model,
                api_key=api_key,
                messages=messages,
                **kwargs,
            )
            content = response.choices[0].message.content
            if isinstance(content, str) and content.strip():
                return content
        except (
            litellm.AuthenticationError,
            litellm.PermissionDeniedError,
            litellm.RateLimitError,
            OpenAIError,
            AttributeError,
            IndexError,
        ):
            continue
    raise LLMProviderError("The LLM provider could not complete the request")


async def get_embeddings(user_id: UUID, texts: list[str]) -> list[list[float]]:
    del user_id
    if not texts:
        return []
    settings = get_settings()

    try:
        response = await litellm.aembedding(
            model=EMBEDDING_MODEL,
            api_key=settings.openrouter_api_key.get_secret_value(),
            input=texts,
            dimensions=EMBEDDING_DIMENSIONS,
        )
    except (litellm.AuthenticationError, litellm.PermissionDeniedError):
        raise LLMAuthError("The provider rejected the configured credentials") from None
    except litellm.RateLimitError:
        raise LLMRateLimitError("The provider rate limit was reached") from None
    except OpenAIError:
        raise LLMProviderError("The LLM provider could not create an embedding") from None

    try:
        vectors = [item["embedding"] for item in response.data]
    except (AttributeError, KeyError, TypeError):
        raise LLMProviderError("The LLM provider returned an invalid embedding") from None
    if len(vectors) != len(texts) or any(
        not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSIONS for vector in vectors
    ):
        raise LLMProviderError(
            f"The embedding provider must return {EMBEDDING_DIMENSIONS}-dimension vectors"
        )
    return [[float(value) for value in vector] for vector in vectors]


async def get_embedding(user_id: UUID, text: str) -> list[float]:
    return (await get_embeddings(user_id, [text]))[0]
