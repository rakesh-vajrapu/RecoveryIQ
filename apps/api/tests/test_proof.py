import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.api.proof import compute_proof_fingerprint
from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_database_engine
from app.models import (
    Customer,
    DecisionKind,
    ExecutionCapability,
    ExecutionInitiator,
    ExecutionMode,
    ExternalExecution,
    ExternalExecutionState,
    ExternalOutcome,
    ExternalOutcomeStatus,
    ExternalWebhookEvent,
    Merchant,
    Payment,
    PaymentAttempt,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryDecisionRecord,
    RecoveryExecutionPlan,
)
from app.models.razorpay import ProviderConfirmationStatus


from typing import Generator, Any

@pytest.fixture
def db_session(test_settings: Settings) -> Generator[Session, None, None]:
    engine = create_database_engine(test_settings)
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_maker() as session:
        yield session
        session.rollback()
    # Let conftest drop_all handle cleanup.

@pytest.fixture
def mock_case_id() -> uuid.UUID:
    return uuid.uuid4()


def create_test_case(session: Session, case_id: uuid.UUID, is_demo: bool = False) -> RecoveryCase:
    merchant = Merchant(name="Test")
    session.add(merchant)
    session.flush()

    customer = Customer(merchant_id=merchant.id, anonymous_reference="cust_123")
    session.add(customer)
    session.flush()

    payment = Payment(
        merchant_id=merchant.id,
        customer_id=customer.id,
        subscription_id=uuid.uuid4(),  # dummy, would normally need real sub
        amount_minor=1000,
        status="failed",
        external_id="demo_recoveriq_123" if is_demo else "pay_123"
    )
    # mock subscription id
    from app.models import Subscription
    sub = Subscription(merchant_id=merchant.id, customer_id=customer.id, status="active")
    session.add(sub)
    session.flush()
    payment.subscription_id = sub.id
    
    session.add(payment)
    session.flush()
    
    payment_attempt = PaymentAttempt(
        payment_id=payment.id,
        status="failed",
        failure_code="insufficient_funds",
        payment_method="card",
    )
    session.add(payment_attempt)
    session.flush()

    case = RecoveryCase(
        id=case_id,
        payment_id=payment.id,
        status=RecoveryCaseStatus.RECOVERED,
        correlation_id=uuid.uuid4()
    )
    session.add(case)
    session.flush()
    return case


@pytest.mark.asyncio
async def test_get_proof_404(client: Any) -> None:
    response = await client.get(f"/api/recovery-cases/{uuid.uuid4()}/proof")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_proof_determinism() -> None:
    record_1 = {
        "case_id": "123",
        "evidence_lane": "RAZORPAY_TEST_MODE",
        "case": {"status": "RECOVERED"},
    }
    record_2 = {
        "evidence_lane": "RAZORPAY_TEST_MODE",
        "case": {"status": "RECOVERED"},
        "case_id": "123",
    }
    # order of keys shouldn't matter
    assert compute_proof_fingerprint(record_1) == compute_proof_fingerprint(record_2)

    record_3 = {
        "evidence_lane": "RAZORPAY_TEST_MODE",
        "case": {"status": "FAILED"},
        "case_id": "123",
    }
    # value matters
    assert compute_proof_fingerprint(record_1) != compute_proof_fingerprint(record_3)

    record_4 = {
        "case_id": "123",
        "evidence_lane": "RAZORPAY_TEST_MODE",
        "case": {"status": "RECOVERED"},
        "integrity": {"some": "data"}  # should be excluded
    }
    assert compute_proof_fingerprint(record_1) == compute_proof_fingerprint(record_4)
    
    # Check nulls are omitted and deterministic
    record_5 = {
        "case_id": "123",
        "evidence_lane": "RAZORPAY_TEST_MODE",
        "case": {"status": "RECOVERED"},
        "outcome": None
    }
    assert compute_proof_fingerprint(record_1) == compute_proof_fingerprint(record_5)


@pytest.mark.asyncio
async def test_demo_case_proof(client: Any, db_session: Session, mock_case_id: uuid.UUID) -> None:
    create_test_case(db_session, mock_case_id, is_demo=True)
    db_session.commit()

    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_lane"] == "DEMO_SYNTHETIC"
    assert data["proof_completeness"] == "DECISION_ONLY"
    assert "integrity" in data
    assert data["integrity"]["algorithm"] == "SHA-256"


@pytest.mark.asyncio
async def test_full_triangulated_proof(client: Any, db_session: Session, mock_case_id: uuid.UUID) -> None:
    case = create_test_case(db_session, mock_case_id, is_demo=False)
    # Convert to Razorpay mode for this test by mocking evidence as non-synthetic
    # We just need some real execution to make it not synthetic.
    # To make it RAZORPAY_TEST_MODE, we need an Execution
    
    decision = RecoveryDecisionRecord(
        recovery_case_id=case.id,
        decision_key="dec_1",
        kind=DecisionKind.ACTION,
        selected_action="CREATE_PAYMENT_LINK",
        reason="Because",
    )
    db_session.add(decision)
    db_session.flush()
    
    plan = RecoveryExecutionPlan(
        recovery_case_id=case.id,
        recovery_decision_id=decision.id,
        action="CREATE_PAYMENT_LINK",
        capability=ExecutionCapability.REAL_TEST_EXECUTION,
        initiator=ExecutionInitiator.POLICY,
        rationale="rat"
    )
    db_session.add(plan)
    db_session.flush()
    
    exec_record = ExternalExecution(
        recovery_case_id=case.id,
        execution_plan_id=plan.id,
        execution_mode=ExecutionMode.RAZORPAY_TEST,
        action="CREATE_PAYMENT_LINK",
        state=ExternalExecutionState.SUCCEEDED,
        idempotency_key="idk1",
        provider_reference_id="ref1",
        amount_minor=1000,
    )
    db_session.add(exec_record)
    
    webhook = ExternalWebhookEvent(
        provider_event_id="ev_1",
        event_type="payment_link.paid",
        payload_sha256="hash",
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
    db_session.flush()
    
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
    data = response.json()
    assert data["evidence_lane"] == "RAZORPAY_TEST_MODE"
    assert data["proof_completeness"] == "PROVIDER_TRIANGULATED"
    assert data["provider_evidence"]["provider_confirmation_status"] == "CONFIRMED"
    assert data["provider_evidence"]["amount_verified"] is True


@pytest.mark.asyncio
async def test_legacy_rs_2_proof(client: Any, db_session: Session, mock_case_id: uuid.UUID) -> None:
    case = create_test_case(db_session, mock_case_id, is_demo=False)
    
    decision = RecoveryDecisionRecord(
        recovery_case_id=case.id,
        decision_key="dec_2",
        kind=DecisionKind.ACTION,
        selected_action="CREATE_PAYMENT_LINK",
        reason="Because",
    )
    db_session.add(decision)
    db_session.flush()
    
    plan = RecoveryExecutionPlan(
        recovery_case_id=case.id,
        recovery_decision_id=decision.id,
        action="CREATE_PAYMENT_LINK",
        capability=ExecutionCapability.REAL_TEST_EXECUTION,
        initiator=ExecutionInitiator.OPERATOR_INITIATED, # Operator initiated
        rationale="rat"
    )
    db_session.add(plan)
    db_session.flush()
    
    exec_record = ExternalExecution(
        recovery_case_id=case.id,
        execution_plan_id=plan.id,
        execution_mode=ExecutionMode.RAZORPAY_TEST,
        action="CREATE_PAYMENT_LINK",
        state=ExternalExecutionState.SUCCEEDED,
        idempotency_key="idk1",
        provider_reference_id="ref1",
        amount_minor=200,
    )
    db_session.add(exec_record)
    
    webhook = ExternalWebhookEvent(
        provider_event_id="ev_1",
        event_type="payment_link.paid",
        payload_sha256="hash",
        provider_confirmation_status=ProviderConfirmationStatus.NOT_REQUIRED # Legacy!
    )
    db_session.add(webhook)
    db_session.flush()
    
    outcome = ExternalOutcome(
        recovery_case_id=case.id,
        external_execution_id=exec_record.id,
        webhook_event_id=webhook.id,
        status=ExternalOutcomeStatus.PAID,
        amount_minor=200,
        currency="INR",
        occurred_at=datetime.now(UTC)
    )
    db_session.add(outcome)
    db_session.flush()
    
    attribution = RecoveryAttribution(
        recovery_case_id=case.id,
        external_execution_id=exec_record.id,
        external_outcome_id=outcome.id,
        execution_mode=ExecutionMode.RAZORPAY_TEST,
        amount_minor=200,
        currency="INR",
        occurred_at=datetime.now(UTC),
        attribution_source="PAYMENT_LINK_PAID"
    )
    db_session.add(attribution)
    
    db_session.commit()

    response = await client.get(f"/api/recovery-cases/{mock_case_id}/proof")
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_lane"] == "RAZORPAY_TEST_MODE"
    assert data["proof_completeness"] == "ATTRIBUTED" # Not triangulated!
    assert data["provider_evidence"]["provider_confirmation_status"] == "NOT_CAPTURED"
    assert data["provider_evidence"]["amount_verified"] is None
    assert data["authorization"]["autonomous"] is False
    assert data["authorization"]["initiator"] == "OPERATOR_INITIATED"
