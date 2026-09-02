from __future__ import annotations

import uuid

from app.celery_app import celery_app
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.integrations.razorpay.dependencies import build_razorpay_gateway
from app.services.razorpay_webhooks import process_webhook_event


@celery_app.task(  # type: ignore[untyped-decorator]
    name="recoveriq.process_razorpay_webhook",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_razorpay_webhook(event_id: str) -> None:
    """Idempotent worker boundary for a previously persisted event."""

    settings = get_settings()
    gateway = build_razorpay_gateway(settings)

    with SessionLocal() as session:
        try:
            process_webhook_event(session, uuid.UUID(event_id), gateway)
        finally:
            gateway.close()
