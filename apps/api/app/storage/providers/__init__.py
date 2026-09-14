"""Storage adapter resolution from settings (compositional root).

This package (plus `providers/supabase_storage.py`) is the only location in
`app/` allowed to import the Supabase Storage SDK (design D2). Resolution
mirrors `app.ai.providers`'s precedent: absent or partial configuration
yields `None` -- the only representation of an unconfigured adapter -- with a
single sanitized log naming the missing setting NAMES, never their values.
"""

import logging
from functools import cache

from app.config import Settings
from app.storage.ports import StoragePort

logger = logging.getLogger(__name__)


def resolve_storage(settings: Settings) -> StoragePort | None:
    """Resolve the storage adapter from settings (compositional root).

    Cached per configuration state, mirroring `resolve_text_model`/
    `resolve_embedding_model`: each distinct state logs its single state
    line and builds the client at most once.
    """
    return _resolve_cached(
        settings.storage_project_url, settings.storage_service_key, settings.storage_bucket
    )


@cache
def _resolve_cached(project_url: str, service_key: str, bucket: str) -> StoragePort | None:
    if not project_url and not service_key and not bucket:
        logger.info("Storage disabled: no configuration present")
        return None
    missing: list[str] = []
    if not project_url:
        missing.append("CONTENT_SUITE_STORAGE_PROJECT_URL")
    if not service_key:
        missing.append("CONTENT_SUITE_STORAGE_SERVICE_KEY")
    if not bucket:
        missing.append("CONTENT_SUITE_STORAGE_BUCKET")
    if missing:
        logger.warning("Storage disabled: missing settings %s", ", ".join(missing))
        return None
    from app.storage.providers.supabase_storage import SupabaseStorage

    return SupabaseStorage(project_url=project_url, service_key=service_key, bucket=bucket)
