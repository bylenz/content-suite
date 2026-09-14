"""Shared test fixtures: test secret, SQLite app database and JWT helper."""

import asyncio
import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TEST_JWT_SECRET = "test-only-secret-0123456789abcdef0123456789abcdef"
TEST_JWT_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_JWT_AUDIENCE = "authenticated"
os.environ.setdefault("CONTENT_SUITE_AUTH_JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("CONTENT_SUITE_AUTH_JWT_ISSUER", TEST_JWT_ISSUER)
# Wildcard: most tests create brands for arbitrary emails and aren't exercising
# the allowlist itself -- that gets its own dedicated coverage with a narrower
# get_settings override (see test_identity_create_brand.py).
os.environ.setdefault("CONTENT_SUITE_BRAND_CREATION_ALLOWLIST", "*")

from app.db import (
    Base,  # noqa: E402
    get_session,  # noqa: E402
)
from app.identity.models import Brand, BrandMembership, BrandRole, Profile  # noqa: E402
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


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def valid_document() -> dict[str, Any]:
    """A minimal canonical Brand DNA document (design.md contract)."""
    return {
        "identity": {
            "purpose": "Make snack content that feels homemade",
            "positioning": "Healthy quinoa snacks for Gen Z",
            "personality_traits": ["Playful", "Professional"],
            "audience": "Gen Z in Peru",
        },
        "voice": {
            "tone_characteristics": ["Warm", "Energetic"],
            "usage_guide": "Speak like a friend sharing a recipe",
            "preferred_vocabulary": ["quinoa"],
            "avoid_vocabulary": ["cheap"],
            "do_examples": ["Say: bites full of real quinoa"],
            "dont_examples": ["Avoid: the cheapest snack"],
        },
        "communication": {
            "message_pillars": [{"name": "Real food", "description": "Ingredients you can name"}],
            "rules": ["Always close with a call to action"],
        },
        "visual_rules": {
            "visual_personality": "Soft clay shapes",
            "imagery_direction": "Bright daylight food photography",
            "composition": "Centered hero product",
            "logo_usage": "Top left, clear space",
        },
        "restrictions": {"rules": ["Never use pure black shadows"]},
    }


def make_workspace(
    session: Session,
    roles: tuple[BrandRole, ...] = (
        BrandRole.CREATOR,
        BrandRole.CONTENT_REVIEWER,
        BrandRole.VISUAL_REVIEWER,
    ),
) -> dict[str, Any]:
    """Seed a unique brand with one profile+token per role; returns ids and tokens."""
    suffix = uuid.uuid4().hex[:8]
    brand = Brand(id=uuid.uuid4(), name=f"Brand {suffix}", slug=f"brand-{suffix}")
    session.add(brand)
    profiles: dict[BrandRole, Profile] = {}
    tokens: dict[BrandRole, str] = {}
    for role in roles:
        profile = Profile(
            id=uuid.uuid4(),
            email=f"{role.value.lower()}-{suffix}@example.com",
            display_name=f"{role.value} {suffix}",
        )
        session.add(profile)
        session.add(
            BrandMembership(id=uuid.uuid4(), profile_id=profile.id, brand_id=brand.id, role=role)
        )
        profiles[role] = profile
        tokens[role] = make_token(sub=str(profile.id), email=profile.email)
    session.commit()
    return {"brand_id": brand.id, "profiles": profiles, "tokens": tokens}


def make_concurrency_engine(tmp_path) -> Engine:
    """File-backed SQLite with WAL + busy_timeout for genuine parallel requests."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrency.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def make_session_override(engine: Engine):
    """Build a get_session override bound to a dedicated engine (per-request sessions)."""

    def _override() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    return _override


def seed_race_workspace(engine: Engine) -> tuple[uuid.UUID, str]:
    """Seed a unique brand + CREATOR on a dedicated engine; returns (brand_id, token)."""
    suffix = uuid.uuid4().hex[:6]
    email = f"creator-{suffix}@example.com"
    with Session(engine) as seed_session:
        brand = Brand(id=uuid.uuid4(), name=f"Race {suffix}", slug=f"race-{suffix}")
        creator = Profile(id=uuid.uuid4(), email=email)
        seed_session.add_all(
            [
                brand,
                creator,
                BrandMembership(
                    id=uuid.uuid4(),
                    profile_id=creator.id,
                    brand_id=brand.id,
                    role=BrandRole.CREATOR,
                ),
            ]
        )
        seed_session.commit()
        return brand.id, make_token(sub=str(creator.id), email=email)


async def gather_asgi_requests(requests: list[dict[str, Any]]) -> list[Any]:
    """Issue concurrent HTTP requests against the app over ASGI (real threadpool)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        coroutines = [
            client.request(
                item["method"],
                item["url"],
                headers=item.get("headers"),
                json=item.get("json"),
            )
            for item in requests
        ]
        return list(await asyncio.gather(*coroutines))


def seed_synced_knowledge(session: Session, brand_id: uuid.UUID, created_by: uuid.UUID) -> Any:
    """ACTIVE Brand DNA + SYNCED knowledge via the real sync machine (spec 04 guards).

    Creative generate/check/submit require SYNCED knowledge; this helper seeds an
    active version and runs the genuine sync with the deterministic fake
    embeddings, so chunks, evidence and vector space all match FakeEmbeddingModel.
    """
    import asyncio

    from app.ai.fakes import FakeEmbeddingModel
    from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion, KnowledgeStatus
    from app.identity.auth import AuthenticatedUser
    from app.knowledge import service as knowledge_service
    from app.observability.noop import NoopTracer

    row = BrandDnaVersion(
        id=uuid.uuid4(),
        brand_id=brand_id,
        version=1,
        status=BrandDnaStatus.ACTIVE,
        document=valid_document(),
        created_by=created_by,
        knowledge_status=KnowledgeStatus.NOT_SYNCED,
    )
    session.add(row)
    session.commit()
    asyncio.run(
        knowledge_service.sync_knowledge(
            session,
            user=AuthenticatedUser(id=created_by, email=f"seed-{brand_id.hex[:8]}@example.com"),
            brand_id=brand_id,
            embedding_adapter=FakeEmbeddingModel(),
            tracer=NoopTracer(),
        )
    )
    return row
