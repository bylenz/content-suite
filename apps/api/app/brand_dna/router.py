"""Brand DNA router. No SQL here; auth dependency and membership policies resolve access."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.brand_dna import service
from app.brand_dna.schemas import (
    BrandDnaOverview,
    BrandDnaVersionList,
    BrandDnaVersionOut,
    DraftUpdateIn,
    PublishIn,
)
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/brands/{brand_id}/brand-dna", tags=["brand-dna"])


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
