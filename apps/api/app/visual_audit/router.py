"""Visual Review router. No SQL here; auth dependency and membership policies
resolve access. Spans multiple resource roots per API.md (creative-items,
visual-assets, visual-audits, visual-reviews), so it carries no single prefix.

Provider adapters, storage and the tracer arrive as dependency-injected
composition roots (creative/knowledge-router pattern): `None` is the only
unconfigured-provider/storage representation. No provider or storage SDK is
imported in this file.
"""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.ports import EmbeddingModel, VisionModel
from app.ai.providers import resolve_embedding_model, resolve_vision_model
from app.config import Settings, get_settings
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user
from app.observability.langfuse_adapter import resolve_tracer
from app.observability.ports import Tracer
from app.observability.recording import RecordingTracer
from app.observability.repository import SqlTraceRecordRepository
from app.storage.ports import StoragePort
from app.storage.providers import resolve_storage
from app.visual_audit import service
from app.visual_audit.schemas import (
    ApproveIn,
    DecisionOut,
    QueueOut,
    RequestChangesIn,
    VisualAssetList,
    VisualAssetOut,
    VisualAuditHistoryOut,
    VisualAuditOut,
)

router = APIRouter(tags=["visual-audit"])


def get_storage_adapter(settings: Settings = Depends(get_settings)) -> StoragePort | None:
    """Compositional root: `None` is the only unconfigured-storage representation."""
    return resolve_storage(settings)


def get_vision_adapter(settings: Settings = Depends(get_settings)) -> VisionModel | None:
    return resolve_vision_model(settings)


def get_embedding_adapter(
    settings: Settings = Depends(get_settings),
) -> EmbeddingModel | None:
    return resolve_embedding_model(settings)


def get_tracer_adapter(settings: Settings = Depends(get_settings)) -> Tracer:
    return RecordingTracer(SqlTraceRecordRepository(), resolve_tracer(settings))


@router.get("/visual-reviews/queue", response_model=QueueOut)
async def read_visual_queue(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    storage: StoragePort | None = Depends(get_storage_adapter),
) -> QueueOut:
    return await service.queue(session, user, storage=storage, settings=settings)


@router.post(
    "/creative-items/{item_id}/visual-assets",
    response_model=VisualAssetOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_visual_asset(
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    storage: StoragePort | None = Depends(get_storage_adapter),
    tracer: Tracer = Depends(get_tracer_adapter),
) -> VisualAssetOut:
    content = await file.read()
    return await service.upload(
        session, user, item_id, content=content, storage=storage, settings=settings, tracer=tracer
    )


@router.get("/creative-items/{item_id}/visual-assets", response_model=VisualAssetList)
async def list_visual_assets(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    storage: StoragePort | None = Depends(get_storage_adapter),
) -> VisualAssetList:
    return await service.list_assets(session, user, item_id, storage=storage, settings=settings)


@router.post("/visual-assets/{asset_id}/audit", response_model=VisualAuditOut)
async def run_visual_audit(
    asset_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    vision_adapter: VisionModel | None = Depends(get_vision_adapter),
    embedding_adapter: EmbeddingModel | None = Depends(get_embedding_adapter),
    storage: StoragePort | None = Depends(get_storage_adapter),
    tracer: Tracer = Depends(get_tracer_adapter),
) -> VisualAuditOut:
    return await service.run_audit(
        session,
        user,
        asset_id,
        vision_adapter=vision_adapter,
        embedding_adapter=embedding_adapter,
        storage=storage,
        settings=settings,
        tracer=tracer,
    )


@router.get("/visual-assets/{asset_id}/audit", response_model=VisualAuditOut)
def read_latest_visual_audit(
    asset_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> VisualAuditOut:
    return service.get_latest_audit(session, user, asset_id)


@router.post("/visual-audits/{audit_id}/approve", response_model=DecisionOut)
def approve_visual_audit(
    audit_id: uuid.UUID,
    payload: ApproveIn = ApproveIn(),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DecisionOut:
    return service.approve(session, user, audit_id, payload)


@router.post("/visual-audits/{audit_id}/request-changes", response_model=DecisionOut)
def request_visual_audit_changes(
    audit_id: uuid.UUID,
    payload: RequestChangesIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DecisionOut:
    return service.request_changes(session, user, audit_id, payload)


@router.get(
    "/creative-items/{item_id}/visual-audit-history", response_model=VisualAuditHistoryOut
)
async def read_visual_audit_history(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    storage: StoragePort | None = Depends(get_storage_adapter),
) -> VisualAuditHistoryOut:
    return await service.history(session, user, item_id, storage=storage, settings=settings)
