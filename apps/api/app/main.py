"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.health.router import router as health_router
from app.identity.router import router as identity_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Content Suite API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(identity_router, prefix="/api/v1")
    return app


app = create_app()
