"""Content Review router. No SQL here; auth dependency and policies resolve access."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.governance import service
from app.governance.schemas import (
    DecisionOut,
    QueueOut,
    RequestChangesIn,
    ReviewDetailOut,
    ReviewHistoryOut,
)
from app.identity.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/content-reviews", tags=["content-review"])


@router.get("/queue", response_model=QueueOut)
def read_queue(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> QueueOut:
    return service.queue(session, user)


@router.get("/{item_id}", response_model=ReviewDetailOut)
def read_review_detail(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReviewDetailOut:
    return service.detail(session, user, item_id)


@router.post("/{item_id}/approve", response_model=DecisionOut)
def approve_review(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DecisionOut:
    return service.approve(session, user, item_id)


@router.post("/{item_id}/request-changes", response_model=DecisionOut)
def request_review_changes(
    item_id: uuid.UUID,
    payload: RequestChangesIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DecisionOut:
    return service.request_changes(session, user, item_id, payload.feedback)


@router.get("/{item_id}/history", response_model=ReviewHistoryOut)
def read_review_history(
    item_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReviewHistoryOut:
    return service.history(session, user, item_id)
