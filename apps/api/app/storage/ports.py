"""Storage port (design D1): domain-agnostic private object storage.

Pure infrastructure port with no visual/creative semantics: `put_object`,
`signed_url`, `remove_object`. Every operation is async (mirrors
`app.ai.ports`) so adapters can wrap a blocking SDK (e.g. via
`asyncio.to_thread`) without leaking that detail to callers. This module
MUST NOT import `app.visual_audit` or `app.creative` (D1): consumers depend
on `storage`, never the other way around.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class StoragePort(Protocol):
    """Private object storage: upload, short-lived signed read URL, remove.

    `path` is always computed server-side by the caller (never client input);
    this port stores/serves bytes at the given path, it does not validate or
    interpret it.
    """

    async def put_object(self, *, path: str, content: bytes, content_type: str) -> None: ...

    async def signed_url(self, *, path: str, ttl_seconds: int) -> str: ...

    async def remove_object(self, *, path: str) -> None: ...
