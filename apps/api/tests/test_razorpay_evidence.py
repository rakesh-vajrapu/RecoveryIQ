import uuid
from datetime import UTC, datetime, timedelta
from collections.abc import Generator

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.session import create_database_engine
from app.models import (
    Payment,
    RecoveryCase,
    RecoveryDecisionRecord,
    RecoveryExecutionPlan,
    ExternalExecution,
    ExternalOutcome,
    RecoveryAttribution,
    ExternalWebhookEvent,
    RecoveryCaseStatus,
    Merchant,
    Customer,
    Subscription
)

pytestmark = pytest.mark.asyncio

@pytest.fixture
def db(test_settings: Settings) -> Generator[Session, None, None]:
    engine = create_database_engine(test_settings)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        yield session

async def test_get_razorpay_evidence_empty(client: AsyncClient, db: Session) -> None:
    response = await client.get("/api/integrations/razorpay/evidence")
    assert response.status_code == 200
    data = response.json()
    
    assert data["evidence_type"] == "RAZORPAY_TEST_MODE"
    assert data["all_time_recovered_minor"] == 0
    assert data["last_7_days_recovered_minor"] == 0
    assert data["selected_case"] is None

async def test_get_razorpay_evidence_seeded(client: AsyncClient, db: Session) -> None:
    # 1. Arrange Merchant, Customer, Subscription, Payment
    merchant = Merchant(external_id="m_1", name="Test Merchant")
    db.add(merchant)
    db.flush()

    customer = Customer(merchant_id=merchant.id, external_id="c_1", anonymous_reference="anon")
    db.add(customer)
    db.flush()

    sub = Subscription(merchant_id=merchant.id, customer_id=customer.id, external_id="s_1")
    db.add(sub)
    db.flush()

    payment = Payment(
        merchant_id=merchant.id,
        customer_id=customer.id,
        subscription_id=sub.id,
        external_id="p_1",
        amount_minor=100,
        currency="INR",
        status="failed"
    )
    db.add(payment)
    db.flush()

    # The endpoint hardcodes: target_id = uuid.UUID("40ebd35f-6c4c-4bb5-b7b5-a25914393528")
    target_id = uuid.UUID("40ebd35f-6c4c-4bb5-b7b5-a25914393528")

    case = RecoveryCase(
        id=target_id,
        payment_id=payment.id,
        status=RecoveryCaseStatus.RECOVERED,
        correlation_id=uuid.uuid4()
    )
    db.add(case)
    db.flush()

    decision = RecoveryDecisionRecord(
        recovery_case_id=case.id,
        decision_key="dec_123",
        kind="HUMAN_REVIEW",
        reason="INSUFFICIENT_CONTEXT"
    )
    db.add(decision)
    db.flush()

    plan = RecoveryExecutionPlan(
        recovery_case_id=case.id,
        recovery_decision_id=decision.id,
        action="CREATE_PAYMENT_LINK",
        capability="RAZORPAY_TEST_MODE_PAYMENT_LINK",
        initiator="OPERATOR_INITIATED",
        rationale="Test"
    )
    db.add(plan)
    db.flush()

    execution = ExternalExecution(
        recovery_case_id=case.id,
        execution_plan_id=plan.id,
        execution_mode="RAZORPAY_TEST",
        action="CREATE_PAYMENT_LINK",
        state="SUCCEEDED",
        payment_link_status="PAID",
        idempotency_key="idem_123",
        provider_reference_id="ref_123",
        provider_entity_id="pl_123",
        amount_minor=100,
        currency="INR"
    )
    db.add(execution)
    db.flush()

    # Webhook
    webhook = ExternalWebhookEvent(
        correlation_id=case.correlation_id,
        event_type="payment.failed",
        provider_event_id="evt_failed123",
        processing_status="PROCESSED",
        payload_sha256="fakehash"
    )
    db.add(webhook)
    db.flush()

    outcome = ExternalOutcome(
        recovery_case_id=case.id,
        external_execution_id=execution.id,
        webhook_event_id=webhook.id,
        status="PAID",
        verified=True,
        amount_minor=100,
        currency="INR",
        occurred_at=datetime.now(UTC).replace(tzinfo=None)
    )
    db.add(outcome)
    db.flush()

    # Recent attribution (last 7 days)
    recent_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2)
    attr1 = RecoveryAttribution(
        recovery_case_id=case.id,
        external_outcome_id=outcome.id,
        execution_mode="RAZORPAY_TEST",
        attribution_source="PAYMENT_LINK_PAID",
        amount_minor=100,
        currency="INR",
        occurred_at=recent_date,
        created_at=recent_date
    )
    db.add(attr1)

    # Need another payment/case for the old attribution to test last_7_days filtering properly
    payment2 = Payment(
        merchant_id=merchant.id,
        customer_id=customer.id,
        subscription_id=sub.id,
        external_id="p_2",
        amount_minor=150,
        currency="INR",
        status="failed"
    )
    db.add(payment2)
    db.flush()

    case2 = RecoveryCase(
        payment_id=payment2.id,
        status=RecoveryCaseStatus.RECOVERED,
        correlation_id=uuid.uuid4()
    )
    db.add(case2)
    db.flush()

    # Webhook 2
    webhook2 = ExternalWebhookEvent(
        correlation_id=case2.correlation_id,
        event_type="payment.failed",
        provider_event_id="evt_failed124",
        processing_status="PROCESSED",
        payload_sha256="fakehash2"
    )
    db.add(webhook2)
    db.flush()

    outcome2 = ExternalOutcome(
        recovery_case_id=case2.id,
        external_execution_id=execution.id,
        webhook_event_id=webhook2.id,
        status="PAID",
        verified=True,
        amount_minor=150,
        currency="INR",
        occurred_at=datetime.now(UTC).replace(tzinfo=None)
    )
    db.add(outcome2)
    db.flush()

    # Old attribution (older than 7 days)
    old_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10)
    attr2 = RecoveryAttribution(
        recovery_case_id=case2.id,
        external_outcome_id=outcome2.id,
        execution_mode="RAZORPAY_TEST",
        attribution_source="PAYMENT_LINK_PAID",
        amount_minor=150,
        currency="INR",
        occurred_at=old_date,
        created_at=old_date
    )
    db.add(attr2)
    
    db.commit()

    # 2. Act
    response = await client.get("/api/integrations/razorpay/evidence")
    assert response.status_code == 200
    data = response.json()

    # 3. Assert exact seeded arithmetic
    assert data["evidence_type"] == "RAZORPAY_TEST_MODE"
    assert data["no_real_money"] is True
    assert data["all_time_recovered_minor"] == 250
    assert data["last_7_days_recovered_minor"] == 100

    selected_case = data["selected_case"]
    assert selected_case is not None
    assert selected_case["case_id"] == "40ebd35f-6c4c-4bb5-b7b5-a25914393528"
    assert selected_case["status"] == "RECOVERED"
    assert selected_case["amount_minor"] == 100
    assert selected_case["execution_initiator"] == "OPERATOR_INITIATED"
    assert selected_case["decision"] == "HUMAN_REVIEW"

    # Check outcomes
    assert len(selected_case["outcomes"]) == 1
    assert selected_case["outcomes"][0]["status"] == "PAID"
    assert selected_case["outcomes"][0]["verified"] is True

    # Check attribution
    assert selected_case["attribution"] is not None
    assert selected_case["attribution"]["amount_minor"] == 100
    assert selected_case["attribution"]["attribution_source"] == "PAYMENT_LINK_PAID"

    # Check executions
    assert len(selected_case["executions"]) == 1
    assert selected_case["executions"][0]["action"] == "CREATE_PAYMENT_LINK"

    # Check failed attempts
    assert len(selected_case["failed_attempts"]) == 1

    # Ensure no secrets leak
    assert "webhook_secret" not in str(data).lower()
    assert "hmac" not in selected_case["webhooks"][0].get("raw_payload", "")
