import asyncio
import json
import time
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


class JWKSCache:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get_key(self, kid: str, url: str) -> Any:
        if time.monotonic() >= self._expires_at or kid not in self._keys:
            async with self._lock:
                if time.monotonic() >= self._expires_at or kid not in self._keys:
                    async with httpx.AsyncClient(timeout=5) as client:
                        response = await client.get(url)
                        response.raise_for_status()
                    self._keys = {
                        key["kid"]: RSAAlgorithm.from_jwk(json.dumps(key))
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
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise jwt.InvalidTokenError("Unexpected token header")
        key = await jwks_cache.get_key(header["kid"], settings.clerk_jwks_url)
        claims = jwt.decode(
            credentials.credentials,
            key=key,
            algorithms=["RS256"],
            issuer=settings.effective_clerk_issuer,
            options={"require": ["exp", "iss", "sub"]},
        )
    except (httpx.HTTPError, jwt.PyJWTError, KeyError, ValueError) as exc:
        raise unauthorized() from exc
    user = await session.scalar(select(User).where(User.clerk_user_id == claims["sub"]))
    if user is None:
        raise unauthorized("Authenticated Clerk user is not synchronized locally")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
