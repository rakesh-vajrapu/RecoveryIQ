from __future__ import annotations

from typing import TypedDict

from celery import Celery

from app.core.config import get_settings


class HealthPingResult(TypedDict):
    status: str
    service: str


settings = get_settings()

celery_app = Celery(
    "recoveriq",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_store_eager_result=True,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="recoveriq.health_ping")  # type: ignore[untyped-decorator]
def health_ping() -> HealthPingResult:
    """Harmless task used to prove worker/eager configuration."""

    return {"status": "ok", "service": "recoveriq-worker"}
