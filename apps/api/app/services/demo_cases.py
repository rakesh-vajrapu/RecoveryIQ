from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    AuditEvent,
    Customer,
    ExternalEntityMapping,
    ExternalExecution,
    ExternalOutcome,
    ExternalWebhookEvent,
    FailureEvent,
    Merchant,
    Payment,
    PaymentAttempt,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryDecisionRecord,
    RecoveryExecutionPlan,
    Subscription,
)
from app.services.audit import add_audit_event
from app.services.razorpay_context import record_safe_v2_demo_decision
from app.services.recovery_evidence import (
    DEMO_EXTERNAL_ID_PREFIX,
    DEMO_FAILURE_AUDIT_EVENT,
    DEMO_SOURCE,
)

_MERCHANT_EXTERNAL_ID = f"{DEMO_EXTERNAL_ID_PREFIX}merchant"


class DemoSeedDisabledError(RuntimeError):
    pass


class DemoSeedStateError(RuntimeError):
    pass


class DemoResetBlockedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DemoCaseSpec:
    external_id: str
    amount_minor: int
    payment_method: str
    failure_type: str
    failure_source: str
    description: str


@dataclass(frozen=True, slots=True)
class DemoSeedResult:
    created: int
    existing: int
    total_amount_minor: int


@dataclass(frozen=True, slots=True)
class DemoResetResult:
    removed_cases: int


DEMO_CASES: tuple[DemoCaseSpec, ...] = (
    DemoCaseSpec(
        "demo_recoveriq_002",
        1_299_900,
        "CARD",
        "ISSUER_UNAVAILABLE",
        "ISSUER",
        "Issuer is temporarily unavailable",
    ),
    DemoCaseSpec(
        "demo_recoveriq_004",
        2_750_000,
        "CARD",
        "INSTRUMENT_EXPIRED",
        "INSTRUMENT",
        "Saved card has expired",
    ),
    DemoCaseSpec(
        "demo_recoveriq_005",
        4_200_000,
        "MANDATE",
        "MANDATE_INACTIVE",
        "MANDATE",
        "Recurring payment mandate is inactive",
    ),
    DemoCaseSpec(
        "demo_recoveriq_006",
        6_850_000,
        "UPI",
        "TEMPORARY_NETWORK_ERROR",
        "NETWORK",
        "Temporary network interruption affected the attempt",
    ),
    DemoCaseSpec(
        "demo_recoveriq_008",
        12_500_000,
        "NETBANKING",
        "UNKNOWN_TRANSIENT_ERROR",
        "UNKNOWN",
        "Transient failure requires review before intervention",
    ),
)


def ensure_demo_seed_enabled(settings: Settings) -> None:
    if settings.app_env != "development":
        raise DemoSeedDisabledError("APP_ENV=development is required")
    if not settings.enable_demo_seed:
        raise DemoSeedDisabledError("ENABLE_DEMO_SEED=true is required")


def seed_demo_cases(session: Session, *, settings: Settings) -> DemoSeedResult:
    ensure_demo_seed_enabled(settings)
    merchant = _get_or_create_merchant(session)
    created = 0
    existing = 0
    for spec in DEMO_CASES:
        payment = session.scalar(select(Payment).where(Payment.external_id == spec.external_id))
        if payment is not None:
            case = session.scalar(select(RecoveryCase).where(RecoveryCase.payment_id == payment.id))
            if case is None:
                raise DemoSeedStateError(f"{spec.external_id} exists without a RecoveryCase")
            existing += 1
            continue
        _create_demo_case(session, merchant=merchant, spec=spec)
        created += 1
    session.flush()
    return DemoSeedResult(
        created=created,
        existing=existing,
        total_amount_minor=sum(spec.amount_minor for spec in DEMO_CASES),
    )


def reset_demo_cases(session: Session, *, settings: Settings) -> DemoResetResult:
    ensure_demo_seed_enabled(settings)
    payments = session.scalars(
        select(Payment).where(Payment.external_id.startswith(DEMO_EXTERNAL_ID_PREFIX))
    ).all()
    payment_ids = [payment.id for payment in payments]
    cases = (
        session.scalars(select(RecoveryCase).where(RecoveryCase.payment_id.in_(payment_ids))).all()
        if payment_ids
        else []
    )
    _assert_reset_has_no_provider_evidence(session, cases)
    case_ids = [case.id for case in cases]
    correlations = [case.correlation_id for case in cases]
    for plan in session.scalars(
        select(RecoveryExecutionPlan).where(RecoveryExecutionPlan.recovery_case_id.in_(case_ids))
    ).all():
        session.delete(plan)
    for decision in session.scalars(
        select(RecoveryDecisionRecord).where(RecoveryDecisionRecord.recovery_case_id.in_(case_ids))
    ).all():
        session.delete(decision)
    for audit in session.scalars(
        select(AuditEvent).where(AuditEvent.correlation_id.in_(correlations))
    ).all():
        session.delete(audit)
    for recovery_case in cases:
        session.delete(recovery_case)
    session.flush()
    for attempt in session.scalars(
        select(PaymentAttempt).where(PaymentAttempt.payment_id.in_(payment_ids))
    ).all():
        session.delete(attempt)
    for payment in payments:
        session.delete(payment)
    session.flush()
    for subscription in session.scalars(
        select(Subscription).where(Subscription.external_id.startswith(DEMO_EXTERNAL_ID_PREFIX))
    ).all():
        session.delete(subscription)
    session.flush()
    for customer in session.scalars(
        select(Customer).where(Customer.external_id.startswith(DEMO_EXTERNAL_ID_PREFIX))
    ).all():
        session.delete(customer)
    session.flush()
    merchant = session.scalar(select(Merchant).where(Merchant.external_id == _MERCHANT_EXTERNAL_ID))
    if merchant is not None:
        session.delete(merchant)
    session.flush()
    return DemoResetResult(removed_cases=len(cases))


def _get_or_create_merchant(session: Session) -> Merchant:
    merchant = session.scalar(select(Merchant).where(Merchant.external_id == _MERCHANT_EXTERNAL_ID))
    if merchant is not None:
        return merchant
    merchant = Merchant(external_id=_MERCHANT_EXTERNAL_ID, name="RecoverIQ Demo Merchant")
    session.add(merchant)
    session.flush()
    return merchant


def _create_demo_case(
    session: Session,
    *,
    merchant: Merchant,
    spec: DemoCaseSpec,
) -> RecoveryCase:
    suffix = spec.external_id.rsplit("_", maxsplit=1)[-1]
    customer = Customer(
        merchant_id=merchant.id,
        external_id=f"{DEMO_EXTERNAL_ID_PREFIX}customer_{suffix}",
        anonymous_reference=f"demo-customer-{suffix}",
    )
    session.add(customer)
    session.flush()
    subscription = Subscription(
        merchant_id=merchant.id,
        customer_id=customer.id,
        external_id=f"{DEMO_EXTERNAL_ID_PREFIX}subscription_{suffix}",
        status="past_due",
    )
    session.add(subscription)
    session.flush()
    payment = Payment(
        merchant_id=merchant.id,
        customer_id=customer.id,
        subscription_id=subscription.id,
        external_id=spec.external_id,
        amount_minor=spec.amount_minor,
        currency="INR",
        status="failed",
    )
    session.add(payment)
    session.flush()
    attempt = PaymentAttempt(
        payment_id=payment.id,
        external_id=f"{DEMO_EXTERNAL_ID_PREFIX}attempt_{suffix}",
        status="failed",
        failure_code=spec.failure_type,
        payment_method=spec.payment_method,
        issuer="DEMO_ISSUER",
    )
    session.add(attempt)
    session.flush()
    recovery_case = RecoveryCase(payment_id=payment.id, status=RecoveryCaseStatus.DETECTED)
    session.add(recovery_case)
    session.flush()
    metadata = {
        "source": DEMO_SOURCE,
        "synthetic": True,
        "demo_id": spec.external_id,
        "amount_minor": spec.amount_minor,
        "currency": "INR",
        "payment_method": spec.payment_method,
        "failure_type": spec.failure_type,
        "failure_source": spec.failure_source,
        "description": spec.description,
    }
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="PaymentAttempt",
        entity_id=attempt.id,
        actor="DEMO_SEED_CLI",
        event_type=DEMO_FAILURE_AUDIT_EVENT,
        metadata=metadata,
    )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryCase",
        entity_id=recovery_case.id,
        actor="DEMO_SEED_CLI",
        event_type="DEMO_SYNTHETIC_RECOVERY_CASE_CREATED",
        metadata=metadata,
    )
    record_safe_v2_demo_decision(
        session,
        recovery_case=recovery_case,
        payment=payment,
        attempt=attempt,
        subscription=subscription,
        source=DEMO_SOURCE,
    )
    return recovery_case


def _assert_reset_has_no_provider_evidence(session: Session, cases: Sequence[RecoveryCase]) -> None:
    case_ids = [case.id for case in cases]
    correlations = [case.correlation_id for case in cases]
    protected = (
        session.scalar(
            select(ExternalExecution.id)
            .where(ExternalExecution.recovery_case_id.in_(case_ids))
            .limit(1)
        ),
        session.scalar(
            select(ExternalOutcome.id)
            .where(ExternalOutcome.recovery_case_id.in_(case_ids))
            .limit(1)
        ),
        session.scalar(
            select(RecoveryAttribution.id)
            .where(RecoveryAttribution.recovery_case_id.in_(case_ids))
            .limit(1)
        ),
        session.scalar(
            select(FailureEvent.id).where(FailureEvent.recovery_case_id.in_(case_ids)).limit(1)
        ),
        session.scalar(
            select(ExternalWebhookEvent.id)
            .where(ExternalWebhookEvent.correlation_id.in_(correlations))
            .limit(1)
        ),
        session.scalar(
            select(ExternalEntityMapping.id)
            .where(ExternalEntityMapping.correlation_id.in_(correlations))
            .limit(1)
        ),
    )
    if any(value is not None for value in protected):
        raise DemoResetBlockedError("demo reset refused because provider evidence is attached")
