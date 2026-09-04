from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    Customer,
    Merchant,
    Payment,
    PaymentAttempt,
    RecoveryCase,
    RecoveryCaseStatus,
    Subscription,
)
from app.services.audit import add_audit_event


class RazorpayJudgeDemoError(RuntimeError):
    pass


def prepare_judge_demo_case(
    session: Session,
    *,
    settings: Settings,
) -> RecoveryCase:
    if not settings.enable_razorpay_judge_demo:
        raise RazorpayJudgeDemoError("ENABLE_RAZORPAY_JUDGE_DEMO=true is required")
    if settings.execution_environment != "RAZORPAY_TEST":
        raise RazorpayJudgeDemoError("EXECUTION_ENVIRONMENT=RAZORPAY_TEST is required")
    if settings.razorpay_mode != "test":
        raise RazorpayJudgeDemoError("RAZORPAY_MODE=test is required")
    if not settings.razorpay_api_configured:
        raise RazorpayJudgeDemoError("Razorpay Test Mode API credentials are not configured")
    if not settings.razorpay_webhook_configured:
        raise RazorpayJudgeDemoError("Razorpay Test Mode Webhook secret is not configured")

    merchant = session.scalar(
        select(Merchant).where(Merchant.external_id == "razorpay_judge_setup_merchant")
    )
    if merchant is None:
        merchant = Merchant(
            external_id="razorpay_judge_setup_merchant",
            name="Razorpay Test Mode Judge Account",
        )
        session.add(merchant)
        session.flush()

    case_uuid = uuid.uuid4().hex
    setup_id = f"razorpay_judge_setup_{case_uuid}"

    customer = Customer(
        merchant_id=merchant.id,
        external_id=f"customer_{setup_id}",
        anonymous_reference=f"demo-customer-{case_uuid[:8]}",
    )
    session.add(customer)
    session.flush()

    subscription = Subscription(
        merchant_id=merchant.id,
        customer_id=customer.id,
        external_id=f"sub_{setup_id}",
        status="past_due",
    )
    session.add(subscription)
    session.flush()

    payment = Payment(
        merchant_id=merchant.id,
        customer_id=customer.id,
        subscription_id=subscription.id,
        external_id=setup_id,
        amount_minor=100000,
        currency="INR",
        status="failed",
    )
    session.add(payment)
    session.flush()

    attempt = PaymentAttempt(
        payment_id=payment.id,
        external_id=f"attempt_{setup_id}",
        status="failed",
        failure_code="LOCAL_UNVERIFIED",
        payment_method="CARD",
        issuer="DEMO_ISSUER",
    )
    session.add(attempt)
    session.flush()

    recovery_case = RecoveryCase(
        payment_id=payment.id,
        status=RecoveryCaseStatus.DETECTED,
    )
    session.add(recovery_case)
    session.flush()

    metadata = {
        "source": "RAZORPAY_TEST_MODE",
        "synthetic": False,
        "demo_id": setup_id,
        "amount_minor": 100000,
        "currency": "INR",
        "payment_method": "CARD",
        "failure_type": "LOCAL_UNVERIFIED",
        "failure_source": "LOCAL",
        "description": "This case was prepared locally for a controlled Razorpay Test Mode provider demonstration. Provider evidence begins when the Test Mode Payment Link is created and Razorpay events are received.",
    }

    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="PaymentAttempt",
        entity_id=attempt.id,
        actor="JUDGE_DEMO_SETUP",
        event_type="LOCAL_TEST_SETUP",
        metadata=metadata,
    )

    add_audit_event(
        session,
        correlation_id=recovery_case.correlation_id,
        entity_type="RecoveryCase",
        entity_id=recovery_case.id,
        actor="JUDGE_DEMO_SETUP",
        event_type="LOCAL_TEST_SETUP",
        metadata=metadata,
    )

    session.commit()
    return recovery_case
