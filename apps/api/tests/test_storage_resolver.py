"""Storage resolver + Supabase adapter (008 task 3.3): env-gated resolution
(partial config -> None -> 503) mirroring `app.ai.providers`'s precedent, and
the adapter itself driven with a stub client (no real SDK/network)."""

import asyncio

import pytest

from app.config import Settings
from app.storage.errors import StorageUnavailableError
from app.storage.providers import _resolve_cached, resolve_storage
from app.storage.providers.supabase_storage import SupabaseStorage


def _settings(
    *,
    storage_project_url: str = "",
    storage_service_key: str = "",
    storage_bucket: str = "",
) -> Settings:
    return Settings(
        _env_file=None,
        storage_project_url=storage_project_url,
        storage_service_key=storage_service_key,
        storage_bucket=storage_bucket,
    )


def test_resolver_returns_none_when_fully_unconfigured() -> None:
    _resolve_cached.cache_clear()
    assert resolve_storage(_settings()) is None


def test_resolver_returns_none_on_partial_configuration() -> None:
    _resolve_cached.cache_clear()
    assert resolve_storage(_settings(storage_project_url="https://proj.supabase.co")) is None
    _resolve_cached.cache_clear()
    assert resolve_storage(_settings(storage_service_key="key")) is None
    _resolve_cached.cache_clear()
    assert resolve_storage(_settings(storage_bucket="visuals")) is None


def test_resolver_builds_adapter_only_with_full_configuration(monkeypatch) -> None:
    _resolve_cached.cache_clear()
    # No real SDK/network: injecting a client bypasses create_client entirely,
    # so the resolver's own "full config" branch is exercised without going
    # through the lazy `from supabase import create_client` import.
    monkeypatch.setattr(
        "app.storage.providers.supabase_storage.SupabaseStorage.__init__",
        lambda self, *, project_url, service_key, bucket, client=None: setattr(
            self, "_bucket", bucket
        ),
    )
    adapter = resolve_storage(
        _settings(
            storage_project_url="https://proj.supabase.co",
            storage_service_key="service-key",
            storage_bucket="visuals",
        )
    )
    assert adapter is not None
    _resolve_cached.cache_clear()


class _StubBucket:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, bytes, dict]] = []
        self.removed: list[list[str]] = []
        self.signed_calls: list[tuple[str, int]] = []
        self.fail_upload = False
        self.fail_sign = False

    def upload(self, path: str, content: bytes, options: dict) -> None:
        if self.fail_upload:
            raise RuntimeError("boom")
        self.uploaded.append((path, content, options))

    def create_signed_url(self, path: str, ttl_seconds: int) -> dict:
        if self.fail_sign:
            raise RuntimeError("boom")
        self.signed_calls.append((path, ttl_seconds))
        return {"signedURL": f"https://signed.example/{path}?ttl={ttl_seconds}"}

    def remove(self, paths: list[str]) -> None:
        self.removed.append(paths)


class _StubStorageNamespace:
    def __init__(self, bucket: _StubBucket) -> None:
        self._bucket = bucket

    def from_(self, name: str) -> _StubBucket:
        return self._bucket


class _StubSupabaseClient:
    def __init__(self, bucket: _StubBucket) -> None:
        self.storage = _StubStorageNamespace(bucket)


def _adapter(bucket: _StubBucket) -> SupabaseStorage:
    return SupabaseStorage(
        project_url="https://proj.supabase.co",
        service_key="key",
        bucket="visuals",
        client=_StubSupabaseClient(bucket),
    )


def test_supabase_storage_put_object_calls_the_bucket_client() -> None:
    bucket = _StubBucket()
    adapter = _adapter(bucket)
    asyncio.run(adapter.put_object(path="p1", content=b"abc", content_type="image/png"))
    assert bucket.uploaded == [("p1", b"abc", {"content-type": "image/png", "upsert": "false"})]


def test_supabase_storage_signed_url_returns_the_signed_url_field() -> None:
    bucket = _StubBucket()
    adapter = _adapter(bucket)
    url = asyncio.run(adapter.signed_url(path="p1", ttl_seconds=120))
    assert url == "https://signed.example/p1?ttl=120"
    assert bucket.signed_calls == [("p1", 120)]


def test_supabase_storage_remove_object_calls_the_bucket_client() -> None:
    bucket = _StubBucket()
    adapter = _adapter(bucket)
    asyncio.run(adapter.remove_object(path="p1"))
    assert bucket.removed == [["p1"]]


def test_supabase_storage_put_object_failure_raises_storage_unavailable() -> None:
    bucket = _StubBucket()
    bucket.fail_upload = True
    adapter = _adapter(bucket)
    with pytest.raises(StorageUnavailableError):
        asyncio.run(adapter.put_object(path="p1", content=b"abc", content_type="image/png"))


def test_supabase_storage_signed_url_failure_raises_storage_unavailable() -> None:
    bucket = _StubBucket()
    bucket.fail_sign = True
    adapter = _adapter(bucket)
    with pytest.raises(StorageUnavailableError):
        asyncio.run(adapter.signed_url(path="p1", ttl_seconds=120))
