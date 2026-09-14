"""Observability facade API (change 009, task 5.1): RBAC/brand filters (403/404),
payload allowlist, pagination, allowlisted query params, explicit no-Langfuse
state — plus the static no-SQL-in-router audit (task 5.3). File-backed WAL
engine: repository sessions and request sessions run on separate connections."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session
from app.identity.models import Brand, BrandMembership, BrandRole
from app.main import app
from app.observability.ports import CapabilitySpan
from app.observability.repository import SqlTraceRecordRepository
from app.observability.router import get_trace_repository
from tests.conftest import (
    auth_header,
    make_concurrency_engine,
    make_session_override,
    make_workspace,
)

ALLOWLIST_KEYS = {
    "trace_id",
    "brand_id",
    "entity_type",
    "entity_id",
    "operation",
    "prompt_version",
    "model",
    "latency_ms",
    "outcome",
    "error_type",
    "created_at",
}


def span_for(brand_id: str | None, **overrides: Any) -> CapabilitySpan:
    defaults: dict[str, Any] = {
        "entity": "creative_item:1",
        "model": "fake-text-model",
        "latency_ms": 10.0,
        "operation": "creative.generate",
        "brand_id": brand_id,
        "entity_type": "creative_version",
        "entity_id": str(uuid4()),
    }
    return CapabilitySpan(**{**defaults, **overrides})


@pytest.fixture
def facade(tmp_path) -> Iterator[dict[str, Any]]:
    engine = make_concurrency_engine(tmp_path)
    repo = SqlTraceRecordRepository(session_factory=sessionmaker(bind=engine))
    with Session(engine) as seed:
        own = make_workspace(seed)
        foreign = make_workspace(seed)
        # Second brand for the same creator profile: aggregation across own brands.
        second_brand_id = uuid4()
        seed.add(Brand(id=second_brand_id, name="Second", slug=f"second-{uuid4().hex[:8]}"))
        seed.add(
            BrandMembership(
                id=uuid4(),
                profile_id=own["profiles"][BrandRole.CREATOR].id,
                brand_id=second_brand_id,
                role=BrandRole.CREATOR,
            )
        )
        seed.commit()
    brand = str(own["brand_id"])
    entity_id = str(uuid4())
    asyncio.run(
        repo.save(span_for(brand, entity_id=entity_id, entity_type="creative_version"), "t-ok")
    )
    asyncio.run(repo.save(span_for(brand, error="AIOutputValidationError"), "t-err"))
    asyncio.run(
        repo.save(
            span_for(brand, entity_type="brand_dna_version", operation="brand.architect"),
            None,
        )
    )
    asyncio.run(repo.save(span_for(str(second_brand_id)), "t-second"))
    asyncio.run(repo.save(span_for(str(foreign["brand_id"])), "t-foreign"))
    asyncio.run(repo.save(span_for(None), "t-unbound"))

    app.dependency_overrides[get_session] = make_session_override(engine)
    app.dependency_overrides[get_trace_repository] = lambda: repo
    try:
        with TestClient(app) as client:
            yield {
                "client": client,
                "token": own["tokens"][BrandRole.CREATOR],
                "brand_id": own["brand_id"],
                "foreign_brand_id": foreign["brand_id"],
                "entity_id": entity_id,
            }
    finally:
        app.dependency_overrides.clear()


def test_list_scopes_to_authorized_brands_and_exposes_state(facade) -> None:
    response = facade["client"].get("/api/v1/traces", headers=auth_header(facade["token"]))
    assert response.status_code == 200
    body = response.json()
    # Own brand (3 rows) + second own brand (t-second); foreign and unbound
    # rows are never listed.
    assert body["total"] == 4
    assert body["langfuse_configured"] is False  # explicit no-Langfuse state
    assert {item["trace_id"] for item in body["items"]} == {"t-ok", "t-err", None, "t-second"}
    for item in body["items"]:
        assert set(item) == ALLOWLIST_KEYS  # sanitized payload: exact allowlist


def test_list_with_brand_filter_and_pagination(facade) -> None:
    headers = auth_header(facade["token"])
    base = facade["client"].get(
        f"/api/v1/traces?brand_id={facade['brand_id']}", headers=headers
    )
    assert base.status_code == 200 and base.json()["total"] == 3
    one = facade["client"].get(
        f"/api/v1/traces?brand_id={facade['brand_id']}&limit=1", headers=headers
    )
    assert one.json()["total"] == 3 and len(one.json()["items"]) == 1
    next_page = facade["client"].get(
        f"/api/v1/traces?brand_id={facade['brand_id']}&limit=1&offset=1", headers=headers
    )
    assert next_page.json()["items"][0]["trace_id"] != one.json()["items"][0]["trace_id"]
    over_limit = facade["client"].get("/api/v1/traces?limit=51", headers=headers)
    assert over_limit.status_code == 422


def test_list_foreign_brand_is_forbidden(facade) -> None:
    response = facade["client"].get(
        f"/api/v1/traces?brand_id={facade['foreign_brand_id']}",
        headers=auth_header(facade["token"]),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_detail_allowlist_and_not_found_semantics(facade) -> None:
    headers = auth_header(facade["token"])
    ok = facade["client"].get("/api/v1/traces/t-ok", headers=headers)
    assert ok.status_code == 200
    assert set(ok.json()) == ALLOWLIST_KEYS
    assert ok.json()["outcome"] == "ok"
    # Foreign, unbound and missing traces are indistinguishable: 404.
    for trace_id in ("t-foreign", "t-unbound", "does-not-exist"):
        missing = facade["client"].get(f"/api/v1/traces/{trace_id}", headers=headers)
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "NOT_FOUND"


def test_unknown_query_params_are_ignored(facade) -> None:
    headers = auth_header(facade["token"])
    baseline = facade["client"].get("/api/v1/traces", headers=headers)
    noisy = facade["client"].get("/api/v1/traces?prompt=raw-secret", headers=headers)
    assert noisy.status_code == 200
    assert noisy.json()["total"] == baseline.json()["total"]


def test_entity_filters_and_validation(facade) -> None:
    headers = auth_header(facade["token"])
    filtered = facade["client"].get(
        f"/api/v1/traces?entity_type=creative_version&entity_id={facade['entity_id']}",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert [item["trace_id"] for item in filtered.json()["items"]] == ["t-ok"]
    invalid_entity = facade["client"].get(
        f"/api/v1/traces?entity_id={facade['entity_id']}", headers=headers
    )
    assert invalid_entity.status_code == 422
    assert invalid_entity.json()["error"]["code"] == "VALIDATION_ERROR"


def test_date_range_filters(facade) -> None:
    from datetime import UTC, datetime, timedelta

    headers = auth_header(facade["token"])
    now = datetime.now(UTC)
    # `Z` suffix: a literal `+00:00` would decode the `+` as a space in the query string.
    past = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    future = (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    inside = facade["client"].get(f"/api/v1/traces?from={past}&to={future}", headers=headers)
    assert inside.status_code == 200
    assert inside.json()["total"] == 4
    before = facade["client"].get(f"/api/v1/traces?to={past}", headers=headers)
    assert before.status_code == 200
    assert before.json()["total"] == 0


def test_langfuse_configured_flag_reflects_settings(facade) -> None:
    from app.config import Settings, get_settings

    configured = Settings(
        _env_file=None,
        langfuse_public_key="pk",
        langfuse_secret_key="sk",
        langfuse_host="https://lf.example.com",
    )
    facade["client"].app.dependency_overrides[get_settings] = lambda: configured
    try:
        response = facade["client"].get("/api/v1/traces", headers=auth_header(facade["token"]))
        assert response.status_code == 200
        assert response.json()["langfuse_configured"] is True
    finally:
        facade["client"].app.dependency_overrides.pop(get_settings, None)


def test_no_sql_calls_in_router_or_service() -> None:
    """Static audit (task 5.3): SQL stays in the repository, never router/service.

    SDK import boundaries (langfuse only in langfuse_adapter.py, providers only
    in ai/providers/) are enforced AST-wide by tests/test_import_audit.py.
    """
    module_root = Path(__file__).resolve().parents[1] / "app" / "observability"
    for name in ("router.py", "service.py"):
        source = (module_root / name).read_text(encoding="utf-8")
        for token in ("select(", "insert(", "update(", "delete(", "session.execute"):
            assert token not in source, f"{name} must not contain SQL: {token}"
