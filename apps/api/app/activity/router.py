"""Recent Activity feed router (change 014). No SQL here; auth dependency and
the membership-first service resolve everything (same shape as `app.observability`)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.activity import service
from app.activity.schemas import ActivityListResponse
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=ActivityListResponse)
def read_activity(
    brand_id: uuid.UUID = Query(...),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ActivityListResponse:
    return service.list_activity(session, user, brand_id, limit=limit, offset=offset)
