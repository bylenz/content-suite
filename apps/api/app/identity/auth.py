"""Authentication boundary: verifies Supabase-compatible HS256 bearer tokens.

Tokens must match the configured issuer/audience and carry the required
``exp``/``sub`` claims; anything else is rejected. Roles and memberships are
never taken from the client; only the verified identity (sub/email) leaves
this module.
"""

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    email: str | None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    if not settings.auth_jwt_secret or not settings.auth_jwt_issuer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth is not configured"
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.auth_jwt_secret,
            algorithms=[settings.auth_jwt_algorithm],
            audience=settings.auth_jwt_audience,
            issuer=settings.auth_jwt_issuer,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token") from None
    try:
        user_id = uuid.UUID(str(payload.get("sub", "")))
    except ValueError:
        raise _unauthorized("Invalid token subject") from None
    return AuthenticatedUser(id=user_id, email=payload.get("email"))


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
