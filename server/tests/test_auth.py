import time
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt.algorithms import RSAAlgorithm

from app.core.config import get_settings
from app.core.security import get_current_user, jwks_cache
from app.models.user import User


@pytest.fixture
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update({"alg": "RS256", "kid": "test-key", "use": "sig"})
    jwks_cache._keys = {"test-key": jwt.PyJWK.from_dict(jwk)}
    jwks_cache._expires_at = time.monotonic() + 60
    return key


def token(signing_key, **overrides):
    now = int(time.time())
    claims = {
        "aud": "authenticated",
        "email": "person@example.com",
        "exp": now + 60,
        "iat": now,
        "iss": "https://example.supabase.co/auth/v1",
        "role": "authenticated",
        "sub": str(uuid4()),
    }
    claims.update(overrides)
    return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-key"})


async def authenticate(raw_token, local_user=None):
    session = AsyncMock()
    session.get.return_value = local_user
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw_token)
    result = await get_current_user(credentials, session, get_settings())
    return result, session


async def test_valid_token_initializes_and_returns_user(signing_key):
    user_id = uuid4()
    user = User(id=user_id, email="person@example.com")

    result, session = await authenticate(token(signing_key, sub=str(user_id)), user)

    assert result is user
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.get.assert_awaited_once_with(User, user_id)


@pytest.mark.parametrize("raw_token", ["malformed", "a.b.c"])
async def test_malformed_token_is_unauthorized(raw_token):
    with pytest.raises(HTTPException) as exc:
        await authenticate(raw_token)
    assert exc.value.status_code == 401


async def test_expired_token_is_unauthorized(signing_key):
    with pytest.raises(HTTPException) as exc:
        await authenticate(token(signing_key, exp=int(time.time()) - 10))
    assert exc.value.status_code == 401


async def test_wrong_audience_is_unauthorized(signing_key):
    with pytest.raises(HTTPException) as exc:
        await authenticate(token(signing_key, aud="anon"))
    assert exc.value.status_code == 401


async def test_missing_email_is_unauthorized(signing_key):
    with pytest.raises(HTTPException) as exc:
        await authenticate(token(signing_key, email=None))
    assert exc.value.status_code == 401
