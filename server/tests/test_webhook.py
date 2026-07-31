import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from svix.webhooks import Webhook

from app.api.webhooks import clerk_webhook
from app.core.config import get_settings


def request_for(body: bytes, headers: dict[str, str]) -> Request:
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhooks/clerk",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
    }
    return Request(scope, receive)


def signed_request(event: dict) -> Request:
    body_text = json.dumps(event, separators=(",", ":"))
    timestamp = datetime.now(UTC)
    signature = Webhook(get_settings().clerk_webhook_signing_secret.get_secret_value()).sign(
        "msg_test", timestamp, body_text
    )
    headers = {
        "svix-id": "msg_test",
        "svix-timestamp": str(int(timestamp.timestamp())),
        "svix-signature": signature,
    }
    return request_for(body_text.encode(), headers)


async def test_valid_signature_creates_user_and_duplicate_is_idempotent():
    event = {
        "type": "user.created",
        "data": {
            "id": "user_123",
            "primary_email_address_id": "email_1",
            "email_addresses": [{"id": "email_1", "email_address": "person@example.com"}],
            "first_name": "Test",
            "last_name": "User",
        },
    }
    session = AsyncMock()
    for _ in range(2):
        response = await clerk_webhook(signed_request(event), session, get_settings())
        assert response == {"status": "ok"}
    assert session.execute.await_count == 2
    assert session.commit.await_count == 2


async def test_invalid_signature_is_rejected():
    request = request_for(b"{}", {"content-type": "application/json"})
    with pytest.raises(HTTPException) as exc:
        await clerk_webhook(request, AsyncMock(), get_settings())
    assert exc.value.status_code == 400
