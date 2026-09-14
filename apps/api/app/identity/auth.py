"""Authentication boundary: verifies Supabase-issued bearer tokens.

Two verification modes, picked from the token's own (unverified) `alg`
header:
- HS256: verified against the static `auth_jwt_secret` shared secret. This is
  only reachable by tokens *we* mint (`scripts/dev_tokens.py`, and tests via
  `tests/conftest.py`) -- real Supabase-issued tokens never use it once a
  project has JWT Signing Keys enabled (the current default: Supabase signs
  with an asymmetric key, e.g. ES256, not the legacy shared secret).
- Anything else (ES256/RS256/...): verified against Supabase's own JWKS
  (`<issuer>/.well-known/jwks.json`), matched by the token's `kid`. This is
  the path real logins (password or magic link) take.

Tokens must match the configured issuer/audience and carry the required
``exp``/``sub`` claims; anything else is rejected. Roles and memberships are
never taken from the client; only the verified identity (sub/email) leaves
this module.
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    email: str | None


@lru_cache
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    # Cached per issuer (fixed per deployment): reuses PyJWT's own JWKS cache
    # (5 min lifespan) instead of refetching on every request.
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", cache_keys=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    if not settings.auth_jwt_issuer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth is not configured"
        )
    token = credentials.credentials
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
        if algorithm == "HS256":
            if not settings.auth_jwt_secret:
                raise _unauthorized("Invalid token")
            key: str | jwt.PyJWK = settings.auth_jwt_secret
        else:
            key = _jwks_client(settings.auth_jwt_issuer).get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            key,
            algorithms=[algorithm] if algorithm else [],
            audience=settings.auth_jwt_audience,
            issuer=settings.auth_jwt_issuer,
            options={"require": ["exp", "sub"]},
        )
    except HTTPException:
        raise
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
