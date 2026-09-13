"""Application settings loaded from environment (prefix CONTENT_SUITE_)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
