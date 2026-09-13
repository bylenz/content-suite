"""Identity router: current user endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user
from app.identity.schemas import Me
from app.identity.service import get_me

router = APIRouter(tags=["identity"])


@router.get("/me", response_model=Me)
def read_current_me(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Me:
    return get_me(session, user)
