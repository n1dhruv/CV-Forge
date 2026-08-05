import asyncio
import time
from typing import Annotated
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


class JWKSCache:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get_key(self, kid: str, url: str) -> jwt.PyJWK:
        if time.monotonic() >= self._expires_at or kid not in self._keys:
            async with self._lock:
                if time.monotonic() >= self._expires_at or kid not in self._keys:
                    async with httpx.AsyncClient(timeout=5) as client:
                        response = await client.get(url)
                        response.raise_for_status()
                    self._keys = {
                        key["kid"]: jwt.PyJWK.from_dict(key)
                        for key in response.json().get("keys", [])
                    }
                    self._expires_at = time.monotonic() + self.ttl_seconds
        if kid not in self._keys:
            raise jwt.InvalidTokenError("Signing key not found")
        return self._keys[kid]


jwks_cache = JWKSCache()


def unauthorized(detail: str = "Invalid or expired authentication token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized("Bearer token is required")
    try:
        header = jwt.get_unverified_header(credentials.credentials)
        if not header.get("kid"):
            raise jwt.InvalidTokenError("Unexpected token header")
        key = await jwks_cache.get_key(header["kid"], settings.supabase_jwks_url)
        if header.get("alg") != key.algorithm_name:
            raise jwt.InvalidTokenError("Unexpected signing algorithm")
        claims = jwt.decode(
            credentials.credentials,
            key=key.key,
            algorithms=[key.algorithm_name],
            issuer=settings.supabase_auth_issuer,
            audience="authenticated",
            options={"require": ["aud", "email", "exp", "iss", "role", "sub"]},
        )
        if claims["role"] != "authenticated":
            raise jwt.InvalidTokenError("Unexpected role")
        user_id = UUID(claims["sub"])
        email = claims["email"]
        if not isinstance(email, str) or not email:
            raise jwt.InvalidTokenError("Email claim is required")
    except (httpx.HTTPError, jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized() from exc

    await session.execute(
        insert(User)
        .values(id=user_id, email=email)
        .on_conflict_do_nothing(index_elements=[User.id])
    )
    await session.commit()
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized("Authenticated user could not be initialized")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
