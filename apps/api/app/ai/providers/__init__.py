"""Provider adapters and their resolution from settings.

This package is the only location in `app/` allowed to import AI provider SDKs
(AI_SYSTEM.md). Resolution mirrors the tracer Langfuse precedent: absent or
partial configuration yields `None` — the only representation of an
unconfigured provider — with a single sanitized log naming the missing setting
NAMES, never their values.
"""

import logging
from functools import cache

from app.ai.ports import EmbeddingModel, TextModel, VisionModel
from app.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TEXT_MODEL = "gpt-4o-mini"
DEFAULT_GLM_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
DEFAULT_GLM_VISION_MODEL = "glm-5.3-flash"


def resolve_embedding_model(settings: Settings) -> EmbeddingModel | None:
    """Resolve the embedding adapter from settings (compositional root).

    Cached per configuration state, mirroring `resolve_tracer`: each distinct
    state logs its single state line and builds the client at most once.
    """
    return _resolve_cached(
        settings.ai_provider,
        settings.openai_api_key,
        settings.openai_embedding_model,
        settings.openai_embedding_dimensions,
    )


@cache
def _resolve_cached(
    ai_provider: str, openai_api_key: str, openai_embedding_model: str, dimensions: int
) -> EmbeddingModel | None:
    if not ai_provider and not openai_api_key:
        logger.info("Embedding provider disabled: no configuration present")
        return None
    missing: list[str] = []
    if ai_provider != "openai":
        # Unsupported/unknown provider or provider selected without key: partial.
        missing.append("CONTENT_SUITE_AI_PROVIDER=openai")
    if not openai_api_key:
        missing.append("CONTENT_SUITE_OPENAI_API_KEY")
    model = openai_embedding_model or DEFAULT_EMBEDDING_MODEL
    from app.ai.providers.openai_embeddings import (
        DOCUMENTED_DIMENSIONS,
        supports_custom_dimensions,
    )

    known_dimension = DOCUMENTED_DIMENSIONS.get(model)
    if dimensions <= 0:
        if known_dimension is None:
            # Unknown model without an explicit dimension: dimension unknowable
            # without a network call, which the port forbids -> partial config.
            missing.append("CONTENT_SUITE_OPENAI_EMBEDDING_DIMENSIONS")
            dimensions = 0
        else:
            dimensions = known_dimension
    elif (
        known_dimension is not None
        and not supports_custom_dimensions(model)
        and dimensions != known_dimension
    ):
        # Fixed-dimension models (ada-002) only accept their documented dimension.
        # text-embedding-3-* instead accepts any explicitly configured positive
        # (typically reduced) dimension via the provider `dimensions` parameter.
        missing.append("CONTENT_SUITE_OPENAI_EMBEDDING_DIMENSIONS")
    if missing:
        logger.warning("Embedding provider disabled: missing settings %s", ", ".join(missing))
        return None
    from app.ai.providers.openai_embeddings import OpenAIEmbeddingModel

    return OpenAIEmbeddingModel(api_key=openai_api_key, model=model, dimensions=dimensions)


def resolve_text_model(settings: Settings) -> TextModel | None:
    """Resolve the text adapter from settings (compositional root, embeddings twin).

    Same states as embeddings: absent config -> None (info), partial config ->
    None (warning naming the missing setting NAMES), complete -> adapter.
    """
    return _resolve_text_cached(
        settings.ai_provider, settings.openai_api_key, settings.openai_text_model
    )


@cache
def _resolve_text_cached(
    ai_provider: str, openai_api_key: str, openai_text_model: str
) -> TextModel | None:
    if not ai_provider and not openai_api_key:
        logger.info("Text provider disabled: no configuration present")
        return None
    missing: list[str] = []
    if ai_provider != "openai":
        missing.append("CONTENT_SUITE_AI_PROVIDER=openai")
    if not openai_api_key:
        missing.append("CONTENT_SUITE_OPENAI_API_KEY")
    if missing:
        logger.warning("Text provider disabled: missing settings %s", ", ".join(missing))
        return None
    from app.ai.providers.openai_text import OpenAITextModel

    return OpenAITextModel(
        api_key=openai_api_key, model=openai_text_model or DEFAULT_TEXT_MODEL
    )


def resolve_vision_model(settings: Settings) -> VisionModel | None:
    """Resolve the Vision adapter from settings (compositional root).

    Independent of `ai_provider`/`resolve_text_model`: text and embeddings
    stay on OpenAI, Vision has no OpenAI adapter in this codebase, only GLM
    (Zhipu/Z.ai, `CONTENT_SUITE_VISION_PROVIDER=glm`). Same states as the
    other resolvers: absent config -> None (info), partial config -> None
    (warning naming the missing setting NAMES), complete -> adapter. Tests
    inject `app.ai.fakes.FakeVisionModel` via dependency override instead of
    going through this resolver.
    """
    return _resolve_vision_cached(
        settings.vision_provider,
        settings.glm_api_key,
        settings.glm_base_url,
        settings.glm_vision_model,
    )


@cache
def _resolve_vision_cached(
    vision_provider: str, glm_api_key: str, glm_base_url: str, glm_vision_model: str
) -> VisionModel | None:
    if not vision_provider and not glm_api_key:
        logger.info("Vision provider disabled: no configuration present")
        return None
    missing: list[str] = []
    if vision_provider != "glm":
        missing.append("CONTENT_SUITE_VISION_PROVIDER=glm")
    if not glm_api_key:
        missing.append("CONTENT_SUITE_GLM_API_KEY")
    if missing:
        logger.warning("Vision provider disabled: missing settings %s", ", ".join(missing))
        return None
    from app.ai.providers.glm_vision import GLMVisionModel

    return GLMVisionModel(
        api_key=glm_api_key,
        base_url=glm_base_url or DEFAULT_GLM_BASE_URL,
        model=glm_vision_model or DEFAULT_GLM_VISION_MODEL,
    )
