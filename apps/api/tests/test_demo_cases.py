from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_database_engine
from app.integrations.razorpay.fake import FakeRazorpayGateway
from app.models import (
    AuditEvent,
    Customer,
    ExternalEntityMapping,
    ExternalExecution,
    ExternalOutcome,
    ExternalWebhookEvent,
    FailureEvent,
    Merchant,
    Payment,
    PaymentAttempt,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryDecisionRecord,
    RecoveryExecutionPlan,
    Subscription,
)
from app.services.demo_cases import (
    DEMO_CASES,
    DemoSeedDisabledError,
    reset_demo_cases,
    seed_demo_cases,
)
from app.services.razorpay_execution import (
    OperatorExecutionError,
    create_operator_test_payment_link,
)
from app.services.recovery_evidence import DEMO_EXTERNAL_ID_PREFIX, DEMO_SOURCE, recovery_evidence


@pytest.fixture
def demo_sessions(tmp_path: Path) -> Generator[sessionmaker[Session], None, None]:
    settings = _settings(database_url=f"sqlite:///{tmp_path / 'demo-seed.db'}")
    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield sessions
    Base.metadata.drop_all(engine)
    engine.dispose()


def _settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "development",
        "enable_demo_seed": True,
        "database_url": "sqlite://",
        "celery_task_always_eager": True,
    }
    values.update(updates)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("app_env", ["test", "staging", "production"])
def test_demo_seed_requires_development(demo_sessions: sessionmaker[Session], app_env: str) -> None:
    with (
        demo_sessions() as session,
        pytest.raises(DemoSeedDisabledError, match="APP_ENV=development"),
    ):
        seed_demo_cases(session, settings=_settings(app_env=app_env))
    with demo_sessions() as session:
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 0


def test_demo_seed_requires_explicit_flag(demo_sessions: sessionmaker[Session]) -> None:
    with (
        demo_sessions() as session,
        pytest.raises(DemoSeedDisabledError, match="ENABLE_DEMO_SEED=true"),
    ):
        seed_demo_cases(session, settings=_settings(enable_demo_seed=False))
    with demo_sessions() as session:
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 0


def test_demo_seed_is_labeled_idempotent_and_has_no_provider_side_effects(
    demo_sessions: sessionmaker[Session],
) -> None:
    settings = _settings()
    with demo_sessions.begin() as session:
        first = seed_demo_cases(session, settings=settings)
    with demo_sessions.begin() as session:
        second = seed_demo_cases(session, settings=settings)

    assert first.created == len(DEMO_CASES) == 8
    assert first.existing == 0
    assert first.total_amount_minor == 39_824_900
    assert second.created == 0
    assert second.existing == 8

    with demo_sessions() as session:
        cases = session.scalars(select(RecoveryCase).order_by(RecoveryCase.created_at)).all()
        payments = session.scalars(select(Payment).order_by(Payment.external_id)).all()
        attempts = session.scalars(
            select(PaymentAttempt).order_by(PaymentAttempt.external_id)
        ).all()
        decisions = session.scalars(select(RecoveryDecisionRecord)).all()
        audits = session.scalars(select(AuditEvent)).all()

        assert len(cases) == len(payments) == len(attempts) == 8
        assert [payment.external_id for payment in payments] == [
            spec.external_id for spec in DEMO_CASES
        ]
        assert all(case.status is RecoveryCaseStatus.HUMAN_REVIEW for case in cases)
        assert len(decisions) == 8
        assert all(decision.kind.value == "HUMAN_REVIEW" for decision in decisions)
        assert all(decision.reason == "INSUFFICIENT_CONTEXT" for decision in decisions)
        assert all(decision.context_metadata["source"] == DEMO_SOURCE for decision in decisions)
        assert all(decision.context_metadata["synthetic"] is True for decision in decisions)
        assert any(event.event_type == "DEMO_SYNTHETIC_FAILURE_RECORDED" for event in audits)
        assert any(event.event_type == "DEMO_SYNTHETIC_RECOVERY_CASE_CREATED" for event in audits)
        assert all(
            event.event_metadata.get("source") == DEMO_SOURCE
            for event in audits
            if event.actor == "DEMO_SEED_CLI"
        )
        assert all(recovery_evidence(session, case).synthetic for case in cases)
        assert session.scalar(select(func.count()).select_from(RecoveryExecutionPlan)) == 8
        assert session.scalar(select(func.count()).select_from(ExternalWebhookEvent)) == 0
        assert session.scalar(select(func.count()).select_from(FailureEvent)) == 0
        assert session.scalar(select(func.count()).select_from(ExternalEntityMapping)) == 0
        assert session.scalar(select(func.count()).select_from(ExternalExecution)) == 0
        assert session.scalar(select(func.count()).select_from(ExternalOutcome)) == 0
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 0


def test_demo_case_cannot_call_razorpay_or_create_payment_link(
    demo_sessions: sessionmaker[Session],
) -> None:
    settings = _settings(
        execution_environment="RAZORPAY_TEST",
        razorpay_mode="test",
        razorpay_key_id=SecretStr("rzp_test_offline"),
        razorpay_key_secret=SecretStr("offline-key-secret"),
    )
    gateway = FakeRazorpayGateway("offline-webhook-secret")
    with demo_sessions.begin() as session:
        seed_demo_cases(session, settings=settings)
    with demo_sessions() as session:
        recovery_case = session.scalar(select(RecoveryCase).order_by(RecoveryCase.created_at))
        assert recovery_case is not None
        with pytest.raises(OperatorExecutionError, match="synthetic demo cases"):
            create_operator_test_payment_link(
                session,
                recovery_case_id=recovery_case.id,
                settings=settings,
                gateway=gateway,
            )
        assert gateway.create_calls == 0
        assert session.scalar(select(func.count()).select_from(ExternalExecution)) == 0
        assert session.scalar(select(func.count()).select_from(ExternalOutcome)) == 0
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 0


def test_demo_reset_removes_only_demo_records(
    demo_sessions: sessionmaker[Session],
) -> None:
    settings = _settings()
    with demo_sessions.begin() as session:
        seed_demo_cases(session, settings=settings)
        provider_case = _add_provider_case(session)
        provider_case_id = provider_case.id

    with demo_sessions.begin() as session:
        result = reset_demo_cases(session, settings=settings)

    assert result.removed_cases == 8
    with demo_sessions() as session:
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
        assert session.get(RecoveryCase, provider_case_id) is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(Payment)
                .where(Payment.external_id.startswith(DEMO_EXTERNAL_ID_PREFIX))
            )
            == 0
        )
        assert session.scalar(select(func.count()).select_from(ExternalWebhookEvent)) == 1


@pytest.mark.asyncio
async def test_no_public_recovery_case_creation_route(client: object) -> None:
    response = await client.post("/api/recovery-cases", json={})  # type: ignore[attr-defined]
    assert response.status_code == 405


def _add_provider_case(session: Session) -> RecoveryCase:
    merchant = Merchant(external_id="provider-merchant", name="Provider Test Merchant")
    session.add(merchant)
    session.flush()
    customer = Customer(
        merchant_id=merchant.id,
        external_id="provider-customer",
        anonymous_reference="provider-customer",
    )
    session.add(customer)
    session.flush()
    subscription = Subscription(
        merchant_id=merchant.id,
        customer_id=customer.id,
        external_id="sub_provider_test",
        status="active",
    )
    session.add(subscription)
    session.flush()
    payment = Payment(
        merchant_id=merchant.id,
        customer_id=customer.id,
        subscription_id=subscription.id,
        external_id="pay_provider_test",
        amount_minor=100,
        currency="INR",
        status="failed",
    )
    session.add(payment)
    session.flush()
    recovery_case = RecoveryCase(payment_id=payment.id, status=RecoveryCaseStatus.HUMAN_REVIEW)
    session.add(recovery_case)
    session.flush()
    event = ExternalWebhookEvent(
        provider_event_id="evt_provider_test",
        event_type="payment.failed",
        payload_sha256="0" * 64,
        correlation_id=recovery_case.correlation_id,
    )
    session.add(event)
    session.flush()
    return recovery_case
