from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.razorpay.capabilities import resolve_capability
from app.integrations.razorpay.gateway import (
    PaymentLinkRequest,
    PaymentLinkResult,
    RazorpayGateway,
    RazorpayGatewayError,
    RazorpayPermanentError,
    RazorpayUnknownOutcomeError,
)
from app.models import (
    ExecutionInitiator,
    ExecutionMode,
    ExternalEntityMapping,
    ExternalExecution,
    ExternalExecutionState,
    Payment,
    PaymentLinkStatus,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryDecisionRecord,
    RecoveryExecutionPlan,
)
from app.models.entities import utc_now
from app.services.audit import add_audit_event

logger = structlog.get_logger()


class OperatorExecutionError(RuntimeError):
    pass


def create_operator_test_payment_link(
    session: Session,
    *,
    recovery_case_id: uuid.UUID,
    settings: Settings,
    gateway: RazorpayGateway,
) -> ExternalExecution:
    if settings.execution_environment != "RAZORPAY_TEST" or settings.razorpay_mode != "test":
        raise OperatorExecutionError("operator Test Payment Link requires RAZORPAY_TEST")
    if not settings.razorpay_api_configured:
        raise OperatorExecutionError("Razorpay Test Mode API credentials are not configured")
    recovery_case = session.get(RecoveryCase, recovery_case_id)
    if recovery_case is None:
        raise LookupError("recovery case not found")
    if recovery_case.status is RecoveryCaseStatus.RECOVERED:
        raise OperatorExecutionError("recovered case cannot create another Payment Link")
    existing = session.scalar(
        select(ExternalExecution).where(
            ExternalExecution.recovery_case_id == recovery_case.id,
            ExternalExecution.action == "CREATE_PAYMENT_LINK",
        )
    )
    if existing is not None:
        if existing.state is ExternalExecutionState.UNKNOWN:
            return reconcile_unknown_execution(session, execution=existing, gateway=gateway)
        return existing
    payment = session.get(Payment, recovery_case.payment_id)
    if payment is None:
        raise LookupError("recovery payment not found")
    if payment.currency != "INR":
        raise OperatorExecutionError("Phase 7 Test Payment Links support INR only")

    decision = session.scalar(
        select(RecoveryDecisionRecord)
        .where(RecoveryDecisionRecord.recovery_case_id == recovery_case.id)
        .order_by(RecoveryDecisionRecord.created_at.desc())
        .limit(1)
    )
    plan = RecoveryExecutionPlan(
        recovery_case_id=recovery_case.id,
        recovery_decision_id=decision.id if decision is not None else None,
        action="CREATE_PAYMENT_LINK",
        capability=resolve_capability("CREATE_PAYMENT_LINK"),
        initiator=ExecutionInitiator.OPERATOR_INITIATED,
        rationale="Explicit operator-approved Test Mode recovery fallback",
    )
    session.add(plan)
    session.flush()
    reference_id = _reference_id(recovery_case.id)
    execution = ExternalExecution(
        recovery_case_id=recovery_case.id,
        execution_plan_id=plan.id,
        execution_mode=ExecutionMode.RAZORPAY_TEST,
        action="CREATE_PAYMENT_LINK",
        state=ExternalExecutionState.PLANNED,
        idempotency_key=f"razorpay-test:payment-link:{recovery_case.id}",
        provider_reference_id=reference_id,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
    )
    session.add(execution)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raced = session.scalar(
            select(ExternalExecution).where(
                ExternalExecution.idempotency_key
                == f"razorpay-test:payment-link:{recovery_case.id}"
            )
        )
        if raced is None:
            raise
        return raced
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryExecutionPlan",
        entity_id=plan.id,
        actor="OPERATOR",
        event_type="OPERATOR_APPROVED_EXECUTION_FALLBACK",
        metadata={
            "action": plan.action,
            "capability": plan.capability.value,
            "initiator": plan.initiator.value,
        },
    )
    session.commit()

    execution.state = ExternalExecutionState.EXECUTING
    execution.requested_at = utc_now()
    recovery_case.status = RecoveryCaseStatus.EXECUTING
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="ExternalExecution",
        entity_id=execution.id,
        actor="RAZORPAY_EXECUTOR",
        event_type="PAYMENT_LINK_CREATE_REQUESTED",
        metadata={
            "amount_minor": execution.amount_minor,
            "currency": execution.currency,
            "execution_mode": execution.execution_mode.value,
        },
    )
    session.commit()
    logger.info("razorpay_api_requests", operation="create_payment_link")
    request = PaymentLinkRequest(
        amount_minor=execution.amount_minor,
        currency=execution.currency,
        reference_id=execution.provider_reference_id,
        description="RecoverIQ Test Mode outstanding subscription payment",
        notes={
            "recoveriq_case": str(recovery_case.id),
            "recoveriq_correlation": str(recovery_case.correlation_id),
            "recoveriq_mode": "test",
            "recoveriq_initiator": "operator",
        },
    )
    try:
        result = gateway.create_payment_link(request)
    except RazorpayPermanentError as exc:
        execution.state = ExternalExecutionState.FAILED
        execution.failure_category = exc.category
        execution.failure_reason = str(exc)
        recovery_case.status = RecoveryCaseStatus.FAILED
        _audit_execution_failure(session, recovery_case, execution)
        session.commit()
        logger.warning("razorpay_api_failures", category=exc.category)
        return execution
    except (RazorpayUnknownOutcomeError, RazorpayGatewayError) as exc:
        execution.state = ExternalExecutionState.UNKNOWN
        execution.failure_category = exc.category
        execution.failure_reason = str(exc)
        add_audit_event(
            session,
            correlation_id=recovery_case.correlation_id,
            entity_type="ExternalExecution",
            entity_id=execution.id,
            actor="RAZORPAY_EXECUTOR",
            event_type="PAYMENT_LINK_CREATE_OUTCOME_UNKNOWN",
            metadata={"failure_category": exc.category},
        )
        session.commit()
        logger.warning("razorpay_api_failures", category=exc.category)
        return reconcile_unknown_execution(session, execution=execution, gateway=gateway)
    if not _result_matches_execution(result, execution):
        execution.state = ExternalExecutionState.UNKNOWN
        execution.failure_category = "RESPONSE_MISMATCH"
        execution.failure_reason = "Provider response did not match the persisted request"
        session.commit()
        return execution
    return _apply_payment_link_result(session, recovery_case, execution, result)


def reconcile_unknown_execution(
    session: Session,
    *,
    execution: ExternalExecution,
    gateway: RazorpayGateway,
) -> ExternalExecution:
    if execution.state is not ExternalExecutionState.UNKNOWN:
        return execution
    recovery_case = session.get(RecoveryCase, execution.recovery_case_id)
    if recovery_case is None:
        raise LookupError("recovery case not found during reconciliation")
    try:
        result = (
            gateway.fetch_payment_link(execution.provider_entity_id)
            if execution.provider_entity_id
            else gateway.find_payment_link_by_reference(execution.provider_reference_id)
        )
    except RazorpayGatewayError as exc:
        execution.failure_category = "RECONCILIATION_PENDING"
        execution.failure_reason = f"Reconciliation did not resolve outcome: {exc.category}"
        session.commit()
        return execution
    if result is None:
        # A list lookup can be eventually consistent. Absence is recorded but does not
        # authorize another create side effect.
        execution.failure_category = "RECONCILIATION_NOT_FOUND"
        execution.failure_reason = "No matching Payment Link observed; replacement remains blocked"
        session.commit()
        return execution
    if not _result_matches_execution(result, execution):
        execution.failure_category = "RECONCILIATION_MISMATCH"
        execution.failure_reason = "Reconciled Payment Link did not match persisted request"
        session.commit()
        return execution
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="ExternalExecution",
        entity_id=execution.id,
        actor="RAZORPAY_RECONCILER",
        event_type="UNKNOWN_EXECUTION_RECONCILED",
        metadata={"result": "FOUND_BY_REFERENCE"},
    )
    return _apply_payment_link_result(session, recovery_case, execution, result)


def _apply_payment_link_result(
    session: Session,
    recovery_case: RecoveryCase,
    execution: ExternalExecution,
    result: PaymentLinkResult,
) -> ExternalExecution:
    execution.provider_entity_id = result.id
    execution.provider_url = result.short_url
    execution.state = ExternalExecutionState.SUCCEEDED
    execution.payment_link_status = _payment_link_status(result.status)
    execution.failure_category = None
    execution.failure_reason = None
    mapping = session.scalar(
        select(ExternalEntityMapping).where(
            ExternalEntityMapping.provider == "RAZORPAY",
            ExternalEntityMapping.external_entity_type == "payment_link",
            ExternalEntityMapping.external_entity_id == result.id,
        )
    )
    if mapping is None:
        session.add(
            ExternalEntityMapping(
                provider="RAZORPAY",
                external_entity_type="payment_link",
                external_entity_id=result.id,
                local_entity_type="ExternalExecution",
                local_entity_id=execution.id,
                correlation_id=recovery_case.correlation_id,
            )
        )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="ExternalExecution",
        entity_id=execution.id,
        actor="RAZORPAY_EXECUTOR",
        event_type="PAYMENT_LINK_RETURNED",
        metadata={
            "payment_link_status": execution.payment_link_status.value,
            "reference_verified": True,
            "amount_verified": True,
        },
    )
    session.commit()
    logger.info("razorpay_payment_links_created")
    return execution


def _audit_execution_failure(
    session: Session,
    recovery_case: RecoveryCase,
    execution: ExternalExecution,
) -> None:
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="ExternalExecution",
        entity_id=execution.id,
        actor="RAZORPAY_EXECUTOR",
        event_type="PAYMENT_LINK_CREATE_FAILED",
        metadata={"failure_category": execution.failure_category or "UNKNOWN"},
    )


def _result_matches_execution(result: PaymentLinkResult, execution: ExternalExecution) -> bool:
    return (
        result.reference_id == execution.provider_reference_id
        and result.amount_minor == execution.amount_minor
        and result.currency.upper() == execution.currency
    )


def _payment_link_status(status: str) -> PaymentLinkStatus:
    normalized = status.lower()
    statuses = {
        "created": PaymentLinkStatus.ISSUED,
        "issued": PaymentLinkStatus.ISSUED,
        "paid": PaymentLinkStatus.PAID,
        "partially_paid": PaymentLinkStatus.PARTIALLY_PAID,
        "expired": PaymentLinkStatus.EXPIRED,
        "cancelled": PaymentLinkStatus.CANCELLED,
    }
    return statuses.get(normalized, PaymentLinkStatus.ISSUED)


def _reference_id(recovery_case_id: uuid.UUID) -> str:
    reference = f"riq_{recovery_case_id.hex}"
    return reference[:40]
