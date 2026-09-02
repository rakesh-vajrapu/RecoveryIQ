from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.factory import create_explanation_provider
from app.ai.schemas import DecisionExplanation
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.integrations.razorpay.capabilities import ACTION_CAPABILITIES
from app.integrations.razorpay.dependencies import get_razorpay_gateway
from app.integrations.razorpay.gateway import (
    RazorpayGateway,
    RazorpayNotConfiguredError,
)
from app.models import (
    AuditEvent,
    ExternalExecution,
    ExternalOutcome,
    ExternalWebhookEvent,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryDecisionRecord,
    RecoveryExecutionPlan,
)
from app.services.razorpay_execution import (
    OperatorExecutionError,
    create_operator_test_payment_link,
)
from app.services.razorpay_webhooks import (
    payment_link_completion_datetime,
    persist_webhook_event,
    process_webhook_event,
)
from app.services.recovery_evidence import recovery_evidence
from app.tasks.razorpay import process_razorpay_webhook

router = APIRouter()
logger = structlog.get_logger()


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RazorpayStatusResponse(ApiModel):
    integration_version: str
    execution_environment: str
    provider_mode: Literal["test"]
    api_configured: bool
    webhook_configured: bool
    live_mode_available: Literal[False]
    capabilities: dict[str, str]


class WebhookAcknowledgement(ApiModel):
    status: Literal["accepted", "duplicate"]


class DecisionResponse(ApiModel):
    id: uuid.UUID
    kind: str
    selected_action: str | None
    reason: str
    model_version: str
    policy_version: str
    feature_schema_version: str
    context_metadata: dict[str, Any]


class PlanResponse(ApiModel):
    id: uuid.UUID
    action: str
    capability: str
    initiator: str
    rationale: str


class ExecutionResponse(ApiModel):
    id: uuid.UUID
    action: str
    execution_mode: str
    state: str
    amount_minor: int
    currency: str
    payment_link_status: str | None
    provider_url: str | None
    failure_category: str | None
    failure_reason: str | None


class AttributionResponse(ApiModel):
    execution_mode: str
    amount_minor: int
    currency: str
    occurred_at: datetime
    created_at: datetime
    attribution_source: str


class OutcomeResponse(ApiModel):
    id: uuid.UUID
    status: str
    verified: bool
    amount_minor: int
    currency: str
    occurred_at: datetime
    created_at: datetime


class RecoveryCaseResponse(ApiModel):
    id: uuid.UUID
    status: str
    correlation_id: uuid.UUID
    amount_minor: int
    currency: str
    subscription_status: str
    source: str
    synthetic: bool
    failure_type: str
    payment_method: str
    failure_description: str | None
    decisions: list[DecisionResponse]
    plans: list[PlanResponse]
    executions: list[ExecutionResponse]
    outcomes: list[OutcomeResponse]
    attribution: AttributionResponse | None


class RecoveryCaseSummary(ApiModel):
    id: uuid.UUID
    status: str
    correlation_id: uuid.UUID
    amount_minor: int
    currency: str
    source: str
    synthetic: bool
    failure_type: str
    payment_method: str
    decision_kind: str | None
    decision_reason: str | None
    verified_recovery_minor: int
    verified_recovery_at: datetime | None
    created_at: datetime
    last_activity_at: datetime


class AuditResponse(ApiModel):
    id: uuid.UUID
    created_at: datetime
    actor: str
    event_type: str
    entity_type: str
    event_metadata: dict[str, Any]


@router.get(
    "/api/integrations/razorpay/status",
    response_model=RazorpayStatusResponse,
    tags=["integrations"],
)
def razorpay_status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> RazorpayStatusResponse:
    return RazorpayStatusResponse(
        integration_version="1.0.0",
        execution_environment=settings.execution_environment,
        provider_mode=settings.razorpay_mode,
        api_configured=settings.razorpay_api_configured,
        webhook_configured=settings.razorpay_webhook_configured,
        live_mode_available=False,
        capabilities={key: value.value for key, value in ACTION_CAPABILITIES.items()},
    )


@router.post(
    "/webhooks/razorpay",
    response_model=WebhookAcknowledgement,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["webhooks"],
)
async def razorpay_webhook(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    gateway: Annotated[RazorpayGateway, Depends(get_razorpay_gateway)],
) -> WebhookAcknowledgement:
    if settings.execution_environment != "RAZORPAY_TEST" or settings.razorpay_mode != "test":
        raise HTTPException(status_code=503, detail="Razorpay Test Mode ingestion is disabled")
    signature = request.headers.get("x-razorpay-signature")
    if not signature:
        logger.warning("razorpay_webhook_invalid_signature", reason="missing")
        raise HTTPException(status_code=400, detail="missing Razorpay signature")
    provider_event_id = request.headers.get("x-razorpay-event-id")
    if not provider_event_id or len(provider_event_id) > 120:
        raise HTTPException(status_code=400, detail="missing or invalid Razorpay event ID")
    raw_body = await request.body()
    if len(raw_body) > 1_048_576:
        raise HTTPException(status_code=413, detail="webhook body exceeds size limit")
    try:
        verified = gateway.verify_webhook(raw_body, signature)
    except RazorpayNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="Razorpay webhook is not configured") from exc
    if not verified:
        logger.warning("razorpay_webhook_invalid_signature", reason="mismatch")
        raise HTTPException(status_code=401, detail="invalid Razorpay signature")
    try:
        decoded = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON webhook body") from exc
    if not isinstance(decoded, dict):
        raise HTTPException(status_code=400, detail="webhook body must be a JSON object")
    event, duplicate = persist_webhook_event(
        session,
        provider_event_id=provider_event_id,
        raw_body=raw_body,
        payload=decoded,
    )
    if duplicate:
        response.status_code = status.HTTP_200_OK
        logger.info("razorpay_webhook_duplicates", event_type=event.event_type)
        return WebhookAcknowledgement(status="duplicate")
    if settings.celery_task_always_eager:
        process_webhook_event(session, event.id, gateway)
    else:
        process_razorpay_webhook.delay(str(event.id))
    return WebhookAcknowledgement(status="accepted")


@router.get(
    "/api/recovery-cases",
    response_model=list[RecoveryCaseSummary],
    tags=["recovery"],
)
def list_recovery_cases(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[RecoveryCaseSummary]:
    rows = session.scalars(
        select(RecoveryCase).order_by(RecoveryCase.created_at.desc()).limit(limit)
    ).all()
    response: list[RecoveryCaseSummary] = []
    for row in rows:
        evidence = recovery_evidence(session, row)
        response.append(
            RecoveryCaseSummary(
                id=row.id,
                status=row.status.value,
                correlation_id=row.correlation_id,
                amount_minor=row.payment.amount_minor,
                currency=row.payment.currency,
                source=evidence.source.value,
                synthetic=evidence.synthetic,
                failure_type=evidence.failure_type,
                payment_method=evidence.payment_method,
                decision_kind=evidence.decision_kind,
                decision_reason=evidence.decision_reason,
                verified_recovery_minor=evidence.verified_recovery_minor,
                verified_recovery_at=evidence.verified_recovery_at,
                created_at=row.created_at,
                last_activity_at=(
                    session.scalar(
                        select(func.max(AuditEvent.created_at)).where(
                            AuditEvent.correlation_id == row.correlation_id
                        )
                    )
                    or row.updated_at
                    or row.created_at
                ),
            )
        )
    return response


@router.get(
    "/api/recovery-cases/{recovery_case_id}",
    response_model=RecoveryCaseResponse,
    tags=["recovery"],
)
def get_recovery_case(
    recovery_case_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> RecoveryCaseResponse:
    recovery_case = session.get(RecoveryCase, recovery_case_id)
    if recovery_case is None:
        raise HTTPException(status_code=404, detail="recovery case not found")
    return _recovery_case_response(session, recovery_case)


@router.get(
    "/api/recovery-cases/{recovery_case_id}/audit",
    response_model=list[AuditResponse],
    tags=["recovery"],
)
def get_recovery_case_audit(
    recovery_case_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> list[AuditResponse]:
    recovery_case = session.get(RecoveryCase, recovery_case_id)
    if recovery_case is None:
        raise HTTPException(status_code=404, detail="recovery case not found")
    rows = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.correlation_id == recovery_case.correlation_id)
        .order_by(AuditEvent.created_at, AuditEvent.id)
    ).all()
    return [AuditResponse.model_validate(row) for row in rows]


@router.post(
    "/api/recovery-cases/{recovery_case_id}/explanation",
    response_model=DecisionExplanation,
    tags=["recovery"],
)
async def explain_recovery_case(
    recovery_case_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DecisionExplanation:
    """Explain allowlisted, already-computed evidence without granting decision authority."""

    recovery_case = session.get(RecoveryCase, recovery_case_id)
    if recovery_case is None:
        raise HTTPException(status_code=404, detail="recovery case not found")

    latest_decision = session.scalar(
        select(RecoveryDecisionRecord)
        .where(RecoveryDecisionRecord.recovery_case_id == recovery_case.id)
        .order_by(RecoveryDecisionRecord.created_at.desc())
        .limit(1)
    )
    executions = session.scalars(
        select(ExternalExecution)
        .where(ExternalExecution.recovery_case_id == recovery_case.id)
        .order_by(ExternalExecution.created_at)
    ).all()
    outcomes = session.scalars(
        select(ExternalOutcome)
        .where(ExternalOutcome.recovery_case_id == recovery_case.id)
        .order_by(ExternalOutcome.occurred_at)
    ).all()
    attribution = session.scalar(
        select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == recovery_case.id)
    )

    evidence: dict[str, Any] = {
        "case_status": recovery_case.status.value,
        "amount_minor": recovery_case.payment.amount_minor,
        "currency": recovery_case.payment.currency,
        "subscription_status": recovery_case.payment.subscription.status,
        "selected_action": latest_decision.selected_action if latest_decision else None,
        "decision_kind": latest_decision.kind.value if latest_decision else "not recorded",
        "decision_reason": latest_decision.reason if latest_decision else "not recorded",
        "model_version": latest_decision.model_version if latest_decision else "not recorded",
        "policy_version": latest_decision.policy_version if latest_decision else "not recorded",
        "execution_states": [execution.state.value for execution in executions],
        "outcome_statuses": [outcome.status.value for outcome in outcomes],
        "attribution_present": attribution is not None,
    }
    provider = create_explanation_provider(settings)
    return await provider.explain_recovery_case(evidence)


@router.post(
    "/api/recovery-cases/{recovery_case_id}/test-payment-link",
    response_model=ExecutionResponse,
    tags=["recovery"],
)
def create_test_payment_link(
    recovery_case_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    gateway: Annotated[RazorpayGateway, Depends(get_razorpay_gateway)],
) -> ExecutionResponse:
    try:
        execution = create_operator_test_payment_link(
            session,
            recovery_case_id=recovery_case_id,
            settings=settings,
            gateway=gateway,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OperatorExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExecutionResponse.model_validate(execution)


def _recovery_case_response(session: Session, recovery_case: RecoveryCase) -> RecoveryCaseResponse:
    payment = recovery_case.payment
    evidence = recovery_evidence(session, recovery_case)
    decisions = session.scalars(
        select(RecoveryDecisionRecord)
        .where(RecoveryDecisionRecord.recovery_case_id == recovery_case.id)
        .order_by(RecoveryDecisionRecord.created_at)
    ).all()
    plans = session.scalars(
        select(RecoveryExecutionPlan)
        .where(RecoveryExecutionPlan.recovery_case_id == recovery_case.id)
        .order_by(RecoveryExecutionPlan.created_at)
    ).all()
    executions = session.scalars(
        select(ExternalExecution)
        .where(ExternalExecution.recovery_case_id == recovery_case.id)
        .order_by(ExternalExecution.created_at)
    ).all()
    outcomes = session.scalars(
        select(ExternalOutcome)
        .where(ExternalOutcome.recovery_case_id == recovery_case.id)
        .order_by(ExternalOutcome.occurred_at)
    ).all()
    attribution = session.scalar(
        select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == recovery_case.id)
    )
    return RecoveryCaseResponse(
        id=recovery_case.id,
        status=recovery_case.status.value,
        correlation_id=recovery_case.correlation_id,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        subscription_status=payment.subscription.status,
        source=evidence.source.value,
        synthetic=evidence.synthetic,
        failure_type=evidence.failure_type,
        payment_method=evidence.payment_method,
        failure_description=evidence.failure_description,
        decisions=[DecisionResponse.model_validate(row) for row in decisions],
        plans=[PlanResponse.model_validate(row) for row in plans],
        executions=[ExecutionResponse.model_validate(row) for row in executions],
        outcomes=[_outcome_response(session, row) for row in outcomes],
        attribution=(
            AttributionResponse.model_validate(attribution) if attribution is not None else None
        ),
    )


def _outcome_response(session: Session, outcome: ExternalOutcome) -> OutcomeResponse:
    occurred_at = outcome.occurred_at
    webhook_event = session.get(ExternalWebhookEvent, outcome.webhook_event_id)
    if webhook_event is not None and webhook_event.event_type == "payment_link.paid":
        occurred_at = payment_link_completion_datetime(
            webhook_event.redacted_payload,
            fallback=outcome.occurred_at,
        )
    return OutcomeResponse(
        id=outcome.id,
        status=outcome.status.value,
        verified=outcome.verified,
        amount_minor=outcome.amount_minor,
        currency=outcome.currency,
        occurred_at=occurred_at,
        created_at=outcome.created_at,
    )
