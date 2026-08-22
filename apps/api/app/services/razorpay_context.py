from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.integrations.razorpay.capabilities import resolve_capability
from app.models import (
    DecisionKind,
    ExecutionInitiator,
    ExternalWebhookEvent,
    Payment,
    PaymentAttempt,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryDecisionRecord,
    RecoveryExecutionPlan,
    Subscription,
)
from app.services.audit import add_audit_event


class RazorpayContextAdaptation(BaseModel):
    """Safe readiness result for the frozen V2 feature boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_schema_version: str = "2.0"
    observable_fields: dict[str, str | int | bool | None]
    missing_requirements: tuple[str, ...]
    inference_permitted: bool


class RazorpayContextAdapter:
    """Maps provider observations without fabricating simulator-only history semantics."""

    def adapt(
        self,
        *,
        payment: Payment,
        attempt: PaymentAttempt,
        subscription: Subscription,
    ) -> RazorpayContextAdaptation:
        observable: dict[str, str | int | bool | None] = {
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "payment_method": attempt.payment_method or "unknown",
            "issuer": attempt.issuer or "unknown",
            "failure_reason": attempt.failure_code or "unknown",
            "subscription_status": subscription.status,
            "existing_payment_link": False,
        }
        # A first Test Mode webhook does not prove that RecoverIQ has complete preceding
        # customer/subscription history or that raw provider categories share the frozen
        # simulator vocabulary. Zero-filling either would fabricate Model V2 inputs.
        missing = (
            "complete_customer_payment_history",
            "complete_subscription_attempt_history",
            "frozen_v2_provider_category_mapping",
        )
        return RazorpayContextAdaptation(
            observable_fields=observable,
            missing_requirements=missing,
            inference_permitted=False,
        )


def record_safe_v2_decision(
    session: Session,
    *,
    recovery_case: RecoveryCase,
    payment: Payment,
    attempt: PaymentAttempt,
    subscription: Subscription,
    event: ExternalWebhookEvent,
) -> RecoveryDecisionRecord:
    existing = (
        session.query(RecoveryDecisionRecord)
        .filter_by(decision_key=f"{event.provider_event_id}:v2")
        .one_or_none()
    )
    if existing is not None:
        return existing

    adaptation = RazorpayContextAdapter().adapt(
        payment=payment, attempt=attempt, subscription=subscription
    )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryCase",
        entity_id=recovery_case.id,
        actor="RAZORPAY_CONTEXT_ADAPTER",
        event_type="FEATURE_CONTEXT_ADAPTED",
        metadata={
            "feature_schema_version": adaptation.feature_schema_version,
            "inference_permitted": adaptation.inference_permitted,
            "missing_requirements": list(adaptation.missing_requirements),
        },
    )
    decision = RecoveryDecisionRecord(
        recovery_case_id=recovery_case.id,
        decision_key=f"{event.provider_event_id}:v2",
        kind=DecisionKind.HUMAN_REVIEW,
        selected_action=None,
        reason="INSUFFICIENT_CONTEXT",
        model_version="2.0.0",
        policy_version="2.0.0",
        feature_schema_version=adaptation.feature_schema_version,
        context_metadata={
            "inference_permitted": False,
            "missing_requirements": list(adaptation.missing_requirements),
            "observable_fields": adaptation.observable_fields,
        },
    )
    session.add(decision)
    session.flush()
    recovery_case.status = RecoveryCaseStatus.HUMAN_REVIEW
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryDecision",
        entity_id=decision.id,
        actor="RECOVERY_MODEL_V2_BOUNDARY",
        event_type="MODEL_V2_INFERENCE_REVIEWED",
        metadata={"reason": decision.reason, "model_version": decision.model_version},
    )
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryDecision",
        entity_id=decision.id,
        actor="SEQUENTIAL_POLICY_V2",
        event_type="POLICY_V2_DECISION_RECORDED",
        metadata={"kind": decision.kind.value, "reason": decision.reason},
    )
    plan = RecoveryExecutionPlan(
        recovery_case_id=recovery_case.id,
        recovery_decision_id=decision.id,
        action="HUMAN_REVIEW",
        capability=resolve_capability("HUMAN_REVIEW"),
        initiator=ExecutionInitiator.POLICY,
        rationale="Frozen V2 inputs could not be constructed without fabrication",
    )
    session.add(plan)
    session.flush()
    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryExecutionPlan",
        entity_id=plan.id,
        actor="EXECUTION_PLANNER",
        event_type="EXECUTION_CAPABILITY_RESOLVED",
        metadata={"action": plan.action, "capability": plan.capability.value},
    )
    return decision


def public_context_metadata(value: dict[str, Any]) -> dict[str, Any]:
    """Typed marker used by API serialization and tests."""

    return value
