from typing import Any
from uuid import UUID

import litellm
from sqlalchemy import select

from app.core.encryption import decrypt
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.settings import UserLLMSettings

COMPLETION_TIMEOUT_SECONDS = 60
COMPLETION_RETRIES = 2
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
    if await _settings_for_user(user_id) is None:
        raise LLMNotConfiguredError("No LLM provider configured")


async def get_completion(user_id: UUID, messages: list[dict[str, str]], **kwargs: Any) -> str:
    settings = await _settings_for_user(user_id)
    if settings is None:
        raise LLMNotConfiguredError("No LLM provider configured")

    kwargs.setdefault("timeout", COMPLETION_TIMEOUT_SECONDS)
    kwargs.setdefault("num_retries", COMPLETION_RETRIES)
    kwargs.setdefault("retry_policy", COMPLETION_RETRY_POLICY)
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


async def get_embeddings(user_id: UUID, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = await _settings_for_user(user_id)
    if settings is None:
        raise LLMNotConfiguredError("No LLM provider configured")

    provider = settings.embedding_provider or settings.provider
    model = settings.embedding_model or get_settings().embedding_model
    encrypted_key = settings.encrypted_embedding_api_key or settings.encrypted_api_key
    if not model:
        raise EmbeddingProviderUnsupportedError(
            "No embedding model is configured for this provider"
        )
    resolved_model = provider_model(provider, model)
    try:
        if litellm.get_model_info(resolved_model).get("mode") != "embedding":
            raise EmbeddingProviderUnsupportedError(
                f"{provider} does not support the configured embedding model"
            )
    except EmbeddingProviderUnsupportedError:
        raise
    except Exception:
        # Unknown/custom models are allowed to reach the provider.
        pass

    try:
        response = await litellm.aembedding(
            model=resolved_model,
            api_key=decrypt(encrypted_key),
            input=texts,
        )
    except (litellm.AuthenticationError, litellm.PermissionDeniedError):
        raise LLMAuthError("The provider rejected the configured credentials") from None
    except litellm.RateLimitError:
        raise LLMRateLimitError("The provider rate limit was reached") from None
    except litellm.BadRequestError as exc:
        raise EmbeddingProviderUnsupportedError(
            f"{provider} does not support the configured embedding model"
        ) from exc
    except (
        litellm.APIError,
        litellm.APIConnectionError,
        litellm.NotFoundError,
        litellm.ServiceUnavailableError,
        litellm.Timeout,
    ):
        raise LLMProviderError("The LLM provider could not create an embedding") from None

    try:
        vectors = [item["embedding"] for item in response.data]
    except (AttributeError, KeyError, TypeError):
        raise LLMProviderError("The LLM provider returned an invalid embedding") from None
    if len(vectors) != len(texts) or any(
        not isinstance(vector, list) or not vector for vector in vectors
    ):
        raise LLMProviderError("The LLM provider returned an invalid embedding")
    return [[float(value) for value in vector] for vector in vectors]


async def get_embedding(user_id: UUID, text: str) -> list[float]:
    return (await get_embeddings(user_id, [text]))[0]
