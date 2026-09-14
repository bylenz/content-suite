"""Mint short-lived dev JWTs for the seeded demo profiles.

Writes the ignored mapping role -> token to `apps/web/.env.development.local`
(Vite loads it only in development). Tokens are HS256 with the local dev
secret/issuer/audience and a 15-minute expiry, so the existing auth boundary
can verify them. The script never prints tokens and the mapping file is
git-ignored (root `.gitignore` covers `.env.*`).

Run from apps/api with:
    uv run python -m scripts.dev_tokens

Requires CONTENT_SUITE_AUTH_JWT_SECRET and CONTENT_SUITE_AUTH_JWT_ISSUER
(the same values the API uses, e.g. from apps/api/.env).
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt

from app.config import get_settings
from scripts.seed import (
    CONTENT_REVIEWER_PROFILE_ID,
    CREATOR_PROFILE_ID,
    VISUAL_REVIEWER_PROFILE_ID,
)

TOKEN_TTL = timedelta(minutes=15)

WEB_ENV_FILE = Path(__file__).resolve().parents[2] / "web" / ".env.development.local"

ROLE_ENTRIES: tuple[tuple[str, object, str], ...] = (
    ("CREATOR", CREATOR_PROFILE_ID, "creator@kinu.example"),
    (
        "CONTENT_REVIEWER",
        CONTENT_REVIEWER_PROFILE_ID,
        "content.reviewer@kinu.example",
    ),
    (
        "VISUAL_REVIEWER",
        VISUAL_REVIEWER_PROFILE_ID,
        "visual.reviewer@kinu.example",
    ),
)


@dataclass(frozen=True)
class MintedToken:
    role: str
    expires_at: datetime


def mint_tokens() -> list[MintedToken]:
    settings = get_settings()
    if not settings.auth_jwt_secret or not settings.auth_jwt_issuer:
        raise SystemExit(
            "Falta CONTENT_SUITE_AUTH_JWT_SECRET / CONTENT_SUITE_AUTH_JWT_ISSUER. "
            "Configura apps/api/.env antes de acuñar tokens de dev."
        )
    now = datetime.now(UTC)
    expires_at = now + TOKEN_TTL
    minted: list[MintedToken] = []
    lines: list[str] = [
        "# Generado por scripts.dev_tokens (apps/api). Ignorado por Git; NO commitear.",
        "# Tokens de vida corta para el modo demo de desarrollo. Regenerar cuando expiren.",
    ]
    for role, profile_id, email in ROLE_ENTRIES:
        token = jwt.encode(
            {
                "iss": settings.auth_jwt_issuer,
                "aud": settings.auth_jwt_audience,
                "sub": str(profile_id),
                "email": email,
                "iat": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
            },
            settings.auth_jwt_secret,
            algorithm=settings.auth_jwt_algorithm,
        )
        lines.append(f"VITE_DEV_API_TOKEN_{role}={token}")
        minted.append(MintedToken(role=role, expires_at=expires_at))
    WEB_ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return minted


def main() -> None:
    minted = mint_tokens()
    print(
        json.dumps(
            {
                "written": str(WEB_ENV_FILE),
                "roles": [m.role for m in minted],
                # Solo la expiración se reporta; el token nunca se imprime.
                "expires_at": minted[0].expires_at.isoformat(),
                "note": "Archivo ignorado por Git; los tokens expiran en 15 minutos.",
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
