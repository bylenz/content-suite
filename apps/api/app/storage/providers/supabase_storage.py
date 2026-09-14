"""Supabase Storage adapter (design D2).

The ONLY place in `app/` allowed to import the `supabase`/`storage3` SDK
(confirmed via Context7 `/supabase/supabase-py`: `create_client(url, key)`,
`storage.from_(bucket).upload(path, bytes, {"content-type": ...})`,
`.create_signed_url(path, expires_in)`, `.remove([path])`). Same boundary
shape as `app.ai.providers.openai_text.OpenAITextModel`: the SDK import is
lazy (constructor), blocking SDK calls run in `asyncio.to_thread`, and the
client is injectable so tests never need real network or credentials.
"""

import asyncio
from typing import Any

from app.storage.errors import StorageUnavailableError


class SupabaseStorage:
    """Async `StoragePort` over the blocking `supabase-py` storage client."""

    def __init__(
        self, *, project_url: str, service_key: str, bucket: str, client: Any = None
    ) -> None:
        if client is None:
            from supabase import create_client  # lazy by design: this module is the SDK boundary

            client = create_client(project_url, service_key)
        self._client = client
        self._bucket = bucket

    async def put_object(self, *, path: str, content: bytes, content_type: str) -> None:
        await asyncio.to_thread(self._put_object_blocking, path, content, content_type)

    async def signed_url(self, *, path: str, ttl_seconds: int) -> str:
        return await asyncio.to_thread(self._signed_url_blocking, path, ttl_seconds)

    async def remove_object(self, *, path: str) -> None:
        await asyncio.to_thread(self._remove_object_blocking, path)

    def _bucket_client(self) -> Any:
        return self._client.storage.from_(self._bucket)

    def _put_object_blocking(self, path: str, content: bytes, content_type: str) -> None:
        try:
            # upsert "false": every path is a fresh immutable version (D3); a
            # collision here means a version was reused, which must fail loud.
            self._bucket_client().upload(
                path, content, {"content-type": content_type, "upsert": "false"}
            )
        except Exception as exc:
            raise StorageUnavailableError("put_object", exc) from exc

    def _signed_url_blocking(self, path: str, ttl_seconds: int) -> str:
        try:
            result = self._bucket_client().create_signed_url(path, ttl_seconds)
        except Exception as exc:
            raise StorageUnavailableError("signed_url", exc) from exc
        url = (
            result.get("signedURL")
            if isinstance(result, dict)
            else getattr(result, "signedURL", None) or getattr(result, "signed_url", None)
        )
        if not url:
            raise StorageUnavailableError("signed_url")
        return url

    def _remove_object_blocking(self, path: str) -> None:
        try:
            self._bucket_client().remove([path])
        except Exception as exc:
            raise StorageUnavailableError("remove_object", exc) from exc
