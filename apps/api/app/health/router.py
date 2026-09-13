"""Health endpoints. No AI or external provider calls."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    """Process is up; no dependency checks."""
    return {"status": "live"}


@router.get("/health/ready")
def readiness(session: Session = Depends(get_session)) -> dict[str, str]:
    """Process is up and essential dependencies (database) are reachable."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable"
        ) from None
    return {"status": "ready"}
