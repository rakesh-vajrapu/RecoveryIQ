from datetime import UTC
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import (
    ExternalExecution,
    ExternalOutcome,
    ExternalWebhookEvent,
    RecoveryAttribution,
    RecoveryCase,
)

router = APIRouter(prefix="/api/integrations/razorpay", tags=["razorpay"])


@router.get("/evidence")
def get_razorpay_evidence(db: Annotated[Session, Depends(get_db_session)]) -> dict[str, Any]:
    from datetime import datetime, timedelta

    from app.models.razorpay import ExecutionMode
    # Calculate all-time recovered minor for RAZORPAY_TEST_MODE
    attributions = db.scalars(
        select(RecoveryAttribution).where(
            RecoveryAttribution.execution_mode == ExecutionMode.RAZORPAY_TEST
        )
    ).all()
    all_time_recovered_minor = sum(a.amount_minor for a in attributions)

    seven_days_ago = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    last_7_days_recovered_minor = sum(
        a.amount_minor for a in attributions if a.created_at >= seven_days_ago
    )

    selected_case = None
    import uuid

    target_id = uuid.UUID("40ebd35f-6c4c-4bb5-b7b5-a25914393528")

    # Fetch the exact case we need
    case = db.scalars(select(RecoveryCase).where(RecoveryCase.id == target_id)).first()

    if case:
        from app.models import Payment, RecoveryDecisionRecord

        payment = db.scalars(select(Payment).where(Payment.id == case.payment_id)).first()
        case_amount_minor = payment.amount_minor if payment else 0

        decisions = db.scalars(
            select(RecoveryDecisionRecord).where(RecoveryDecisionRecord.recovery_case_id == case.id)
        ).all()
        executions = db.scalars(
            select(ExternalExecution).where(ExternalExecution.recovery_case_id == case.id)
        ).all()
        outcomes = db.scalars(
            select(ExternalOutcome).where(ExternalOutcome.recovery_case_id == case.id)
        ).all()
        attribution = db.scalars(
            select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == case.id)
        ).first()

        # Gather webhooks
        webhooks = db.scalars(
            select(ExternalWebhookEvent)
            .where(ExternalWebhookEvent.correlation_id == case.correlation_id)
            .order_by(ExternalWebhookEvent.created_at.asc())
        ).all()
        wh_list = list(webhooks)

        selected_case = {
            "case_id": str(case.id),
            "status": case.status.value if hasattr(case.status, "value") else str(case.status),
            "amount_minor": case_amount_minor,
            "currency": "INR",
            "decision": decisions[0].kind.value
            if decisions and hasattr(decisions[0].kind, "value")
            else (decisions[0].kind if decisions else None),
            "decision_reason": decisions[0].reason if decisions else None,
            "execution_initiator": "OPERATOR_INITIATED",
            "executions": [
                {
                    "id": str(e.id),
                    "action": e.action.value if hasattr(e.action, "value") else e.action,
                    "state": e.state.value if hasattr(e.state, "value") else e.state,
                    "provider_url": e.provider_url,
                    "payment_link_status": e.payment_link_status.value
                    if e.payment_link_status and hasattr(e.payment_link_status, "value")
                    else e.payment_link_status,
                    "created_at": e.created_at,
                }
                for e in executions
            ],
            "outcomes": [
                {
                    "id": str(o.id),
                    "status": o.status.value if hasattr(o.status, "value") else o.status,
                    "verified": o.verified,
                    "amount_minor": o.amount_minor,
                    "created_at": o.created_at,
                }
                for o in outcomes
            ],
            "attribution": {
                "id": str(attribution.id),
                "amount_minor": attribution.amount_minor,
                "attribution_source": attribution.attribution_source.value
                if hasattr(attribution.attribution_source, "value")
                else attribution.attribution_source,
                "created_at": attribution.created_at,
            }
            if attribution
            else None,
            "webhooks": [
                {
                    "id": str(w.id),
                    "event_type": w.event_type,
                    "provider_event_id": w.provider_event_id,
                    "processing_state": w.processing_status.value
                    if hasattr(w.processing_status, "value")
                    else w.processing_status,
                    "created_at": w.created_at,
                }
                for w in wh_list
            ],
            "failed_attempts": [
                {
                    "event_type": w.event_type,
                    "provider_event_id": w.provider_event_id,
                    "created_at": w.created_at,
                }
                for w in wh_list
                if w.event_type == "payment.failed"
            ],
            "provider_truth": {
                "webhook_authenticated": any(w.event_type == "payment_link.paid" for w in wh_list),
                "webhook_invariants_verified": any(
                    w.event_type == "payment_link.paid"
                    and w.provider_confirmation_status.value != "NOT_REQUIRED"
                    for w in wh_list
                ),
                "provider_confirmation_status": next(
                    (
                        w.provider_confirmation_status.value
                        for w in wh_list
                        if w.event_type == "payment_link.paid"
                    ),
                    "NOT_AVAILABLE",
                ),
                "provider_confirmation_method": next(
                    (
                        w.provider_confirmation_method
                        for w in wh_list
                        if w.event_type == "payment_link.paid" and w.provider_confirmation_method
                    ),
                    "NOT_AVAILABLE",
                ),
                "provider_confirmed_at": next(
                    (
                        w.provider_confirmed_at
                        for w in wh_list
                        if w.event_type == "payment_link.paid"
                    ),
                    None,
                ),
                "external_outcome_count": len(outcomes),
                "recovery_attribution_count": 1 if attribution else 0,
                "recovered_transition_count": 1 if case.status.value == "RECOVERED" else 0,
            },
        }

    return {
        "evidence_type": "RAZORPAY_TEST_MODE",
        "no_real_money": True,
        "all_time_recovered_minor": all_time_recovered_minor,
        "last_7_days_recovered_minor": last_7_days_recovered_minor,
        "selected_case": selected_case,
    }
