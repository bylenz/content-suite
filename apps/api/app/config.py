"""Application settings loaded from environment (prefix CONTENT_SUITE_)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTENT_SUITE_", env_file=".env", extra="ignore")

    # Canonical target is Supabase PostgreSQL (psycopg); SQLite is only for local dev and tests.
    database_url: str = "sqlite:///./content_suite_dev.db"
    # Supabase-compatible HS256 JWT secret. Empty disables token verification (auth returns 503).
    auth_jwt_secret: str = ""
    auth_jwt_algorithm: Literal["HS256"] = "HS256"
    # Expected JWT claims; access tokens must match issuer and audience and carry exp/sub.
    # Supabase issuer shape: https://<project-ref>.supabase.co/auth/v1
    auth_jwt_issuer: str = ""
    auth_jwt_audience: str = "authenticated"
    # Browser origins allowed to call the API. Plain comma-separated list (same
    # `NoDecode` parsing as the allowlist below). The single entry "*" allows any
    # origin: safe here because auth is a bearer header, never cookies, so CORS
    # credentials are disabled in that mode (see `main.create_app`).
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # Emails allowed to self-serve create a brand (POST /brands), matched
    # case-insensitively. Empty means nobody may -- consistent with this app's
    # "unconfigured -> refuses to operate" convention (see vision/storage below)
    # rather than silently allowing anyone with a valid token. The single entry
    # "*" disables the check entirely (local dev convenience). `NoDecode` +
    # the validator below let the env var be a plain comma-separated string
    # (a@x.com,b@x.com) instead of forcing JSON-array syntax.
    brand_creation_allowlist: Annotated[list[str], NoDecode] = []

    @field_validator("cors_origins", "brand_creation_allowlist", mode="before")
    @classmethod
    def _parse_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [entry.strip() for entry in value.split(",") if entry.strip()]
        return value

    # AI platform (empty defaults: the app starts fully unconfigured; resolution of
    # adapters/tracers treats empty as "not configured", never as an error).
    ai_provider: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    # OpenAI embeddings (production provider). Empty/0 defaults keep the app
    # starting unconfigured; the resolver treats them as "not configured".
    openai_api_key: str = ""
    openai_embedding_model: str = ""
    openai_embedding_dimensions: int = 0
    openai_text_model: str = ""
    # Vision provider (change 008 follow-up): independent of `ai_provider`
    # since text/embeddings stay on OpenAI while Vision has no OpenAI adapter
    # in this codebase -- only GLM (Zhipu/Z.ai) is implemented so far.
    vision_provider: str = ""
    glm_api_key: str = ""
    glm_base_url: str = ""
    glm_vision_model: str = ""
    # Private storage (change 008): empty defaults keep storage unconfigured; the
    # resolver treats partial configuration the same as absent (503, no fallback).
    storage_project_url: str = ""
    storage_service_key: str = ""
    storage_bucket: str = ""
    storage_signed_url_ttl_seconds: int = 300
    storage_max_upload_bytes: int = 5 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
