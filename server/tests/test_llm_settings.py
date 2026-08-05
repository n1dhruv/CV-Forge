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


async def test_missing_settings_never_attempts_network(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = AsyncMock()
    monkeypatch.setattr(llm_client, "_settings_for_user", AsyncMock(return_value=None))
    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)

    with pytest.raises(llm_client.LLMNotConfiguredError):
        await llm_client.get_completion(uuid4(), [{"role": "user", "content": "hello"}])

    completion.assert_not_awaited()


async def test_litellm_auth_error_is_normalized_without_key(
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
    monkeypatch.setattr(llm_client.litellm, "acompletion", AsyncMock(side_effect=provider_error))

    with pytest.raises(llm_client.LLMAuthError) as caught:
        await llm_client.get_completion(user_id, [{"role": "user", "content": "hello"}])

    assert "sk-super-secret" not in str(caught.value)


async def test_connection_endpoint_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "get_completion", AsyncMock(return_value="OK"))
    user = User(id=uuid4(), email="a@example.com")

    result = await run_connection_test(user)

    assert result.model_dump() == {"success": True, "error": None}


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
