"""Application settings, read from environment variables (and an optional .env file)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me"  # noqa: S105 (rejected in production)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Nashik Water Quality API"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Database. Plain postgres:// URLs from Supabase/Neon/Render are accepted and normalised.
    database_url: str = "postgresql+psycopg://water:water@localhost:5432/water"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Comma-separated list of allowed front-end origins.
    cors_origins: str = "http://localhost:5173"

    # Auth
    jwt_secret: SecretStr = SecretStr(DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    # Bootstrap values. Used once, on first start, then managed from the admin panel.
    ingest_api_key: SecretStr | None = None
    admin_email: str | None = None
    admin_password: SecretStr | None = None

    # Rate limits (slowapi syntax)
    rate_limit_enabled: bool = True
    rate_limit_public: str = "60/minute"
    rate_limit_ingest: str = "600/minute"
    rate_limit_login: str = "10/minute"

    # Domain behaviour
    stale_after_minutes: int = 15
    alert_dedup_minutes: int = 30
    retention_days: int = 90
    # Hourly roll-up + pruning runs inside the API process (Render's free tier has no cron).
    retention_task_enabled: bool = True
    retention_interval_minutes: int = 60
    # Largest batch the Pi may flush in one request.
    ingest_batch_max: int = 1000

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.environment != "production":
            return self
        secret = self.jwt_secret.get_secret_value()
        if secret == DEV_JWT_SECRET or len(secret) < 32:
            raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters")
        if self.ingest_api_key and len(self.ingest_api_key.get_secret_value()) < 24:
            raise ValueError("INGEST_API_KEY must be at least 24 characters in production")
        if self.admin_password and len(self.admin_password.get_secret_value()) < 12:
            raise ValueError("ADMIN_PASSWORD must be at least 12 characters in production")
        if "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must list explicit origins in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
