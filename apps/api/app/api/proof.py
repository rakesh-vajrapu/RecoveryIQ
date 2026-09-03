from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import (
    ExecutionInitiator,
    ExternalExecution,
    ExternalOutcome,
    ExternalWebhookEvent,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryDecisionRecord,
    RecoveryExecutionPlan,
)
from app.models.razorpay import ProviderConfirmationStatus
from app.services.recovery_evidence import recovery_evidence

router = APIRouter()
logger = structlog.get_logger()


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CaseProof(ApiModel):
    status: str
    amount_minor: int
    currency: str
    created_at: datetime
    recovered_at: datetime | None


class DecisionProof(ApiModel):
    decision_id: uuid.UUID
    decision_kind: str
    selected_action: str | None
    model_version: str | None
    policy_version: str | None
    policy_config_hash: str | None
    decision_recorded_at: datetime


class AuthorizationProof(ApiModel):
    initiator: str
    provider_capability: str
    execution_mode: str
    autonomous: bool


class ExecutionProof(ApiModel):
    execution_id: uuid.UUID
    provider: str
    provider_entity_type: str
    provider_entity_reference: str
    execution_status: str
    created_at: datetime


class ProviderEvidenceProof(ApiModel):
    webhook_received: bool
    webhook_signature_verified: bool
    provider_event_id: str | None
    provider_confirmation_status: str
    provider_confirmation_method: str | None
    provider_confirmed_at: datetime | None
    amount_verified: bool | None
    currency_verified: bool | None
    reference_verified: bool | None


class OutcomeProof(ApiModel):
    external_outcome_id: uuid.UUID
    provider_payment_reference: str | None
    outcome: str
    recorded_at: datetime


class AttributionProof(ApiModel):
    attribution_id: uuid.UUID
    attributed: bool
    amount_minor: int
    currency: str
    recorded_at: datetime
    local_semantics: str


class IntegrityProof(ApiModel):
    canonicalization_version: str
    algorithm: str
    fingerprint: str


class RecoveryProofRecord(ApiModel):
    proof_version: str
    case_id: uuid.UUID
    evidence_lane: str
    case: CaseProof
    decision: DecisionProof | None = None
    authorization: AuthorizationProof | None = None
    execution: ExecutionProof | None = None
    provider_evidence: ProviderEvidenceProof | None = None
    outcome: OutcomeProof | None = None
    attribution: AttributionProof | None = None
    integrity: IntegrityProof
    proof_completeness: str


def compute_proof_fingerprint(record_dict: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 fingerprint over non-secret fields."""
    # We remove the integrity block itself if present
    payload = {k: v for k, v in record_dict.items() if k != "integrity" and v is not None}
    
    canonical_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    
    return hashlib.sha256(canonical_bytes).hexdigest()


def build_recovery_proof_record(session: Session, recovery_case: RecoveryCase) -> RecoveryProofRecord:
    evidence = recovery_evidence(session, recovery_case)
    evidence_lane = "DEMO_SYNTHETIC" if evidence.synthetic else "RAZORPAY_TEST_MODE"
    
    recovered_at = None
    
    # Decision
    decision_record = session.scalar(
        select(RecoveryDecisionRecord)
        .where(RecoveryDecisionRecord.recovery_case_id == recovery_case.id)
        .order_by(RecoveryDecisionRecord.created_at.desc())
        .limit(1)
    )
    
    decision_proof = None
    if decision_record:
        decision_proof = DecisionProof(
            decision_id=decision_record.id,
            decision_kind=decision_record.kind.value,
            selected_action=decision_record.selected_action,
            model_version=decision_record.model_version if evidence_lane != "DEMO_SYNTHETIC" else None,
            policy_version=decision_record.policy_version if evidence_lane != "DEMO_SYNTHETIC" else None,
            policy_config_hash=decision_record.context_metadata.get("policy_config_hash") if evidence_lane != "DEMO_SYNTHETIC" else None,
            decision_recorded_at=decision_record.created_at,
        )
    
    # Execution & Authorization
    execution_plan = session.scalar(
        select(RecoveryExecutionPlan)
        .where(RecoveryExecutionPlan.recovery_case_id == recovery_case.id)
        .order_by(RecoveryExecutionPlan.created_at.desc())
        .limit(1)
    )
    
    external_execution = session.scalar(
        select(ExternalExecution)
        .where(ExternalExecution.recovery_case_id == recovery_case.id)
        .order_by(ExternalExecution.created_at.desc())
        .limit(1)
    )
    
    authorization_proof = None
    if execution_plan:
        mode = external_execution.execution_mode.value if external_execution else "UNKNOWN"
        authorization_proof = AuthorizationProof(
            initiator=execution_plan.initiator.value,
            provider_capability=execution_plan.capability.value,
            execution_mode=mode,
            autonomous=(execution_plan.initiator == ExecutionInitiator.POLICY),
        )
        
    execution_proof = None
    if external_execution:
        provider_entity_type = "PAYMENT_LINK" if external_execution.action == "CREATE_PAYMENT_LINK" else "UNKNOWN"
        execution_proof = ExecutionProof(
            execution_id=external_execution.id,
            provider=external_execution.provider,
            provider_entity_type=provider_entity_type,
            provider_entity_reference=external_execution.provider_reference_id,
            execution_status=external_execution.state.value,
            created_at=external_execution.created_at,
        )
        
    # Outcome & Provider Evidence
    external_outcome = session.scalar(
        select(ExternalOutcome)
        .where(ExternalOutcome.recovery_case_id == recovery_case.id)
        .order_by(ExternalOutcome.occurred_at.desc())
        .limit(1)
    )
    
    outcome_proof = None
    provider_evidence_proof = None
    
    if external_outcome:
        outcome_proof = OutcomeProof(
            external_outcome_id=external_outcome.id,
            provider_payment_reference=external_outcome.external_payment_id,
            outcome=external_outcome.status.value,
            recorded_at=external_outcome.occurred_at,
        )
        if recovery_case.status == RecoveryCaseStatus.RECOVERED:
            recovered_at = external_outcome.occurred_at
            
        # Try to find webhook
        webhook = session.get(ExternalWebhookEvent, external_outcome.webhook_event_id)
        if webhook:
            conf_status = webhook.provider_confirmation_status
            if conf_status == ProviderConfirmationStatus.NOT_REQUIRED or not conf_status:
                status_str = "NOT_CAPTURED"
            else:
                status_str = conf_status.value
                
            amount_verified = True if status_str == "CONFIRMED" else (None if status_str == "NOT_CAPTURED" else False)
                
            provider_evidence_proof = ProviderEvidenceProof(
                webhook_received=True,
                webhook_signature_verified=True,  # if it was persisted, it was verified
                provider_event_id=webhook.provider_event_id,
                provider_confirmation_status=status_str,
                provider_confirmation_method=webhook.provider_confirmation_method,
                provider_confirmed_at=webhook.provider_confirmed_at,
                amount_verified=amount_verified,
                currency_verified=amount_verified,
                reference_verified=amount_verified,
            )
            
    # Attribution
    attribution = session.scalar(
        select(RecoveryAttribution)
        .where(RecoveryAttribution.recovery_case_id == recovery_case.id)
        .order_by(RecoveryAttribution.occurred_at.desc())
        .limit(1)
    )
    
    attribution_proof = None
    if attribution:
        attribution_proof = AttributionProof(
            attribution_id=attribution.id,
            attributed=True,
            amount_minor=attribution.amount_minor,
            currency=attribution.currency,
            recorded_at=attribution.occurred_at,
            local_semantics="EXACTLY_ONCE_LOCAL",
        )
        if recovered_at is None and recovery_case.status == RecoveryCaseStatus.RECOVERED:
            recovered_at = attribution.occurred_at

    case_proof = CaseProof(
        status=recovery_case.status.value,
        amount_minor=recovery_case.payment.amount_minor,
        currency=recovery_case.payment.currency,
        created_at=recovery_case.created_at,
        recovered_at=recovered_at,
    )
    
    # Proof completeness
    completeness = "DECISION_ONLY"
    if external_execution:
        completeness = "EXECUTION_RECORDED"
    if external_outcome:
        completeness = "PROVIDER_OUTCOME_RECORDED"
    if attribution:
        completeness = "ATTRIBUTED"
    if (
        provider_evidence_proof 
        and provider_evidence_proof.provider_confirmation_status == "CONFIRMED"
        and attribution 
        and external_outcome
    ):
        completeness = "PROVIDER_TRIANGULATED"
            
    # Build dictionary without integrity block
    proof_dict = {
        "proof_version": "1.0.0",
        "case_id": str(recovery_case.id),
        "evidence_lane": evidence_lane,
        "case": json.loads(case_proof.model_dump_json(exclude_none=True)),
        "proof_completeness": completeness,
    }
    if decision_proof:
        proof_dict["decision"] = json.loads(decision_proof.model_dump_json(exclude_none=True))
    if authorization_proof:
        proof_dict["authorization"] = json.loads(authorization_proof.model_dump_json(exclude_none=True))
    if execution_proof:
        proof_dict["execution"] = json.loads(execution_proof.model_dump_json(exclude_none=True))
    if provider_evidence_proof:
        proof_dict["provider_evidence"] = json.loads(provider_evidence_proof.model_dump_json(exclude_none=True))
    if outcome_proof:
        proof_dict["outcome"] = json.loads(outcome_proof.model_dump_json(exclude_none=True))
    if attribution_proof:
        proof_dict["attribution"] = json.loads(attribution_proof.model_dump_json(exclude_none=True))
        
    fingerprint = compute_proof_fingerprint(proof_dict)
    
    integrity_proof = IntegrityProof(
        canonicalization_version="1.0.0",
        algorithm="SHA-256",
        fingerprint=fingerprint,
    )
    
    return RecoveryProofRecord(
        proof_version="1.0.0",
        case_id=recovery_case.id,
        evidence_lane=evidence_lane,
        case=case_proof,
        decision=decision_proof,
        authorization=authorization_proof,
        execution=execution_proof,
        provider_evidence=provider_evidence_proof,
        outcome=outcome_proof,
        attribution=attribution_proof,
        integrity=integrity_proof,
        proof_completeness=completeness,
    )


@router.get(
    "/api/recovery-cases/{recovery_case_id}/proof",
    response_model=RecoveryProofRecord,
    tags=["recovery"],
)
def get_recovery_case_proof(
    recovery_case_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> RecoveryProofRecord:
    recovery_case = session.get(RecoveryCase, recovery_case_id)
    if recovery_case is None:
        raise HTTPException(status_code=404, detail="recovery case not found")
    
    return build_recovery_proof_record(session, recovery_case)
