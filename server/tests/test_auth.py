import time
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import get_settings
from app.core.security import get_current_user, jwks_cache
from app.models.user import User


@pytest.fixture
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks_cache._keys = {"test-key": key.public_key()}
    jwks_cache._expires_at = time.monotonic() + 60
    return key


def token(signing_key, **overrides):
    now = int(time.time())
    claims = {"sub": "user_123", "iss": "https://clerk.example", "iat": now, "exp": now + 60}
    claims.update(overrides)
    return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-key"})


async def authenticate(raw_token, local_user):
    session = AsyncMock()
    session.scalar.return_value = local_user
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw_token)
    return await get_current_user(credentials, session, get_settings())


async def test_valid_token_succeeds(signing_key):
    user = User(id=uuid4(), clerk_user_id="user_123", email="person@example.com")
    assert await authenticate(token(signing_key), user) is user


@pytest.mark.parametrize("raw_token", ["malformed", "a.b.c"])
async def test_malformed_token_is_unauthorized(raw_token):
    with pytest.raises(HTTPException) as exc:
        await authenticate(raw_token, None)
    assert exc.value.status_code == 401


async def test_expired_token_is_unauthorized(signing_key):
    with pytest.raises(HTTPException) as exc:
        await authenticate(token(signing_key, exp=int(time.time()) - 10), None)
    assert exc.value.status_code == 401


async def test_unsynchronized_user_is_unauthorized(signing_key):
    with pytest.raises(HTTPException) as exc:
        await authenticate(token(signing_key), None)
    assert exc.value.status_code == 401
