"""Deterministic async fake of the storage port: tests and local dev, no network.

Mirrors `app.ai.fakes`'s shape: records calls so tests can assert on them,
and models signed-URL expiry deterministically (`advance_clock`) instead of
sleeping in real time.
"""

from dataclasses import dataclass
from typing import Any

from app.storage.errors import StorageUnavailableError


@dataclass
class _StoredObject:
    content: bytes
    content_type: str


class FakeStorage:
    """In-memory `StoragePort`: upload, signed URL (simulable expiry), remove.

    `signed_url` encodes its own expiry (`fake-signed://<path>?exp=<epoch>`)
    so a test can assert expiry behavior without a real signer; `is_expired`
    decodes it against the fake's own clock.
    """

    def __init__(self) -> None:
        self._objects: dict[str, _StoredObject] = {}
        self._clock: float = 0.0
        self.put_calls: list[dict[str, Any]] = []
        self.remove_calls: list[str] = []
        self.signed_url_calls: list[dict[str, Any]] = []

    def advance_clock(self, seconds: float) -> None:
        self._clock += seconds

    async def put_object(self, *, path: str, content: bytes, content_type: str) -> None:
        self.put_calls.append({"path": path, "content_type": content_type, "size": len(content)})
        self._objects[path] = _StoredObject(content=content, content_type=content_type)

    async def signed_url(self, *, path: str, ttl_seconds: int) -> str:
        self.signed_url_calls.append({"path": path, "ttl_seconds": ttl_seconds})
        if path not in self._objects:
            raise StorageUnavailableError("signed_url")
        expires_at = self._clock + ttl_seconds
        return f"fake-signed://{path}?exp={expires_at:.0f}"

    async def remove_object(self, *, path: str) -> None:
        self.remove_calls.append(path)
        self._objects.pop(path, None)

    def is_expired(self, signed_url: str) -> bool:
        """Test helper: decode the fake's own scheme and compare against its clock."""
        try:
            exp = float(signed_url.rsplit("exp=", 1)[1])
        except (IndexError, ValueError):
            return True
        return self._clock > exp

    def object_exists(self, path: str) -> bool:
        return path in self._objects
