from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables and an optional local .env."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    database_url: str = "sqlite:///./recoveriq.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = True

    razorpay_key_id: SecretStr | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None

    gemini_enabled: bool = False
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.7-flash"
    gemini_api_version: str = "v1"
    gemini_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    gemini_max_retries: int = Field(default=3, ge=0, le=10)
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def database_kind(self) -> Literal["sqlite", "postgresql", "other"]:
        if self.database_url.startswith("sqlite"):
            return "sqlite"
        if self.database_url.startswith("postgresql"):
            return "postgresql"
        return "other"

    @property
    def celery_broker_url(self) -> str:
        return "memory://" if self.celery_task_always_eager else self.redis_url

    @property
    def celery_result_backend(self) -> str:
        return "cache+memory://" if self.celery_task_always_eager else self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
