
with open("tests/test_proof.py", "a", encoding="utf-8") as f:
    f.write('''

@pytest.mark.asyncio
async def test_proof_stages(client: Any, db_session: Session, mock_case_id: uuid.UUID) -> None:
    # 1. CASE ONLY
    case = create_test_case(db_session, mock_case_id, is_demo=False)
    db_session.commit()
    
    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    data = response.json()
    assert data["proof_completeness"] == "CASE_ONLY"
    assert "decision" not in data
    
    # 2. DECISION RECORDED
    decision = RecoveryDecisionRecord(
        recovery_case_id=case.id,
        decision_key="dec_stages",
        kind=DecisionKind.ACTION,
        selected_action="CREATE_PAYMENT_LINK",
        reason="Because",
        model_version="2.0.0",
        policy_version="2.0.0",
        feature_schema_version="2.0",
        context_metadata={"policy_config_hash": "hash1"}
    )
    db_session.add(decision)
    db_session.commit()
    
    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    assert response.json()["proof_completeness"] == "DECISION_RECORDED"
    
    # 3. EXECUTION RECORDED
    plan = RecoveryExecutionPlan(
        recovery_case_id=case.id,
        recovery_decision_id=decision.id,
        action="CREATE_PAYMENT_LINK",
        capability=ExecutionCapability.REAL_TEST_EXECUTION,
        initiator=ExecutionInitiator.POLICY,
        rationale="rat"
    )
    db_session.add(plan)
    exec_record = ExternalExecution(
        recovery_case_id=case.id,
        execution_plan_id=plan.id,
        execution_mode=ExecutionMode.RAZORPAY_TEST,
        action="CREATE_PAYMENT_LINK",
        state=ExternalExecutionState.SUCCEEDED,
        idempotency_key="idk2",
        provider_reference_id="ref2",
        amount_minor=1000,
    )
    db_session.add(exec_record)
    db_session.commit()
    
    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    assert response.json()["proof_completeness"] == "EXECUTION_RECORDED"
    
    # 4. PROVIDER OUTCOME RECORDED
    webhook = ExternalWebhookEvent(
        provider_event_id="ev_2",
        event_type="payment_link.paid",
        payload_sha256="hash2",
        provider_confirmation_status=ProviderConfirmationStatus.CONFIRMED,
        provider_confirmation_method="PAYMENT_LINK_FETCH"
    )
    db_session.add(webhook)
    db_session.flush()
    
    outcome = ExternalOutcome(
        recovery_case_id=case.id,
        external_execution_id=exec_record.id,
        webhook_event_id=webhook.id,
        status=ExternalOutcomeStatus.PAID,
        amount_minor=1000,
        currency="INR",
        occurred_at=datetime.now(UTC)
    )
    db_session.add(outcome)
    db_session.commit()
    
    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    assert response.json()["proof_completeness"] == "PROVIDER_OUTCOME_RECORDED"
    assert response.json()["provider_evidence"]["webhook_signature_verified"] is False
    
    # Add Webhook Signature Validation Audit
    from app.models import AuditEvent
    audit = AuditEvent(
        correlation_id=case.correlation_id,
        entity_type="ExternalWebhookEvent",
        entity_id=webhook.id,
        actor="TEST",
        event_type="WEBHOOK_SIGNATURE_VALIDATED",
        metadata={"method": "HMAC_SHA256_RAW_BODY"}
    )
    db_session.add(audit)
    db_session.commit()
    
    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    assert response.json()["provider_evidence"]["webhook_signature_verified"] is True
    
    # 5. ATTRIBUTED
    webhook.provider_confirmation_status = ProviderConfirmationStatus.NOT_REQUIRED
    
    attribution = RecoveryAttribution(
        recovery_case_id=case.id,
        external_execution_id=exec_record.id,
        external_outcome_id=outcome.id,
        execution_mode=ExecutionMode.RAZORPAY_TEST,
        amount_minor=1000,
        currency="INR",
        occurred_at=datetime.now(UTC),
        attribution_source="PAYMENT_LINK_PAID"
    )
    db_session.add(attribution)
    db_session.commit()
    
    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    assert response.json()["proof_completeness"] == "ATTRIBUTED"
    
    # 6. PROVIDER_TRIANGULATED
    webhook.provider_confirmation_status = ProviderConfirmationStatus.CONFIRMED
    db_session.commit()
    
    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    assert response.json()["proof_completeness"] == "PROVIDER_TRIANGULATED"
''')
