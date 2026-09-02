from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.razorpay.gateway import (
    RazorpayGateway,
    RazorpayTransientError,
    RazorpayUnknownOutcomeError,
)
from app.models import (
    AttributionSource,
    AuditEvent,
    Customer,
    ExecutionMode,
    ExternalEntityMapping,
    ExternalExecution,
    ExternalExecutionState,
    ExternalOutcome,
    ExternalOutcomeStatus,
    ExternalWebhookEvent,
    FailureEvent,
    Merchant,
    Payment,
    PaymentAttempt,
    PaymentLinkStatus,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryCaseStatus,
    Subscription,
    WebhookProcessingStatus,
)
from app.models.entities import utc_now
from app.models.razorpay import ProviderConfirmationStatus
from app.services.audit import add_audit_event
from app.services.razorpay_context import record_safe_v2_decision

logger = structlog.get_logger()

_SUPPORTED_EVENTS = frozenset(
    {
        "subscription.pending",
        "subscription.charged",
        "payment.failed",
        "payment_link.paid",
        "payment_link.partially_paid",
        "payment_link.expired",
        "payment_link.cancelled",
    }
)

_SAFE_FIELDS: dict[str, frozenset[str]] = {
    "subscription": frozenset(
        {
            "id",
            "customer_id",
            "status",
            "paid_count",
            "remaining_count",
            "total_count",
            "current_start",
            "current_end",
            "charge_at",
            "created_at",
        }
    ),
    "payment": frozenset(
        {
            "id",
            "amount",
            "currency",
            "status",
            "method",
            "issuer",
            "error_code",
            "error_reason",
            "error_source",
            "error_step",
            "subscription_id",
            "invoice_id",
            "order_id",
            "created_at",
        }
    ),
    "payment_link": frozenset(
        {
            "id",
            "amount",
            "amount_paid",
            "currency",
            "status",
            "reference_id",
            "created_at",
            "updated_at",
            "expired_at",
            "cancelled_at",
            "accept_partial",
            "notes",
        }
    ),
}


def sanitize_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Retain only fields needed for Test Mode normalization and reconciliation."""

    safe: dict[str, Any] = {
        "entity": str(payload.get("entity", "")),
        "event": str(payload.get("event", "")),
        "created_at": payload.get("created_at"),
        "account_id": str(payload.get("account_id", "")),
        "payload": {},
        "storage_mode": "RAZORPAY_TEST_REDACTED",
    }
    source_payload = payload.get("payload", {})
    if not isinstance(source_payload, dict):
        return safe
    safe_payload = cast(dict[str, Any], safe["payload"])
    for entity_type, allowed_fields in _SAFE_FIELDS.items():
        wrapper = source_payload.get(entity_type)
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("entity"), dict):
            continue
        source_entity = cast(dict[str, Any], wrapper["entity"])
        safe_entity = {key: value for key, value in source_entity.items() if key in allowed_fields}
        if entity_type == "payment_link" and isinstance(safe_entity.get("notes"), dict):
            safe_entity["notes"] = {
                str(key): str(value)
                for key, value in cast(dict[str, Any], safe_entity["notes"]).items()
                if str(key).startswith("recoveriq_")
            }
        safe_payload[entity_type] = {"entity": safe_entity}
    return safe


def persist_webhook_event(
    session: Session,
    *,
    provider_event_id: str,
    raw_body: bytes,
    payload: dict[str, Any],
) -> tuple[ExternalWebhookEvent, bool]:
    existing = session.scalar(
        select(ExternalWebhookEvent).where(
            ExternalWebhookEvent.provider_event_id == provider_event_id
        )
    )
    if existing is not None:
        return existing, True

    redacted = sanitize_webhook_payload(payload)
    event = ExternalWebhookEvent(
        provider_event_id=provider_event_id,
        event_type=str(payload.get("event", "unknown")),
        provider_created_at=_provider_datetime(payload.get("created_at")),
        payload_sha256=hashlib.sha256(raw_body).hexdigest(),
        external_entity_ids=_external_entity_ids(redacted),
        redacted_payload=redacted,
    )
    session.add(event)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raced = session.scalar(
            select(ExternalWebhookEvent).where(
                ExternalWebhookEvent.provider_event_id == provider_event_id
            )
        )
        if raced is None:
            raise
        return raced, True
    add_audit_event(
        session,
        correlation_id=event.correlation_id,
        entity_type="ExternalWebhookEvent",
        entity_id=event.id,
        actor="RAZORPAY_WEBHOOK",
        event_type="WEBHOOK_RECEIVED",
        metadata={"event_type": event.event_type, "execution_mode": "RAZORPAY_TEST"},
    )
    add_audit_event(
        session,
        correlation_id=event.correlation_id,
        entity_type="ExternalWebhookEvent",
        entity_id=event.id,
        actor="RAZORPAY_WEBHOOK",
        event_type="WEBHOOK_SIGNATURE_VALIDATED",
        metadata={"method": "HMAC_SHA256_RAW_BODY"},
    )
    session.commit()
    logger.info("razorpay_webhooks_received", event_type=event.event_type)
    return event, False


def process_webhook_event(
    session: Session, event_id: uuid.UUID, gateway: RazorpayGateway | None = None
) -> None:
    event = session.get(ExternalWebhookEvent, event_id)
    if event is None:
        raise LookupError("external webhook event not found")
    if event.processing_status in {
        WebhookProcessingStatus.PROCESSED,
        WebhookProcessingStatus.IGNORED,
    }:
        return
    event.processing_status = WebhookProcessingStatus.PROCESSING
    session.commit()
    try:
        if event.event_type not in _SUPPORTED_EVENTS:
            _mark_ignored(session, event, "UNKNOWN_EVENT")
        elif event.event_type in {"subscription.pending", "payment.failed"}:
            _process_failure_event(session, event)
        elif event.event_type == "subscription.charged":
            _process_subscription_charged(session, event)
        else:
            _process_payment_link_event(session, event, gateway)
        if event.processing_status is WebhookProcessingStatus.PROCESSING:
            event.processing_status = WebhookProcessingStatus.PROCESSED
        event.processed_at = utc_now()
        session.commit()
        logger.info("razorpay_webhook_processed", event_type=event.event_type)
    except Exception as exc:
        session.rollback()
        failed = session.get(ExternalWebhookEvent, event_id)
        if failed is not None:
            failed.processing_status = WebhookProcessingStatus.FAILED
            failed.failure_reason = type(exc).__name__
            failed.processed_at = utc_now()
            session.commit()
        logger.exception("razorpay_webhook_processing_failed", event_type=event.event_type)
        raise


def _process_failure_event(session: Session, event: ExternalWebhookEvent) -> None:
    envelope = event.redacted_payload
    subscription_entity = _entity(envelope, "subscription")
    payment_entity = _entity(envelope, "payment")
    subscription_external_id = str(
        subscription_entity.get("id") or payment_entity.get("subscription_id") or ""
    )
    if not subscription_external_id:
        _process_payment_link_failure(session, event, payment_entity)
        return

    mapping = _mapping(session, "subscription", subscription_external_id)
    if mapping is not None and _is_stale(event.provider_created_at, mapping.last_provider_event_at):
        _mark_ignored(session, event, "STALE_SUBSCRIPTION_EVENT")
        return

    account_id = str(envelope.get("account_id") or "test-account-unavailable")
    merchant = _get_or_create_merchant(session, account_id)
    customer_external_id = str(
        subscription_entity.get("customer_id")
        or payment_entity.get("customer_id")
        or f"anonymous:{subscription_external_id}"
    )
    customer = _get_or_create_customer(session, merchant, customer_external_id)
    subscription = _get_or_create_subscription(
        session, merchant, customer, subscription_external_id
    )

    recovered_case = _latest_case_for_subscription(
        session, subscription.id, statuses={RecoveryCaseStatus.RECOVERED}
    )
    if recovered_case is not None and (
        event.provider_created_at is None
        or mapping is None
        or _is_stale(event.provider_created_at, mapping.last_provider_event_at)
    ):
        _mark_ignored(session, event, "PENDING_AFTER_RECOVERY")
        return

    subscription.status = "pending"
    _upsert_mapping(
        session,
        entity_type="subscription",
        external_id=subscription_external_id,
        local_entity_type="Subscription",
        local_entity_id=subscription.id,
        correlation_id=event.correlation_id,
        event_at=event.provider_created_at,
    )
    payment_external_id = str(payment_entity.get("id") or f"event:{event.provider_event_id}")
    try:
        amount_minor = int(payment_entity.get("amount", 0))
    except (TypeError, ValueError):
        amount_minor = 0
    currency = str(payment_entity.get("currency") or "INR").upper()
    if amount_minor <= 0 or len(currency) != 3:
        _mark_ignored(session, event, "INVALID_OR_MISSING_AMOUNT")
        return
    payment = _get_or_create_payment(
        session,
        merchant=merchant,
        customer=customer,
        subscription=subscription,
        external_id=payment_external_id,
        amount_minor=amount_minor,
        currency=currency,
        status="failed",
    )
    attempt = _get_or_create_attempt(session, payment, payment_entity)
    recovery_case = session.scalar(
        select(RecoveryCase).where(RecoveryCase.payment_id == payment.id)
    )
    case_created = recovery_case is None
    if recovery_case is None:
        recovery_case = RecoveryCase(
            payment_id=payment.id,
            status=RecoveryCaseStatus.DETECTED,
            correlation_id=event.correlation_id,
        )
        session.add(recovery_case)
        session.flush()
    if recovery_case.status is RecoveryCaseStatus.RECOVERED:
        _mark_ignored(session, event, "RECOVERED_CASE_IS_TERMINAL")
        return
    existing_failure = session.scalar(
        select(FailureEvent).where(FailureEvent.webhook_event_id == event.id)
    )
    if existing_failure is None:
        session.add(
            FailureEvent(
                recovery_case_id=recovery_case.id,
                webhook_event_id=event.id,
                reason=str(payment_entity.get("error_reason") or "unknown"),
                source=str(payment_entity.get("error_source") or "unknown"),
                step=str(payment_entity.get("error_step") or "unknown"),
                observed_at=event.provider_created_at or event.received_at,
            )
        )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryCase",
        entity_id=recovery_case.id,
        actor="RAZORPAY_NORMALIZER",
        event_type="EXTERNAL_ENTITY_NORMALIZED",
        metadata={
            "event_type": event.event_type,
            "case_created": case_created,
            "failure_reason": attempt.failure_code or "unknown",
        },
    )
    if case_created:
        add_audit_event(
            session,
            correlation_id=recovery_case.correlation_id,
            entity_type="RecoveryCase",
            entity_id=recovery_case.id,
            actor="RECOVERY_SERVICE",
            event_type="RECOVERY_CASE_CREATED",
            metadata={"execution_mode": "RAZORPAY_TEST"},
        )
    record_safe_v2_decision(
        session,
        recovery_case=recovery_case,
        payment=payment,
        attempt=attempt,
        subscription=subscription,
        event=event,
    )


def _process_payment_link_failure(
    session: Session,
    event: ExternalWebhookEvent,
    payment_entity: dict[str, Any],
) -> None:
    order_external_id = str(payment_entity.get("order_id") or "")
    if not order_external_id:
        _mark_ignored(session, event, "MISSING_SUBSCRIPTION_AND_ORDER_ID")
        return
    mapping = _mapping(session, "order", order_external_id)
    if mapping is None:
        _mark_ignored(session, event, "UNMATCHED_PAYMENT_ORDER")
        return
    if mapping.local_entity_type != "ExternalExecution":
        _mark_ignored(session, event, "BROKEN_PAYMENT_ORDER_MAPPING")
        return
    execution = session.get(ExternalExecution, mapping.local_entity_id)
    if execution is None:
        _mark_ignored(session, event, "EXTERNAL_EXECUTION_MISSING")
        return
    if (
        execution.provider != "RAZORPAY"
        or execution.execution_mode is not ExecutionMode.RAZORPAY_TEST
        or execution.action != "CREATE_PAYMENT_LINK"
    ):
        _mark_ignored(session, event, "INVALID_PAYMENT_ORDER_EXECUTION")
        return
    recovery_case = session.get(RecoveryCase, execution.recovery_case_id)
    if recovery_case is None:
        _mark_ignored(session, event, "RECOVERY_CASE_MISSING")
        return
    _correlate_event(session, event, recovery_case)
    if recovery_case.status is not RecoveryCaseStatus.EXECUTING:
        _mark_ignored(session, event, "RECOVERY_CASE_NOT_EXECUTING")
        return
    amount_minor = _safe_int(payment_entity.get("amount"))
    currency = str(payment_entity.get("currency") or "").upper()
    if amount_minor != execution.amount_minor:
        _mark_ignored(session, event, "PAYMENT_FAILURE_AMOUNT_MISMATCH")
        return
    if currency != execution.currency:
        _mark_ignored(session, event, "PAYMENT_FAILURE_CURRENCY_MISMATCH")
        return
    payment = session.get(Payment, recovery_case.payment_id)
    if payment is None:
        _mark_ignored(session, event, "RECOVERY_PAYMENT_MISSING")
        return
    attempt_external_id = str(payment_entity.get("id") or event.provider_event_id)
    attempt = _get_or_create_attempt(
        session,
        payment,
        payment_entity,
        external_payment_id=attempt_external_id,
    )
    existing_failure = session.scalar(
        select(FailureEvent).where(FailureEvent.webhook_event_id == event.id)
    )
    if existing_failure is None:
        session.add(
            FailureEvent(
                recovery_case_id=recovery_case.id,
                webhook_event_id=event.id,
                reason=str(payment_entity.get("error_reason") or "unknown"),
                source=str(payment_entity.get("error_source") or "unknown"),
                step=str(payment_entity.get("error_step") or "unknown"),
                observed_at=event.provider_created_at or event.received_at,
            )
        )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="ExternalExecution",
        entity_id=execution.id,
        actor="RAZORPAY_WEBHOOK_PROCESSOR",
        event_type="RECOVERY_PAYMENT_ATTEMPT_FAILED",
        metadata={
            "amount_minor": execution.amount_minor,
            "currency": execution.currency,
            "failure_reason": attempt.failure_code or "unknown",
            "payment_method": attempt.payment_method or "unknown",
            "case_status": recovery_case.status.value,
            "execution_mode": execution.execution_mode.value,
        },
    )


def _process_subscription_charged(session: Session, event: ExternalWebhookEvent) -> None:
    envelope = event.redacted_payload
    subscription_entity = _entity(envelope, "subscription")
    payment_entity = _entity(envelope, "payment")
    subscription_external_id = str(subscription_entity.get("id") or "")
    if not subscription_external_id:
        _mark_ignored(session, event, "MISSING_SUBSCRIPTION_ID")
        return
    mapping = _mapping(session, "subscription", subscription_external_id)
    if mapping is not None and _is_stale(event.provider_created_at, mapping.last_provider_event_at):
        _mark_ignored(session, event, "STALE_SUBSCRIPTION_EVENT")
        return
    if mapping is None:
        account_id = str(envelope.get("account_id") or "test-account-unavailable")
        merchant = _get_or_create_merchant(session, account_id)
        customer = _get_or_create_customer(
            session,
            merchant,
            str(subscription_entity.get("customer_id") or f"anonymous:{subscription_external_id}"),
        )
        subscription = _get_or_create_subscription(
            session, merchant, customer, subscription_external_id
        )
    else:
        mapped_subscription = session.get(Subscription, mapping.local_entity_id)
        if mapped_subscription is None:
            _mark_ignored(session, event, "BROKEN_SUBSCRIPTION_MAPPING")
            return
        subscription = mapped_subscription
    subscription.status = "active"
    _upsert_mapping(
        session,
        entity_type="subscription",
        external_id=subscription_external_id,
        local_entity_type="Subscription",
        local_entity_id=subscription.id,
        correlation_id=event.correlation_id,
        event_at=event.provider_created_at,
    )
    recovery_case = _latest_case_for_subscription(
        session,
        subscription.id,
        statuses={
            RecoveryCaseStatus.DETECTED,
            RecoveryCaseStatus.HUMAN_REVIEW,
            RecoveryCaseStatus.EXECUTING,
            RecoveryCaseStatus.WAITING,
            RecoveryCaseStatus.FAILED,
        },
    )
    if recovery_case is None:
        return
    _correlate_event(session, event, recovery_case)
    payment = session.get(Payment, recovery_case.payment_id)
    if payment is None:
        _mark_ignored(session, event, "RECOVERY_PAYMENT_MISSING")
        return
    amount = _safe_int(payment_entity.get("amount"))
    currency = str(payment_entity.get("currency") or "INR").upper()
    if amount != payment.amount_minor or currency != payment.currency:
        _audit_outcome_rejected(session, recovery_case, event, "AMOUNT_OR_CURRENCY_MISMATCH")
        return
    external_payment_id = str(payment_entity.get("id") or "") or None
    occurred_at = event.provider_created_at or event.received_at
    outcome = _record_external_outcome(
        session,
        event=event,
        recovery_case=recovery_case,
        execution=None,
        status=ExternalOutcomeStatus.CHARGED,
        external_payment_id=external_payment_id,
        external_payment_link_id=None,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        occurred_at=occurred_at,
    )
    _attribute_recovery_once(
        session,
        recovery_case=recovery_case,
        execution=None,
        outcome=outcome,
        external_payment_id=external_payment_id,
        external_payment_link_id=None,
        occurred_at=occurred_at,
        source=AttributionSource.SUBSCRIPTION_CHARGED,
    )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryCase",
        entity_id=recovery_case.id,
        actor="RAZORPAY_WEBHOOK_PROCESSOR",
        event_type="SUBSCRIPTION_CHARGED_SATISFIED_CASE",
        metadata={"amount_minor": payment.amount_minor, "currency": payment.currency},
    )


def _process_payment_link_event(
    session: Session, event: ExternalWebhookEvent, gateway: RazorpayGateway | None
) -> None:
    link = _entity(event.redacted_payload, "payment_link")
    link_id = str(link.get("id") or "")
    reference_id = str(link.get("reference_id") or "")
    execution = None
    if link_id:
        execution = session.scalar(
            select(ExternalExecution).where(ExternalExecution.provider_entity_id == link_id)
        )
    if execution is None and reference_id:
        execution = session.scalar(
            select(ExternalExecution).where(ExternalExecution.provider_reference_id == reference_id)
        )
    if execution is None:
        _mark_ignored(session, event, "UNMATCHED_PAYMENT_LINK")
        return
    recovery_case = session.get(RecoveryCase, execution.recovery_case_id)
    if recovery_case is None:
        _mark_ignored(session, event, "RECOVERY_CASE_MISSING")
        return
    _correlate_event(session, event, recovery_case)
    if execution.provider_reference_id != reference_id:
        _audit_outcome_rejected(session, recovery_case, event, "REFERENCE_MISMATCH")
        return
    if execution.provider_entity_id not in {None, link_id}:
        _audit_outcome_rejected(session, recovery_case, event, "PAYMENT_LINK_ID_MISMATCH")
        return
    notes = link.get("notes", {})
    if isinstance(notes, dict):
        case_note = notes.get("recoveriq_case")
        correlation_note = notes.get("recoveriq_correlation")
        if case_note is not None and str(case_note) != str(recovery_case.id):
            _audit_outcome_rejected(session, recovery_case, event, "CASE_NOTE_MISMATCH")
            return
        if correlation_note is not None and str(correlation_note) != str(
            recovery_case.correlation_id
        ):
            _audit_outcome_rejected(session, recovery_case, event, "CORRELATION_NOTE_MISMATCH")
            return
    execution.provider_entity_id = link_id
    if event.event_type == "payment_link.paid":
        status = str(link.get("status") or "")
        amount = _safe_int(link.get("amount"))
        amount_paid = _safe_int(link.get("amount_paid"))
        currency = str(link.get("currency") or "").upper()
        if (
            status != "paid"
            or amount != execution.amount_minor
            or amount_paid != execution.amount_minor
            or currency != execution.currency
        ):
            _audit_outcome_rejected(session, recovery_case, event, "PAID_INVARIANT_MISMATCH")
            return
        if event.provider_confirmation_status == ProviderConfirmationStatus.NOT_REQUIRED:
            event.provider_confirmation_status = ProviderConfirmationStatus.PENDING
            event.provider_confirmation_method = "PAYMENT_LINK_FETCH"
            session.commit()

        if event.provider_confirmation_status == ProviderConfirmationStatus.PENDING:
            if gateway is None:
                raise RuntimeError(
                    "RazorpayGateway is required to process payment_link.paid events"
                )
            reconcile_payment_link_provider_truth(session, event.id, gateway)

        return
    if recovery_case.status is RecoveryCaseStatus.RECOVERED:
        _mark_ignored(session, event, "TERMINAL_RECOVERY_CASE")
        return
    if event.event_type == "payment_link.partially_paid":
        execution.payment_link_status = PaymentLinkStatus.PARTIALLY_PAID
    elif event.event_type == "payment_link.expired":
        execution.payment_link_status = PaymentLinkStatus.EXPIRED
        execution.state = ExternalExecutionState.FAILED
        execution.completed_at = event.provider_created_at or event.received_at
        recovery_case.status = RecoveryCaseStatus.FAILED
    elif event.event_type == "payment_link.cancelled":
        execution.payment_link_status = PaymentLinkStatus.CANCELLED
        execution.state = ExternalExecutionState.CANCELLED
        execution.completed_at = event.provider_created_at or event.received_at
        recovery_case.status = RecoveryCaseStatus.FAILED
    link_status = execution.payment_link_status
    if link_status is None:
        raise RuntimeError("Payment Link status transition was not resolved")
    outcome_status = {
        PaymentLinkStatus.PARTIALLY_PAID: ExternalOutcomeStatus.PARTIALLY_PAID,
        PaymentLinkStatus.EXPIRED: ExternalOutcomeStatus.EXPIRED,
        PaymentLinkStatus.CANCELLED: ExternalOutcomeStatus.CANCELLED,
    }[link_status]
    _record_external_outcome(
        session,
        event=event,
        recovery_case=recovery_case,
        execution=execution,
        status=outcome_status,
        external_payment_id=None,
        external_payment_link_id=link_id,
        amount_minor=execution.amount_minor,
        currency=execution.currency,
        occurred_at=event.provider_created_at or event.received_at,
    )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="ExternalExecution",
        entity_id=execution.id,
        actor="RAZORPAY_WEBHOOK_PROCESSOR",
        event_type="PAYMENT_LINK_STATUS_UPDATED",
        metadata={"payment_link_status": link_status.value},
    )


def _attribute_recovery_once(
    session: Session,
    *,
    recovery_case: RecoveryCase,
    execution: ExternalExecution | None,
    outcome: ExternalOutcome,
    external_payment_id: str | None,
    external_payment_link_id: str | None,
    occurred_at: datetime,
    source: AttributionSource,
) -> RecoveryAttribution:
    existing = session.scalar(
        select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == recovery_case.id)
    )
    if existing is not None:
        return existing
    payment = session.get(Payment, recovery_case.payment_id)
    if payment is None:
        raise LookupError("recovery payment missing")
    attribution = RecoveryAttribution(
        recovery_case_id=recovery_case.id,
        external_execution_id=execution.id if execution is not None else None,
        external_outcome_id=outcome.id,
        execution_mode=ExecutionMode.RAZORPAY_TEST,
        external_payment_id=external_payment_id,
        external_payment_link_id=external_payment_link_id,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        occurred_at=occurred_at,
        attribution_source=source,
    )
    session.add(attribution)
    recovery_case.status = RecoveryCaseStatus.RECOVERED
    session.flush()
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryAttribution",
        entity_id=attribution.id,
        actor="RECOVERY_ATTRIBUTION",
        event_type="RAZORPAY_TEST_RECOVERY_ATTRIBUTED",
        metadata={
            "amount_minor": attribution.amount_minor,
            "currency": attribution.currency,
            "source": attribution.attribution_source.value,
            "execution_mode": attribution.execution_mode.value,
        },
    )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryCase",
        entity_id=recovery_case.id,
        actor="RECOVERY_SERVICE",
        event_type="RECOVERY_CASE_TRANSITIONED_RECOVERED",
        metadata={"source": source.value},
    )
    logger.info("test_recovery_cases_completed", source=source.value)
    return attribution


def _record_external_outcome(
    session: Session,
    *,
    event: ExternalWebhookEvent,
    recovery_case: RecoveryCase,
    execution: ExternalExecution | None,
    status: ExternalOutcomeStatus,
    external_payment_id: str | None,
    external_payment_link_id: str | None,
    amount_minor: int,
    currency: str,
    occurred_at: datetime,
) -> ExternalOutcome:
    existing = session.scalar(
        select(ExternalOutcome).where(ExternalOutcome.webhook_event_id == event.id)
    )
    if existing is None and external_payment_id is not None:
        existing = session.scalar(
            select(ExternalOutcome).where(
                ExternalOutcome.external_payment_id == external_payment_id
            )
        )
    if existing is not None:
        return existing
    outcome = ExternalOutcome(
        recovery_case_id=recovery_case.id,
        external_execution_id=execution.id if execution is not None else None,
        webhook_event_id=event.id,
        status=status,
        verified=True,
        external_payment_id=external_payment_id,
        external_payment_link_id=external_payment_link_id,
        amount_minor=amount_minor,
        currency=currency,
        occurred_at=occurred_at,
    )
    session.add(outcome)
    session.flush()
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="ExternalOutcome",
        entity_id=outcome.id,
        actor="RAZORPAY_WEBHOOK_PROCESSOR",
        event_type="EXTERNAL_OUTCOME_VERIFIED",
        metadata={
            "status": status.value,
            "amount_minor": amount_minor,
            "currency": currency,
        },
    )
    return outcome


def _audit_outcome_rejected(
    session: Session,
    recovery_case: RecoveryCase,
    event: ExternalWebhookEvent,
    reason: str,
) -> None:
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="ExternalWebhookEvent",
        entity_id=event.id,
        actor="RECOVERY_ATTRIBUTION",
        event_type="EXTERNAL_OUTCOME_REJECTED",
        metadata={"reason": reason},
    )
    event.processing_status = WebhookProcessingStatus.IGNORED
    event.failure_reason = reason


def _correlate_event(
    session: Session, event: ExternalWebhookEvent, recovery_case: RecoveryCase
) -> None:
    if event.correlation_id == recovery_case.correlation_id:
        return
    event.correlation_id = recovery_case.correlation_id
    receipt_audits = session.scalars(
        select(AuditEvent).where(
            AuditEvent.entity_type == "ExternalWebhookEvent",
            AuditEvent.entity_id == event.id,
        )
    ).all()
    for audit in receipt_audits:
        audit.correlation_id = recovery_case.correlation_id


def _mark_ignored(session: Session, event: ExternalWebhookEvent, reason: str) -> None:
    event.processing_status = WebhookProcessingStatus.IGNORED
    event.failure_reason = reason
    add_audit_event(
        session,
        correlation_id=event.correlation_id,
        entity_type="ExternalWebhookEvent",
        entity_id=event.id,
        actor="RAZORPAY_WEBHOOK_PROCESSOR",
        event_type="WEBHOOK_IGNORED",
        metadata={"reason": reason, "event_type": event.event_type},
    )


def _get_or_create_merchant(session: Session, account_id: str) -> Merchant:
    external_id = f"razorpay:{account_id}"
    merchant = session.scalar(select(Merchant).where(Merchant.external_id == external_id))
    if merchant is None:
        merchant = Merchant(external_id=external_id, name="Razorpay Test Merchant")
        session.add(merchant)
        session.flush()
    return merchant


def _get_or_create_customer(
    session: Session, merchant: Merchant, external_customer_id: str
) -> Customer:
    external_id = f"razorpay:{external_customer_id}"
    customer = session.scalar(select(Customer).where(Customer.external_id == external_id))
    if customer is None:
        anonymous_reference = hashlib.sha256(external_id.encode()).hexdigest()[:20]
        customer = Customer(
            merchant_id=merchant.id,
            external_id=external_id,
            anonymous_reference=f"rzp-test-{anonymous_reference}",
        )
        session.add(customer)
        session.flush()
    return customer


def _get_or_create_subscription(
    session: Session,
    merchant: Merchant,
    customer: Customer,
    external_subscription_id: str,
) -> Subscription:
    external_id = f"razorpay:{external_subscription_id}"
    subscription = session.scalar(
        select(Subscription).where(Subscription.external_id == external_id)
    )
    if subscription is None:
        subscription = Subscription(
            merchant_id=merchant.id,
            customer_id=customer.id,
            external_id=external_id,
            status="pending",
        )
        session.add(subscription)
        session.flush()
    return subscription


def _get_or_create_payment(
    session: Session,
    *,
    merchant: Merchant,
    customer: Customer,
    subscription: Subscription,
    external_id: str,
    amount_minor: int,
    currency: str,
    status: str,
) -> Payment:
    provider_id = f"razorpay:{external_id}"
    payment = session.scalar(select(Payment).where(Payment.external_id == provider_id))
    if payment is None:
        payment = Payment(
            merchant_id=merchant.id,
            customer_id=customer.id,
            subscription_id=subscription.id,
            external_id=provider_id,
            amount_minor=amount_minor,
            currency=currency,
            status=status,
        )
        session.add(payment)
        session.flush()
    else:
        payment.status = status
    return payment


def _get_or_create_attempt(
    session: Session,
    payment: Payment,
    payment_entity: dict[str, Any],
    *,
    external_payment_id: str | None = None,
) -> PaymentAttempt:
    external_id = f"razorpay-attempt:{external_payment_id or payment.external_id}"
    attempt = session.scalar(
        select(PaymentAttempt).where(PaymentAttempt.external_id == external_id)
    )
    if attempt is None:
        attempt = PaymentAttempt(
            payment_id=payment.id,
            external_id=external_id,
            status="failed",
            failure_code=str(
                payment_entity.get("error_reason") or payment_entity.get("error_code") or "unknown"
            ),
            payment_method=str(payment_entity.get("method") or "unknown"),
            issuer=str(payment_entity.get("issuer") or "unknown"),
            attempted_at=_provider_datetime(payment_entity.get("created_at")) or utc_now(),
        )
        session.add(attempt)
        session.flush()
    return attempt


def _upsert_mapping(
    session: Session,
    *,
    entity_type: str,
    external_id: str,
    local_entity_type: str,
    local_entity_id: uuid.UUID,
    correlation_id: uuid.UUID,
    event_at: datetime | None,
) -> ExternalEntityMapping:
    mapping = _mapping(session, entity_type, external_id)
    if mapping is None:
        mapping = ExternalEntityMapping(
            provider="RAZORPAY",
            external_entity_type=entity_type,
            external_entity_id=external_id,
            local_entity_type=local_entity_type,
            local_entity_id=local_entity_id,
            correlation_id=correlation_id,
            last_provider_event_at=event_at,
        )
        session.add(mapping)
        session.flush()
    elif not _is_stale(event_at, mapping.last_provider_event_at):
        mapping.last_provider_event_at = event_at or mapping.last_provider_event_at
    return mapping


def _mapping(session: Session, entity_type: str, external_id: str) -> ExternalEntityMapping | None:
    return session.scalar(
        select(ExternalEntityMapping).where(
            ExternalEntityMapping.provider == "RAZORPAY",
            ExternalEntityMapping.external_entity_type == entity_type,
            ExternalEntityMapping.external_entity_id == external_id,
        )
    )


def _latest_case_for_subscription(
    session: Session,
    subscription_id: uuid.UUID,
    *,
    statuses: set[RecoveryCaseStatus],
) -> RecoveryCase | None:
    return session.scalar(
        select(RecoveryCase)
        .join(Payment, RecoveryCase.payment_id == Payment.id)
        .where(Payment.subscription_id == subscription_id, RecoveryCase.status.in_(statuses))
        .order_by(RecoveryCase.created_at.desc())
        .limit(1)
    )


def _entity(payload: dict[str, Any], entity_type: str) -> dict[str, Any]:
    nested = payload.get("payload", {})
    if not isinstance(nested, dict):
        return {}
    wrapper = nested.get(entity_type, {})
    if not isinstance(wrapper, dict):
        return {}
    entity = wrapper.get("entity", {})
    return cast(dict[str, Any], entity) if isinstance(entity, dict) else {}


def _external_entity_ids(payload: dict[str, Any]) -> dict[str, str]:
    return {
        entity_type: str(entity["id"])
        for entity_type in _SAFE_FIELDS
        if (entity := _entity(payload, entity_type)).get("id")
    }


def _provider_datetime(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    return None


def payment_link_completion_datetime(
    payload: dict[str, Any],
    *,
    fallback: datetime,
) -> datetime:
    """Resolve when a paid Payment Link completed, never when the link was created."""

    payment_link = _entity(payload, "payment_link")
    payment = _entity(payload, "payment")
    return (
        _provider_datetime(payment_link.get("updated_at"))
        or _provider_datetime(payment.get("created_at"))
        or fallback
    )


def _is_stale(candidate: datetime | None, current: datetime | None) -> bool:
    if candidate is None or current is None:
        return False
    return _as_utc(candidate) <= _as_utc(current)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def reconcile_payment_link_provider_truth(
    session: Session, event_id: uuid.UUID, gateway: RazorpayGateway
) -> None:
    event = session.get(ExternalWebhookEvent, event_id)
    if not event:
        return

    envelope = event.redacted_payload
    link = _entity(envelope, "payment_link")
    link_id = str(link.get("id") or "")
    reference_id = str(link.get("reference_id") or "")

    execution = None
    if link_id:
        execution = session.scalar(
            select(ExternalExecution).where(ExternalExecution.provider_entity_id == link_id)
        )
    if execution is None and reference_id:
        execution = session.scalar(
            select(ExternalExecution).where(ExternalExecution.provider_reference_id == reference_id)
        )
    if execution is None:
        return

    recovery_case = session.get(RecoveryCase, execution.recovery_case_id)
    if recovery_case is None:
        return

    try:
        if link_id:
            provider_link = gateway.fetch_payment_link(link_id)
        else:
            provider_link = gateway.find_payment_link_by_reference(reference_id)
    except (RazorpayTransientError, RazorpayUnknownOutcomeError):
        logger.warning("provider_fetch_transient_failure", link_id=link_id, exc_info=True)
        raise

    if not provider_link:
        event.provider_confirmation_status = ProviderConfirmationStatus.MISMATCH
        event.provider_confirmed_at = utc_now()
        session.add(event)
        _audit_outcome_rejected(session, recovery_case, event, "PROVIDER_LINK_NOT_FOUND")
        return

    if (
        provider_link.status != "paid"
        or provider_link.amount_minor != execution.amount_minor
        or provider_link.amount_paid_minor != execution.amount_minor
        or provider_link.currency != execution.currency
    ):
        event.provider_confirmation_status = ProviderConfirmationStatus.MISMATCH
        event.provider_confirmed_at = utc_now()
        session.add(event)
        _audit_outcome_rejected(session, recovery_case, event, "PROVIDER_TRUTH_MISMATCH")
        return

    event.provider_confirmation_status = ProviderConfirmationStatus.CONFIRMED
    event.provider_confirmed_at = utc_now()
    session.add(event)

    execution.provider_entity_id = provider_link.id
    execution.payment_link_status = PaymentLinkStatus.PAID

    payment_completed_at = payment_link_completion_datetime(
        event.redacted_payload, fallback=event.received_at
    )
    execution.completed_at = payment_completed_at

    payment_entity = _entity(event.redacted_payload, "payment")
    external_payment_id = str(payment_entity.get("id") or "") or None

    outcome = _record_external_outcome(
        session,
        event=event,
        recovery_case=recovery_case,
        execution=execution,
        status=ExternalOutcomeStatus.PAID,
        external_payment_id=external_payment_id,
        external_payment_link_id=provider_link.id,
        amount_minor=execution.amount_minor,
        currency=execution.currency,
        occurred_at=payment_completed_at,
    )

    _attribute_recovery_once(
        session,
        recovery_case=recovery_case,
        execution=execution,
        outcome=outcome,
        external_payment_id=external_payment_id,
        external_payment_link_id=provider_link.id,
        occurred_at=payment_completed_at,
        source=AttributionSource.PAYMENT_LINK_PAID,
    )
    logger.info("razorpay_payment_links_paid_triangulated")
