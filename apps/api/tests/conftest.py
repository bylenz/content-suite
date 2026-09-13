"""Shared test fixtures: test secret, SQLite app database and JWT helper."""

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TEST_JWT_SECRET = "test-only-secret-0123456789abcdef0123456789abcdef"
TEST_JWT_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_JWT_AUDIENCE = "authenticated"
os.environ.setdefault("CONTENT_SUITE_AUTH_JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("CONTENT_SUITE_AUTH_JWT_ISSUER", TEST_JWT_ISSUER)

from app.db import (
    Base,  # noqa: E402
    get_session,  # noqa: E402
)
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
        session.rollback()


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_token(
    sub: str | None = None,
    email: str = "user@example.com",
    secret: str = TEST_JWT_SECRET,
    algorithm: str = "HS256",
    expires_in: timedelta | None = timedelta(hours=1),
    **claims: Any,
) -> str:
    """Mint a Supabase-shaped JWT. Only for tests; never hardcode demo users in domain code."""
    if sub is None:
        sub = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "iss": TEST_JWT_ISSUER,
        "aud": TEST_JWT_AUDIENCE,
        "sub": sub,
        "email": email,
        **claims,
    }
    if expires_in is not None:
        payload["exp"] = datetime.now(UTC) + expires_in
    return jwt.encode(payload, secret, algorithm=algorithm)
