"""Creative router. No SQL here; auth dependency and membership policies resolve access.

Provider adapters and the tracer arrive as dependency-injected composition
roots (knowledge-router pattern): `None` is the only unconfigured-provider
representation, and the tracer wraps the local read-model sink (change 009).
No provider SDK is imported in this file.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.ai.ports import EmbeddingModel, TextModel
from app.ai.providers import resolve_embedding_model, resolve_text_model
from app.config import Settings, get_settings
from app.creative import service
from app.creative.schemas import (
    AppliedContextOut,
    ItemCreateIn,
    ItemList,
    ItemOut,
    PipelineOut,
    SubmitIn,
    VersionCreateIn,
    VersionList,
    VersionOut,
)
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user
from app.observability.langfuse_adapter import resolve_tracer
from app.observability.ports import Tracer
from app.observability.recording import RecordingTracer
from app.observability.repository import SqlTraceRecordRepository

router = APIRouter(prefix="/creative-items", tags=["creative"])


def get_text_adapter(settings: Settings = Depends(get_settings)) -> TextModel | None:
    """Compositional root: `None` is the only unconfigured-provider representation."""
    return resolve_text_model(settings)


def get_embedding_adapter(
    settings: Settings = Depends(get_settings),
) -> EmbeddingModel | None:
    return resolve_embedding_model(settings)


def get_tracer_adapter(settings: Settings = Depends(get_settings)) -> Tracer:
    # Composition root (change 009 pattern): the resolved tracer is wrapped with
    # the local read-model sink; the wrapper records entity-bound spans only and
    # delegates emission to the inner (no-op or Langfuse) tracer unchanged.
    return RecordingTracer(SqlTraceRecordRepository(), resolve_tracer(settings))


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_creative_item(
    payload: ItemCreateIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ItemOut:
    return service.create_item(session, user, payload)


@router.get("", response_model=ItemList)
def list_creative_items(
    brand_id: uuid.UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ItemList:
    return service.list_items(session, user, brand_id)


@router.get("/pipeline", response_model=PipelineOut)
def read_creative_pipeline(
    brand_id: uuid.UUID = Query(...),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PipelineOut:
    # Registered before `/{item_id}` on purpose: a literal segment must be
    # matched first, or "pipeline" would be parsed as a (failing) item UUID.
    return service.pipeline(session, user, brand_id)


@router.get("/{item_id}", response_model=ItemOut)
def read_creative_item(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ItemOut:
    return service.get_item(session, user, item_id)


@router.get("/{item_id}/versions", response_model=VersionList)
def list_creative_versions(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> VersionList:
    return service.list_versions(session, user, item_id)


@router.get("/{item_id}/versions/{version_id}", response_model=VersionOut)
def read_creative_version(
    item_id: uuid.UUID,
    version_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> VersionOut:
    return service.get_version_detail(session, user, item_id, version_id)


@router.get("/{item_id}/applied-context", response_model=AppliedContextOut)
def read_applied_context(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AppliedContextOut:
    return service.applied_context(session, user, item_id)


@router.post(
    "/{item_id}/versions", response_model=VersionOut, status_code=status.HTTP_201_CREATED
)
def create_creative_version(
    item_id: uuid.UUID,
    payload: VersionCreateIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> VersionOut:
    return service.create_version(session, user, item_id, payload)


@router.post("/{item_id}/submit", response_model=ItemOut)
def submit_creative_item(
    item_id: uuid.UUID,
    payload: SubmitIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ItemOut:
    return service.submit(session, user, item_id, payload)


@router.post(
    "/{item_id}/generate", response_model=VersionOut, status_code=status.HTTP_201_CREATED
)
async def generate_creative_item(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    text_adapter: TextModel | None = Depends(get_text_adapter),
    embedding_adapter: EmbeddingModel | None = Depends(get_embedding_adapter),
    tracer: Tracer = Depends(get_tracer_adapter),
) -> VersionOut:
    return await service.generate(
        session,
        user,
        item_id,
        text_adapter=text_adapter,
        embedding_adapter=embedding_adapter,
        tracer=tracer,
    )


@router.post(
    "/{item_id}/regenerate", response_model=VersionOut, status_code=status.HTTP_201_CREATED
)
async def regenerate_creative_item(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    text_adapter: TextModel | None = Depends(get_text_adapter),
    embedding_adapter: EmbeddingModel | None = Depends(get_embedding_adapter),
    tracer: Tracer = Depends(get_tracer_adapter),
) -> VersionOut:
    return await service.generate(
        session,
        user,
        item_id,
        text_adapter=text_adapter,
        embedding_adapter=embedding_adapter,
        tracer=tracer,
        regenerate=True,
    )


@router.post("/{item_id}/consistency-check", response_model=VersionOut)
async def check_creative_consistency(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    text_adapter: TextModel | None = Depends(get_text_adapter),
    embedding_adapter: EmbeddingModel | None = Depends(get_embedding_adapter),
    tracer: Tracer = Depends(get_tracer_adapter),
) -> VersionOut:
    return await service.consistency_check(
        session,
        user,
        item_id,
        text_adapter=text_adapter,
        embedding_adapter=embedding_adapter,
        tracer=tracer,
    )
