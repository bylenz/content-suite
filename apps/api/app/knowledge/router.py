"""Knowledge router. No SQL here; auth dependency and membership policies
resolve access (membership-first: 403 before any brand resource lookup)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.ports import EmbeddingModel
from app.ai.providers import resolve_embedding_model
from app.config import Settings, get_settings
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user
from app.knowledge import service
from app.knowledge.schemas import KnowledgeChunksOut, KnowledgeStatusOut
from app.observability.langfuse_adapter import resolve_tracer
from app.observability.ports import Tracer
from app.observability.recording import RecordingTracer
from app.observability.repository import SqlTraceRecordRepository

router = APIRouter(prefix="/brands/{brand_id}/brand-knowledge", tags=["brand-knowledge"])


def get_embedding_adapter(
    settings: Settings = Depends(get_settings),
) -> EmbeddingModel | None:
    """Compositional root: `None` is the only unconfigured-provider representation."""
    return resolve_embedding_model(settings)


def get_tracer_adapter(settings: Settings = Depends(get_settings)) -> Tracer:
    # Composition root (change 009): the resolved tracer is wrapped with the
    # local read-model sink; the wrapper records entity-bound spans only and
    # delegates emission to the inner (no-op or Langfuse) tracer unchanged.
    return RecordingTracer(SqlTraceRecordRepository(), resolve_tracer(settings))


@router.get("", response_model=KnowledgeChunksOut)
def read_brand_knowledge(
    brand_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> KnowledgeChunksOut:
    return service.get_knowledge(session, user, brand_id)


@router.get("/status", response_model=KnowledgeStatusOut)
def read_brand_knowledge_status(
    brand_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> KnowledgeStatusOut:
    return service.get_status(session, user, brand_id)


@router.post("/sync", response_model=KnowledgeStatusOut)
async def sync_brand_knowledge(
    brand_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    embedding_adapter: EmbeddingModel | None = Depends(get_embedding_adapter),
    tracer: Tracer = Depends(get_tracer_adapter),
) -> KnowledgeStatusOut:
    return await service.sync_knowledge(
        session,
        user=user,
        brand_id=brand_id,
        embedding_adapter=embedding_adapter,
        tracer=tracer,
    )
