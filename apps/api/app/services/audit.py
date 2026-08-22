from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent

_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "authorization",
        "cvv",
        "email",
        "key",
        "key_id",
        "key_secret",
        "otp",
        "pan",
        "phone",
        "secret",
        "signature",
    }
)


def add_audit_event(
    session: Session,
    *,
    correlation_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    actor: str,
    event_type: str,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    safe_metadata = metadata or {}
    _assert_safe_metadata(safe_metadata)
    event = AuditEvent(
        correlation_id=correlation_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        event_type=event_type,
        event_metadata=safe_metadata,
    )
    session.add(event)
    return event


def _assert_safe_metadata(value: Any, *, key: str | None = None) -> None:
    if key is not None and key.lower() in _FORBIDDEN_METADATA_KEYS:
        raise ValueError(f"sensitive audit metadata key rejected: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            _assert_safe_metadata(child, key=str(child_key))
    elif isinstance(value, list):
        for child in value:
            _assert_safe_metadata(child)
