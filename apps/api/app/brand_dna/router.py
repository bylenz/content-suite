"""Brand DNA router. No SQL here; auth dependency and membership policies resolve access.

Provider adapter and the tracer arrive as dependency-injected composition
roots for the `generate` endpoint (creative-router pattern, change 013):
`None` is the only unconfigured-provider representation, and the tracer wraps
the local read-model sink (change 009). No provider SDK is imported here.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.ports import TextModel
from app.ai.providers import resolve_text_model
from app.brand_dna import service
from app.brand_dna.schemas import (
    BrandDnaOverview,
    BrandDnaVersionList,
    BrandDnaVersionOut,
    DraftUpdateIn,
    GenerateIn,
    PublishIn,
)
from app.config import Settings, get_settings
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user
from app.observability.langfuse_adapter import resolve_tracer
from app.observability.ports import Tracer
from app.observability.recording import RecordingTracer
from app.observability.repository import SqlTraceRecordRepository

router = APIRouter(prefix="/brands/{brand_id}/brand-dna", tags=["brand-dna"])


def get_text_adapter(settings: Settings = Depends(get_settings)) -> TextModel | None:
    """Compositional root: `None` is the only unconfigured-provider representation."""
    return resolve_text_model(settings)


def get_tracer_adapter(settings: Settings = Depends(get_settings)) -> Tracer:
    return RecordingTracer(SqlTraceRecordRepository(), resolve_tracer(settings))


@router.get("", response_model=BrandDnaOverview)
def read_brand_dna(
    brand_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandDnaOverview:
    return BrandDnaOverview(**service.get_brand_dna(session, user, brand_id))


@router.get("/versions", response_model=BrandDnaVersionList)
def list_brand_dna_versions(
    brand_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandDnaVersionList:
    return BrandDnaVersionList(versions=service.list_versions(session, user, brand_id))


@router.get("/versions/{version}", response_model=BrandDnaVersionOut)
def read_brand_dna_version(
    brand_id: uuid.UUID,
    version: int,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandDnaVersionOut:
    return service.get_version(session, user, brand_id, version)


@router.post("/generate", response_model=BrandDnaVersionOut)
async def generate_brand_dna(
    brand_id: uuid.UUID,
    payload: GenerateIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    text_adapter: TextModel | None = Depends(get_text_adapter),
    tracer: Tracer = Depends(get_tracer_adapter),
) -> BrandDnaVersionOut:
    return await service.generate(
        session,
        user,
        brand_id,
        payload.brief,
        text_adapter=text_adapter,
        tracer=tracer,
    )


@router.patch("/draft", response_model=BrandDnaVersionOut)
def update_brand_dna_draft(
    brand_id: uuid.UUID,
    payload: DraftUpdateIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandDnaVersionOut:
    return service.upsert_draft(session, user, brand_id, payload.document)


@router.post("/publish", response_model=BrandDnaVersionOut)
def publish_brand_dna(
    brand_id: uuid.UUID,
    payload: PublishIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandDnaVersionOut:
    return service.publish(session, user, brand_id, payload.expected_draft_id)
