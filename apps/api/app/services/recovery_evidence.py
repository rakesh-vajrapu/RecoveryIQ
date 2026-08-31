from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    ExecutionMode,
    ExternalEntityMapping,
    ExternalExecution,
    Payment,
    PaymentAttempt,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryDecisionRecord,
)

DEMO_SOURCE = "DEMO_SYNTHETIC"
DEMO_EXTERNAL_ID_PREFIX = "demo_recoveriq_"
DEMO_FAILURE_AUDIT_EVENT = "DEMO_SYNTHETIC_FAILURE_RECORDED"


class RecoveryEvidenceSource(StrEnum):
    DEMO_SYNTHETIC = DEMO_SOURCE
    RAZORPAY_TEST_MODE = "RAZORPAY_TEST_MODE"
    LOCAL_UNVERIFIED = "LOCAL_UNVERIFIED"


@dataclass(frozen=True, slots=True)
class RecoveryEvidence:
    source: RecoveryEvidenceSource
    synthetic: bool
    failure_type: str
    payment_method: str
    failure_description: str | None
    decision_kind: str | None
    decision_reason: str | None
    verified_recovery_minor: int
    verified_recovery_at: datetime | None


def is_demo_payment_external_id(external_id: str | None) -> bool:
    return external_id is not None and external_id.startswith(DEMO_EXTERNAL_ID_PREFIX)


def recovery_evidence(session: Session, recovery_case: RecoveryCase) -> RecoveryEvidence:
    payment = recovery_case.payment
    attempt = session.scalar(
        select(PaymentAttempt)
        .where(PaymentAttempt.payment_id == payment.id)
        .order_by(PaymentAttempt.attempted_at.desc(), PaymentAttempt.created_at.desc())
        .limit(1)
    )
    decision = session.scalar(
        select(RecoveryDecisionRecord)
        .where(RecoveryDecisionRecord.recovery_case_id == recovery_case.id)
        .order_by(RecoveryDecisionRecord.created_at.desc())
        .limit(1)
    )
    attribution = session.scalar(
        select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == recovery_case.id)
    )
    source = _source_for_case(session, recovery_case, payment, attribution)
    description = _failure_description(session, recovery_case) if source == DEMO_SOURCE else None
    verified_minor = (
        attribution.amount_minor
        if attribution is not None
        and attribution.execution_mode is ExecutionMode.RAZORPAY_TEST
        and source is RecoveryEvidenceSource.RAZORPAY_TEST_MODE
        else 0
    )
    return RecoveryEvidence(
        source=source,
        synthetic=source is RecoveryEvidenceSource.DEMO_SYNTHETIC,
        failure_type=attempt.failure_code or "UNKNOWN" if attempt is not None else "UNKNOWN",
        payment_method=attempt.payment_method or "UNKNOWN" if attempt is not None else "UNKNOWN",
        failure_description=description,
        decision_kind=decision.kind.value if decision is not None else None,
        decision_reason=decision.reason if decision is not None else None,
        verified_recovery_minor=verified_minor,
        verified_recovery_at=(
            attribution.created_at if attribution is not None and verified_minor > 0 else None
        ),
    )


def _source_for_case(
    session: Session,
    recovery_case: RecoveryCase,
    payment: Payment,
    attribution: RecoveryAttribution | None,
) -> RecoveryEvidenceSource:
    if is_demo_payment_external_id(payment.external_id):
        return RecoveryEvidenceSource.DEMO_SYNTHETIC
    execution_id = session.scalar(
        select(ExternalExecution.id)
        .where(ExternalExecution.recovery_case_id == recovery_case.id)
        .limit(1)
    )
    mapping_id = session.scalar(
        select(ExternalEntityMapping.id)
        .where(ExternalEntityMapping.correlation_id == recovery_case.correlation_id)
        .limit(1)
    )
    if attribution is not None or execution_id is not None or mapping_id is not None:
        return RecoveryEvidenceSource.RAZORPAY_TEST_MODE
    return RecoveryEvidenceSource.LOCAL_UNVERIFIED


def _failure_description(session: Session, recovery_case: RecoveryCase) -> str | None:
    event = session.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.correlation_id == recovery_case.correlation_id,
            AuditEvent.event_type == DEMO_FAILURE_AUDIT_EVENT,
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(1)
    )
    if event is None:
        return None
    description = event.event_metadata.get("description")
    return description if isinstance(description, str) else None
