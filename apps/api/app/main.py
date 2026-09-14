"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import errors
from app.activity.router import router as activity_router
from app.brand_dna.router import router as brand_dna_router
from app.config import get_settings
from app.creative.router import router as creative_router
from app.governance.router import router as governance_router
from app.health.router import router as health_router
from app.identity.router import router as identity_router
from app.knowledge.router import router as knowledge_router
from app.observability.router import router as observability_router


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
    app.include_router(brand_dna_router, prefix="/api/v1")
    app.include_router(knowledge_router, prefix="/api/v1")
    app.include_router(creative_router, prefix="/api/v1")
    app.include_router(governance_router, prefix="/api/v1")
    app.include_router(observability_router, prefix="/api/v1")
    app.include_router(activity_router, prefix="/api/v1")
    errors.register_handlers(app)
    return app


app = create_app()
