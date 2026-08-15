from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.api.settings.llm import (
    delete_llm_settings,
    read_llm_settings,
    test_llm_settings as run_connection_test,
)
from app.models.settings import UserLLMSettings
from app.models.user import User
from app.schemas.llm_settings import LLMSettingsCreate
from app.services import llm_client, llm_settings


async def test_saving_settings_encrypts_api_key() -> None:
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    user_id = uuid4()

    saved = await llm_settings.save_for_user(
        session,
        user_id,
        LLMSettingsCreate(provider="openai", model="gpt-4o-mini", api_key="sk-plain"),
    )

    assert saved.encrypted_api_key != "sk-plain"
    assert "sk-plain" not in saved.encrypted_api_key
    session.commit.assert_awaited_once()


async def test_updating_chat_key_preserves_legacy_embedding_data() -> None:
    old_chat_key = llm_settings.encrypt("old-chat-key")
    old_embedding_key = llm_settings.encrypt("old-embedding-key")
    settings = UserLLMSettings(
        user_id=uuid4(),
        provider="openai",
        model="gpt-4o-mini",
        encrypted_api_key=old_chat_key,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        encrypted_embedding_api_key=old_embedding_key,
    )
    session = MagicMock()
    session.scalar = AsyncMock(return_value=settings)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    await llm_settings.save_for_user(
        session,
        settings.user_id,
        LLMSettingsCreate(
            provider="openai",
            model="gpt-4o-mini",
            api_key="new-chat-key",
        ),
    )

    assert llm_settings.decrypt(settings.encrypted_api_key) == "new-chat-key"
    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.encrypted_embedding_api_key == old_embedding_key


async def test_initial_settings_require_the_missing_api_key() -> None:
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)

    with pytest.raises(llm_settings.MissingAPIKeyError, match="Chat API key"):
        await llm_settings.save_for_user(
            session,
            uuid4(),
            LLMSettingsCreate(provider="openai", model="gpt-4o-mini"),
        )

    session.add.assert_not_called()


async def test_read_settings_only_returns_masked_key(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=uuid4(), email="a@example.com")
    settings = UserLLMSettings(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        encrypted_api_key=llm_settings.encrypt("sk-secret-ab12"),
    )
    monkeypatch.setattr(llm_settings, "get_for_user", AsyncMock(return_value=settings))

    response = await read_llm_settings(AsyncMock(), user)

    assert response.masked_key == "••••ab12"
    assert "sk-secret" not in response.model_dump_json()


def test_short_key_is_never_returned_in_full() -> None:
    settings = UserLLMSettings(
        user_id=uuid4(),
        provider="custom",
        model="model",
        encrypted_api_key=llm_settings.encrypt("abc"),
    )

    assert llm_settings.masked_key(settings) == "••••"


async def test_missing_settings_use_openrouter_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="fallback"))]
        )
    )
    monkeypatch.setattr(llm_client, "_settings_for_user", AsyncMock(return_value=None))
    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)

    result = await llm_client.get_completion(uuid4(), [{"role": "user", "content": "hello"}])

    assert result == "fallback"
    assert completion.await_args.kwargs["model"] == (
        "openrouter/nvidia/nemotron-3.5-lightning:free"
    )
    assert completion.await_args.kwargs["api_key"] == "test"


async def test_primary_auth_failure_uses_openrouter_fallback_without_leaking_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    settings = UserLLMSettings(
        user_id=user_id,
        provider="openai",
        model="gpt-4o-mini",
        encrypted_api_key=llm_settings.encrypt("sk-super-secret"),
    )
    provider_error = llm_client.litellm.AuthenticationError(
        "invalid sk-super-secret", "openai", "gpt-4o-mini"
    )
    monkeypatch.setattr(llm_client, "_settings_for_user", AsyncMock(return_value=settings))
    completion = AsyncMock(
        side_effect=[
            provider_error,
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fallback"))]),
        ]
    )
    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)

    result = await llm_client.get_completion(user_id, [{"role": "user", "content": "hello"}])

    assert result == "fallback"
    assert "sk-super-secret" not in repr(completion.await_args_list[1])
    assert completion.await_args_list[1].kwargs["model"] == (
        "openrouter/nvidia/nemotron-3.5-lightning:free"
    )


async def test_primary_internal_error_uses_openrouter_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    settings = UserLLMSettings(
        user_id=user_id,
        provider="openai",
        model="gpt-4o-mini",
        encrypted_api_key=llm_settings.encrypt("primary-key"),
    )
    monkeypatch.setattr(llm_client, "_settings_for_user", AsyncMock(return_value=settings))
    completion = AsyncMock(
        side_effect=[
            llm_client.litellm.InternalServerError(
                "provider unavailable", "openai", "gpt-4o-mini"
            ),
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fallback"))]),
        ]
    )
    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)

    assert await llm_client.get_completion(
        user_id, [{"role": "user", "content": "hello"}]
    ) == "fallback"
    assert completion.await_count == 2


async def test_completion_uses_bounded_transient_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    settings = UserLLMSettings(
        user_id=user_id,
        provider="google",
        model="gemini-3.6-flash",
        encrypted_api_key=llm_settings.encrypt("google-key"),
    )
    completion = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))]
        )
    )
    monkeypatch.setattr(llm_client, "_settings_for_user", AsyncMock(return_value=settings))
    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)

    assert await llm_client.get_completion(user_id, [{"role": "user", "content": "hello"}]) == "{}"

    kwargs = completion.await_args.kwargs
    assert kwargs["timeout"] == 60
    assert kwargs["num_retries"] == 2
    assert kwargs["retry_policy"] == {
        "AuthenticationErrorRetries": 0,
        "BadRequestErrorRetries": 0,
        "ContentPolicyViolationErrorRetries": 0,
        "InternalServerErrorRetries": 2,
        "RateLimitErrorRetries": 2,
        "TimeoutErrorRetries": 2,
    }


async def test_connection_endpoint_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = AsyncMock(return_value="OK")
    monkeypatch.setattr(llm_client, "get_completion", completion)
    user = User(id=uuid4(), email="a@example.com")

    result = await run_connection_test(user)

    assert result.model_dump() == {"success": True, "error": None}
    assert completion.await_args.kwargs["allow_fallback"] is False


async def test_connection_endpoint_normalizes_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        llm_client,
        "get_completion",
        AsyncMock(side_effect=llm_client.LLMAuthError("credentials rejected")),
    )
    user = User(id=uuid4(), email="a@example.com")

    result = await run_connection_test(user)

    assert result.model_dump() == {"success": False, "error": "credentials rejected"}


async def test_settings_lookup_is_always_scoped_to_current_user() -> None:
    session = AsyncMock()
    session.scalar.return_value = None

    await llm_settings.get_for_user(session, uuid4())

    sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "user_llm_settings.user_id" in sql


async def test_second_user_get_and_delete_return_404(monkeypatch: pytest.MonkeyPatch) -> None:
    user_b = User(id=uuid4(), email="b@example.com")
    monkeypatch.setattr(llm_settings, "get_for_user", AsyncMock(return_value=None))
    monkeypatch.setattr(llm_settings, "delete_for_user", AsyncMock(return_value=False))

    with pytest.raises(HTTPException) as read_error:
        await read_llm_settings(AsyncMock(), user_b)
    with pytest.raises(HTTPException) as delete_error:
        await delete_llm_settings(AsyncMock(), user_b)

    assert read_error.value.status_code == 404
    assert delete_error.value.status_code == 404


def test_provider_model_uses_litellm_prefixes() -> None:
    assert llm_client.provider_model("google", "gemini-1.5-flash") == "gemini/gemini-1.5-flash"
    assert llm_client.provider_model("anthropic", "claude-haiku-4-5") == (
        "anthropic/claude-haiku-4-5"
    )
    assert llm_client.provider_model("custom", "openrouter/model") == "openrouter/model"


async def test_get_embedding_always_uses_nvidia_openrouter_at_2048_dimensions(monkeypatch) -> None:
    user_id = uuid4()
    vector = [0.1] * 2048
    monkeypatch.setattr(
        llm_client,
        "_settings_for_user",
        AsyncMock(side_effect=AssertionError("embedding must ignore user settings")),
    )
    embedding = AsyncMock(return_value=SimpleNamespace(data=[{"embedding": vector}]))
    monkeypatch.setattr(llm_client.litellm, "aembedding", embedding)

    assert await llm_client.get_embedding(user_id, "Built APIs") == vector
    assert embedding.await_args.kwargs["model"] == ("openrouter/nvidia/nemotron-3-embed-1b:free")
    assert embedding.await_args.kwargs["api_key"] == "test"
    assert embedding.await_args.kwargs["dimensions"] == 2048


async def test_get_embeddings_batches_provider_request(monkeypatch) -> None:
    user_id = uuid4()
    vector_a, vector_b = [0.1] * 2048, [0.2] * 2048
    embedding = AsyncMock(
        return_value=SimpleNamespace(data=[{"embedding": vector_a}, {"embedding": vector_b}])
    )
    monkeypatch.setattr(llm_client.litellm, "aembedding", embedding)

    result = await llm_client.get_embeddings(user_id, ["Python APIs", "Apache Kafka"])

    assert result == [vector_a, vector_b]
    assert embedding.await_args.kwargs["input"] == ["Python APIs", "Apache Kafka"]


async def test_embedding_rejects_wrong_vector_dimension(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_client.litellm,
        "aembedding",
        AsyncMock(return_value=SimpleNamespace(data=[{"embedding": [0.1]}])),
    )

    with pytest.raises(llm_client.LLMProviderError, match="2048"):
        await llm_client.get_embedding(uuid4(), "Built APIs")
