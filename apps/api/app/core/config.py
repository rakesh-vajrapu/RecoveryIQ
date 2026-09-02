from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    enable_demo_seed: bool = False

    execution_environment: Literal["SIMULATION", "RAZORPAY_TEST"] = "SIMULATION"
    razorpay_mode: Literal["test"] = "test"
    razorpay_test_smoke_enabled: bool = False
    razorpay_key_id: SecretStr | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None

    explanation_provider: Literal["fallback", "groq"] = "fallback"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    groq_max_retries: int = Field(default=2, ge=0, le=10)

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator(
        "razorpay_key_id",
        "razorpay_key_secret",
        "razorpay_webhook_secret",
        "groq_api_key",
        mode="before",
    )
    @classmethod
    def empty_secret_is_unconfigured(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def require_test_mode_razorpay_credentials(self) -> Settings:
        """Make Live Mode impossible even if a live key is supplied accidentally."""

        if self.razorpay_key_id is not None:
            key_id = self.razorpay_key_id.get_secret_value()
            if not key_id.startswith("rzp_test_"):
                raise ValueError("only rzp_test_ Razorpay credentials are supported")
        return self

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

    @property
    def razorpay_api_configured(self) -> bool:
        return self.razorpay_key_id is not None and self.razorpay_key_secret is not None

    @property
    def razorpay_webhook_configured(self) -> bool:
        return self.razorpay_webhook_secret is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
