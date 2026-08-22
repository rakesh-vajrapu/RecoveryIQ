from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.integrations.razorpay.dependencies import build_razorpay_gateway
from app.models import Customer, Merchant, Payment, RecoveryCase, RecoveryCaseStatus, Subscription
from app.services.razorpay_execution import create_operator_test_payment_link


def main() -> int:
    """Create at most one persisted Test Mode link after an explicit opt-in."""

    settings = get_settings()
    if not settings.razorpay_test_smoke_enabled:
        raise SystemExit("RAZORPAY_TEST_SMOKE_ENABLED=true is required")
    if settings.execution_environment != "RAZORPAY_TEST" or settings.razorpay_mode != "test":
        raise SystemExit("EXECUTION_ENVIRONMENT=RAZORPAY_TEST and RAZORPAY_MODE=test are required")
    if not settings.razorpay_api_configured:
        raise SystemExit("Razorpay Test Mode API credentials are required")
    gateway = build_razorpay_gateway(settings)
    try:
        with SessionLocal() as session:
            recovery_case = _get_or_create_smoke_case(session)
            execution = create_operator_test_payment_link(
                session,
                recovery_case_id=recovery_case.id,
                settings=settings,
                gateway=gateway,
            )
            fetched = (
                gateway.fetch_payment_link(execution.provider_entity_id)
                if execution.provider_entity_id is not None
                else None
            )
            print(
                json.dumps(
                    {
                        "status": "PASS" if fetched is not None else execution.state.value,
                        "mode": "RAZORPAY_TEST",
                        "resources_created_at_most": 1,
                        "fetch_verified": fetched is not None,
                    },
                    sort_keys=True,
                )
            )
    finally:
        gateway.close()
    return 0


def _get_or_create_smoke_case(session: Session) -> RecoveryCase:
    payment = session.scalar(
        select(Payment).where(Payment.external_id == "recoveriq:razorpay-test-smoke-payment")
    )
    if payment is None:
        merchant = Merchant(
            external_id="recoveriq:razorpay-test-smoke-merchant",
            name="RecoverIQ Test Smoke Merchant",
        )
        session.add(merchant)
        session.flush()
        customer = Customer(
            merchant_id=merchant.id,
            external_id="recoveriq:razorpay-test-smoke-customer",
            anonymous_reference="recoveriq-test-smoke",
        )
        session.add(customer)
        session.flush()
        subscription = Subscription(
            merchant_id=merchant.id,
            customer_id=customer.id,
            external_id="recoveriq:razorpay-test-smoke-subscription",
            status="pending",
        )
        session.add(subscription)
        session.flush()
        payment = Payment(
            merchant_id=merchant.id,
            customer_id=customer.id,
            subscription_id=subscription.id,
            external_id="recoveriq:razorpay-test-smoke-payment",
            amount_minor=100,
            currency="INR",
            status="failed",
        )
        session.add(payment)
        session.flush()
    recovery_case = session.scalar(
        select(RecoveryCase).where(RecoveryCase.payment_id == payment.id)
    )
    if recovery_case is None:
        recovery_case = RecoveryCase(
            payment_id=payment.id,
            status=RecoveryCaseStatus.HUMAN_REVIEW,
        )
        session.add(recovery_case)
        session.commit()
    return recovery_case


if __name__ == "__main__":
    raise SystemExit(main())
