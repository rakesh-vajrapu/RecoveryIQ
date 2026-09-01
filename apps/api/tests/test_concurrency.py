import asyncio
import copy
import hashlib
import hmac
import json
from typing import Any

import pytest
from httpx import Response
from sqlalchemy import select

from app.models import (
    ExternalExecution,
    ExternalOutcome,
    ExternalWebhookEvent,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryCaseStatus,
)
from tests.test_razorpay_integration import (
    FIXTURES,
    WEBHOOK_SECRET,
    RazorpayHarness,
    razorpay_harness as razorpay_harness,  # noqa: F811  # pytest fixture re-export
)

pytestmark = pytest.mark.asyncio


def sign_webhook(payload: dict[str, Any], secret: str = WEBHOOK_SECRET) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, signature


async def test_webhook_deduplication_race(razorpay_harness: RazorpayHarness) -> None:
    payload = json.loads((FIXTURES / "subscription_charged.json").read_text(encoding="utf-8"))
    payload["created_at"] = 1718000000
    body, signature = sign_webhook(payload)
    event_id = "ev_Race1"
    headers = {
        "x-razorpay-signature": signature,
        "x-razorpay-event-id": event_id,
        "content-type": "application/json",
    }

    async def fire() -> Response:
        return await razorpay_harness.client.post(
            "/webhooks/razorpay", content=body, headers=headers
        )

    responses = await asyncio.gather(*[fire() for _ in range(10)])

    for r in responses:
        assert r.status_code in (200, 202)

    with razorpay_harness.sessions() as session:
        events = session.scalars(
            select(ExternalWebhookEvent).where(ExternalWebhookEvent.provider_event_id == event_id)
        ).all()
        assert len(events) == 1


async def test_execution_idempotency_race(razorpay_harness: RazorpayHarness) -> None:
    payload = json.loads((FIXTURES / "subscription_pending.json").read_text(encoding="utf-8"))
    body, signature = sign_webhook(payload)
    event_id = "ev_Race2Setup"
    headers = {
        "x-razorpay-signature": signature,
        "x-razorpay-event-id": event_id,
        "content-type": "application/json",
    }
    await razorpay_harness.client.post("/webhooks/razorpay", content=body, headers=headers)

    with razorpay_harness.sessions() as session:
        case = session.scalar(select(RecoveryCase).limit(1))
        assert case is not None
        case_id = str(case.id)

    async def fire() -> Response:
        return await razorpay_harness.client.post(
            f"/api/recovery-cases/{case_id}/test-payment-link"
        )

    responses = await asyncio.gather(*[fire() for _ in range(10)])

    successes = [r for r in responses if r.status_code == 200]
    conflicts = [r for r in responses if r.status_code == 409]

    assert len(successes) > 0
    assert len(successes) + len(conflicts) == 10

    with razorpay_harness.sessions() as session:
        executions = session.scalars(
            select(ExternalExecution).where(ExternalExecution.recovery_case_id == case.id)
        ).all()
        assert len(executions) == 1
        assert razorpay_harness.gateway.create_calls == 1


async def test_outcome_attribution_race(razorpay_harness: RazorpayHarness) -> None:
    # 1. Create a case
    payload = json.loads((FIXTURES / "subscription_pending.json").read_text(encoding="utf-8"))
    body, signature = sign_webhook(payload)
    await razorpay_harness.client.post(
        "/webhooks/razorpay",
        content=body,
        headers={
            "x-razorpay-signature": signature,
            "x-razorpay-event-id": "ev_Race3Setup",
            "content-type": "application/json",
        },
    )

    with razorpay_harness.sessions() as session:
        case = session.scalar(select(RecoveryCase).limit(1))
        assert case is not None
        case_id = str(case.id)

    # 2. Create payment link
    await razorpay_harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")

    with razorpay_harness.sessions() as session:
        execution = session.scalar(
            select(ExternalExecution).where(ExternalExecution.recovery_case_id == case.id)
        )
        assert execution is not None
        link_id = execution.provider_entity_id
        assert link_id is not None

    # 3. Fire 10 DIFFERENT payment_link.paid webhooks for the same link exactly concurrently
    paid_payload = json.loads((FIXTURES / "payment_link_paid.json").read_text(encoding="utf-8"))
    paid_payload["payload"]["payment_link"]["entity"]["id"] = link_id
    paid_payload["payload"]["payment_link"]["entity"]["reference_id"] = (
        execution.provider_reference_id
    )
    paid_payload["payload"]["payment_link"]["entity"]["notes"] = {
        "recoveriq_case": case_id,
        "recoveriq_correlation": str(case.correlation_id),
    }
    # Important: same payment ID so it attributes to the same payment
    paid_payload["payload"]["payment"]["entity"]["id"] = "pay_race123"

    async def fire_paid(i: int) -> Response:
        local_payload = copy.deepcopy(paid_payload)
        # DIFFERENT event IDs! So they all pass deduplication and process concurrently!
        event_id = f"ev_Race3Paid_{i}"
        local_payload["created_at"] = 1718000000 + i
        b, sig = sign_webhook(local_payload)
        return await razorpay_harness.client.post(
            "/webhooks/razorpay",
            content=b,
            headers={
                "x-razorpay-signature": sig,
                "x-razorpay-event-id": event_id,
                "content-type": "application/json",
            },
        )

    responses = await asyncio.gather(*[fire_paid(i) for i in range(10)])

    # Let's check status codes. The user said: "Assert no 500s."
    for r in responses:
        assert r.status_code in (200, 202)

    with razorpay_harness.sessions() as session:
        outcomes = session.scalars(
            select(ExternalOutcome).where(ExternalOutcome.recovery_case_id == case.id)
        ).all()
        assert len(outcomes) == 1

        attributions = session.scalars(
            select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == case.id)
        ).all()
        assert len(attributions) == 1

        updated_case = session.get(RecoveryCase, case.id)
        assert updated_case is not None
        assert updated_case.status == RecoveryCaseStatus.RECOVERED
