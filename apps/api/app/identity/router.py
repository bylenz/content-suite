"""Identity router: current user + self-serve workspace creation."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user
from app.identity.schemas import BrandCreateIn, Me, MembershipOut
from app.identity.service import create_brand, get_me

router = APIRouter(tags=["identity"])


@router.get("/me", response_model=Me)
def read_current_me(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Me:
    return get_me(session, user)


@router.post("/brands", response_model=MembershipOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: BrandCreateIn,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MembershipOut:
    return create_brand(session, user, payload, settings)
