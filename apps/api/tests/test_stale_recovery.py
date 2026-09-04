import uuid
from collections.abc import Generator
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.integrations.razorpay.fake import FakeRazorpayGateway
from app.models import (
    ExecutionInitiator,
    ExecutionMode,
    ExternalExecution,
    ExternalExecutionState,
    Payment,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryExecutionPlan,
)
from app.models.entities import utc_now
from app.services.stale_recovery import sweep_stale_external_executions


@pytest.fixture
def sessions() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _setup_stale_data(
    session: Session,
    state: ExternalExecutionState,
    minutes_old: int = 20,
    provider_reference_id: str | None = None,
    amount_minor: int = 1000,
    currency: str = "INR",
) -> tuple[RecoveryCase, ExternalExecution]:
    now = utc_now()
    stale_time = now - timedelta(minutes=minutes_old)
    
    payment = Payment(
        id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        external_id=f"pay_{uuid.uuid4().hex[:10]}",
        amount_minor=amount_minor,
        currency=currency,
        status="captured",
        created_at=stale_time,
    )
    session.add(payment)

    case = RecoveryCase(
        id=uuid.uuid4(),
        payment_id=payment.id,
        correlation_id=uuid.uuid4(),
        status=RecoveryCaseStatus.EXECUTING,
        created_at=stale_time,
    )
    session.add(case)
    
    plan = RecoveryExecutionPlan(
        id=uuid.uuid4(),
        recovery_case_id=case.id,
        action="CREATE_PAYMENT_LINK",
        capability="REAL_TEST_EXECUTION",
        initiator=ExecutionInitiator.OPERATOR_INITIATED,
        rationale="test",
        created_at=stale_time,
    )
    session.add(plan)

    execution = ExternalExecution(
        id=uuid.uuid4(),
        recovery_case_id=case.id,
        execution_plan_id=plan.id,
        execution_mode=ExecutionMode.RAZORPAY_TEST,
        action="CREATE_PAYMENT_LINK",
        state=state,
        idempotency_key=f"razorpay-test:payment-link:{case.id}",
        amount_minor=amount_minor,
        currency=currency,
        created_at=stale_time,
        requested_at=(
            stale_time 
            if state in (ExternalExecutionState.EXECUTING, ExternalExecutionState.UNKNOWN) 
            else None
        ),
        provider_reference_id=provider_reference_id or f"ref_{uuid.uuid4().hex[:10]}",
    )
    session.add(execution)
    session.commit()
    return case, execution


def test_stale_pre_dispatch_reservation_swept(sessions: Session) -> None:
    gateway = FakeRazorpayGateway("secret")
    case, execution = _setup_stale_data(sessions, ExternalExecutionState.PLANNED)

    result = sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    assert result["pre_dispatch_swept"] == 1
    assert result["post_dispatch_swept"] == 0

    sessions.refresh(execution)
    sessions.refresh(case)
    
    assert execution.state == ExternalExecutionState.FAILED
    assert execution.failure_category == "STALE_RESERVATION"
    assert case.status == RecoveryCaseStatus.FAILED
    assert gateway.create_calls == 0


def test_stale_post_dispatch_ambiguous_execution(sessions: Session) -> None:
    gateway = FakeRazorpayGateway("secret")
    def mock_find(*args: object, **kwargs: object) -> None:
        from app.integrations.razorpay.gateway import RazorpayUnknownOutcomeError
        raise RazorpayUnknownOutcomeError("mocked network failure")
    gateway.find_payment_link_by_reference = mock_find  # type: ignore[method-assign]

    _case, execution = _setup_stale_data(
        sessions, ExternalExecutionState.EXECUTING, provider_reference_id="ref_123"
    )

    result = sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    assert result["post_dispatch_swept"] == 1

    sessions.refresh(execution)
    assert execution.state == ExternalExecutionState.UNKNOWN
    assert execution.failure_category == "RECONCILIATION_PENDING"
    assert gateway.create_calls == 0


def test_provider_resource_found_during_reconciliation(sessions: Session) -> None:
    gateway = FakeRazorpayGateway("secret")
    _case, execution = _setup_stale_data(
        sessions, ExternalExecutionState.EXECUTING, provider_reference_id="ref_456"
    )

    # Simulate provider HAS the link
    from app.integrations.razorpay.gateway import PaymentLinkRequest
    gateway.create_payment_link(PaymentLinkRequest(
        amount_minor=execution.amount_minor,
        currency=execution.currency,
        reference_id="ref_456",
        description="test",
        notes={},
    ))
    gateway.create_calls = 0 # reset counter

    result = sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    assert result["post_dispatch_swept"] == 1

    sessions.refresh(execution)
    assert execution.state == ExternalExecutionState.SUCCEEDED
    assert execution.provider_entity_id is not None
    assert gateway.create_calls == 0


def test_provider_lookup_mismatch(sessions: Session) -> None:
    gateway = FakeRazorpayGateway("secret")
    _case, execution = _setup_stale_data(
        sessions, ExternalExecutionState.EXECUTING, provider_reference_id="ref_789"
    )

    from app.integrations.razorpay.gateway import PaymentLinkRequest
    gateway.create_payment_link(PaymentLinkRequest(
        amount_minor=2000, # MISMATCH
        currency="INR",
        reference_id="ref_789",
        description="test",
        notes={},
    ))
    gateway.create_calls = 0 # reset counter

    sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    sessions.refresh(execution)
    assert execution.state == ExternalExecutionState.UNKNOWN
    assert execution.failure_category == "RECONCILIATION_MISMATCH"


def test_duplicate_sweeper_invocation(sessions: Session) -> None:
    gateway = FakeRazorpayGateway("secret")
    _case, _execution = _setup_stale_data(sessions, ExternalExecutionState.PLANNED)

    result1 = sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    assert result1["pre_dispatch_swept"] == 1

    result2 = sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    assert result2["pre_dispatch_swept"] == 0


def test_concurrent_sweeper_race(sessions: Session) -> None:
    gateway = FakeRazorpayGateway("secret")
    _case, execution = _setup_stale_data(sessions, ExternalExecutionState.PLANNED)

    # Simulate executor claiming it first (changes state)
    execution.state = ExternalExecutionState.EXECUTING
    sessions.commit()

    result = sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    assert result["pre_dispatch_swept"] == 0


def test_terminal_execution_ignored(sessions: Session) -> None:
    gateway = FakeRazorpayGateway("secret")
    _case, _execution = _setup_stale_data(sessions, ExternalExecutionState.SUCCEEDED)

    result = sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    assert result["pre_dispatch_swept"] == 0
    assert result["post_dispatch_swept"] == 0


def test_provider_lookup_returns_none(sessions: Session) -> None:
    gateway = FakeRazorpayGateway("secret")
    _case, execution = _setup_stale_data(
        sessions, ExternalExecutionState.EXECUTING, provider_reference_id="ref_none"
    )

    result = sweep_stale_external_executions(sessions, gateway=gateway, timeout_minutes=15)
    assert result["post_dispatch_swept"] == 1

    sessions.refresh(execution)
    assert execution.state == ExternalExecutionState.UNKNOWN
    assert execution.failure_category == "RECONCILIATION_NOT_FOUND"
    assert gateway.create_calls == 0
