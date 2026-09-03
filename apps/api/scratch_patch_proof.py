import re

with open("app/api/proof.py", encoding="utf-8") as f:
    content = f.read()

# 1. Update DecisionProof
content = content.replace(
    "    selected_action: str | None\n    model_version: str | None",
    "    selected_action: str | None\n    provenance_status: str\n    model_version: str | None"
)

# 2. Update Webhook Verification
webhook_verification_logic = """        # Try to find webhook
        webhook = session.get(ExternalWebhookEvent, external_outcome.webhook_event_id)
        if webhook:
            conf_status = webhook.provider_confirmation_status
            if conf_status == ProviderConfirmationStatus.NOT_REQUIRED or not conf_status:
                status_str = "NOT_CAPTURED"
            else:
                status_str = conf_status.value
                
            # Audit webhook signature validated
            from app.models import AuditEvent
            audit_validated = session.scalar(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "ExternalWebhookEvent",
                    AuditEvent.entity_id == webhook.id,
                    AuditEvent.event_type == "WEBHOOK_SIGNATURE_VALIDATED"
                ).limit(1)
            )
            webhook_signature_verified = bool(audit_validated)

            # Invariant: Provider Truth Triangulation explicitly verifies 
            # amount_minor, amount_paid_minor, and currency match the execution 
            # before persisting ProviderConfirmationStatus.CONFIRMED.
            amount_verified = (
                True if status_str == "CONFIRMED"
                else (None if status_str == "NOT_CAPTURED" else False)
            )
                
            provider_evidence_proof = ProviderEvidenceProof(
                webhook_received=True,
                webhook_signature_verified=webhook_signature_verified,
                provider_event_id=webhook.provider_event_id,"""

content = re.sub(
    r"        # Try to find webhook.*?provider_event_id=webhook\.provider_event_id,",
    webhook_verification_logic,
    content,
    flags=re.DOTALL
)

# 3. Update Decision Provenance Logic
decision_provenance_logic = """    decision_proof = None
    if decision_record:
        has_provenance = bool(decision_record.context_metadata.get("policy_config_hash"))
        if evidence_lane == "DEMO_SYNTHETIC":
            prov_status = "NOT_APPLICABLE"
            mod_v, pol_v, hash_v = None, None, None
        elif has_provenance:
            prov_status = "RECORDED"
            mod_v = decision_record.model_version
            pol_v = decision_record.policy_version
            hash_v = decision_record.context_metadata.get("policy_config_hash")
        else:
            prov_status = "NOT_CAPTURED"
            mod_v, pol_v, hash_v = None, None, None

        decision_proof = DecisionProof(
            decision_id=decision_record.id,
            decision_kind=decision_record.kind.value,
            selected_action=decision_record.selected_action,
            provenance_status=prov_status,
            model_version=mod_v,
            policy_version=pol_v,
            policy_config_hash=hash_v,
            decision_recorded_at=decision_record.created_at,
        )"""

content = re.sub(
    r"    decision_proof = None.*?decision_recorded_at=decision_record\.created_at,\n        \)",
    decision_provenance_logic,
    content,
    flags=re.DOTALL
)

# 4. Update Completeness stages
completeness_logic = """    # Proof completeness
    completeness = "CASE_ONLY"
    if decision_proof:
        completeness = "DECISION_RECORDED"
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
"""
content = re.sub(
    r"    # Proof completeness.*?completeness = \"PROVIDER_TRIANGULATED\"\n",
    completeness_logic.lstrip(),
    content,
    flags=re.DOTALL
)

with open("app/api/proof.py", "w", encoding="utf-8") as f:
    f.write(content)
