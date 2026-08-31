from __future__ import annotations

import copy
import hashlib
import hmac
import json
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import create_database_engine, get_db_session
from app.integrations.razorpay.dependencies import get_razorpay_gateway
from app.integrations.razorpay.fake import FakeRazorpayGateway
from app.main import app
from app.models import (
    AuditEvent,
    ExternalEntityMapping,
    ExternalExecution,
    ExternalExecutionState,
    ExternalOutcome,
    ExternalOutcomeStatus,
    ExternalWebhookEvent,
    FailureEvent,
    PaymentAttempt,
    PaymentLinkStatus,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryExecutionPlan,
    WebhookProcessingStatus,
)

FIXTURES = Path(__file__).parent / "fixtures" / "razorpay"
WEBHOOK_SECRET = "offline-webhook-secret"


@dataclass(slots=True)
class RazorpayHarness:
    client: AsyncClient
    sessions: sessionmaker[Session]
    gateway: FakeRazorpayGateway
    settings: Settings


@pytest_asyncio.fixture
async def razorpay_harness(tmp_path: Path) -> AsyncGenerator[RazorpayHarness, None]:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'razorpay-test.db'}",
        execution_environment="RAZORPAY_TEST",
        razorpay_mode="test",
        razorpay_key_id=SecretStr("rzp_test_offline"),
        razorpay_key_secret=SecretStr("offline-key-secret"),
        razorpay_webhook_secret=SecretStr(WEBHOOK_SECRET),
        celery_task_always_eager=True,
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    gateway = FakeRazorpayGateway(WEBHOOK_SECRET)

    def override_settings() -> Settings:
        return settings

    def override_session() -> Generator[Session, None, None]:
        with sessions() as session:
            yield session

    def override_gateway() -> FakeRazorpayGateway:
        return gateway

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_razorpay_gateway] = override_gateway
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield RazorpayHarness(client, sessions, gateway, settings)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _fixture(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / name).read_text(encoding="utf-8")))


async def _post_event(
    harness: RazorpayHarness,
    payload: dict[str, Any],
    event_id: str,
    *,
    raw_body: bytes | None = None,
    signature_body: bytes | None = None,
    include_signature: bool = True,
) -> Response:
    body = raw_body or json.dumps(payload, separators=(",", ":")).encode()
    signed = signature_body or body
    headers = {"x-razorpay-event-id": event_id, "content-type": "application/json"}
    if include_signature:
        headers["x-razorpay-signature"] = hmac.new(
            WEBHOOK_SECRET.encode(), signed, hashlib.sha256
        ).hexdigest()
    return await harness.client.post("/webhooks/razorpay", content=body, headers=headers)


async def _open_case(harness: RazorpayHarness, event_id: str = "evt_pending_001") -> RecoveryCase:
    response = await _post_event(harness, _fixture("subscription_pending.json"), event_id=event_id)
    assert response.status_code == 202
    with harness.sessions() as session:
        recovery_case = session.scalar(select(RecoveryCase))
        assert recovery_case is not None
        session.expunge(recovery_case)
        return recovery_case


def _link_event(
    fixture_name: str,
    execution: ExternalExecution,
    recovery_case: RecoveryCase,
) -> dict[str, Any]:
    payload = _fixture(fixture_name)
    entity = payload["payload"]["payment_link"]["entity"]
    entity["id"] = execution.provider_entity_id
    entity["reference_id"] = execution.provider_reference_id
    entity["amount"] = execution.amount_minor
    if payload["event"] == "payment_link.paid":
        entity["amount_paid"] = execution.amount_minor
    entity["currency"] = execution.currency
    entity["notes"]["recoveriq_case"] = str(recovery_case.id)
    entity["notes"]["recoveriq_correlation"] = str(recovery_case.correlation_id)
    return payload


def _order_failure_event(
    *,
    order_id: str | None,
    amount_minor: int,
    currency: str,
    payment_id: str = "pay_test_recovery_attempt_failed",
) -> dict[str, Any]:
    payload = copy.deepcopy(_fixture("subscription_pending.json"))
    payload["event"] = "payment.failed"
    payload["contains"] = ["payment"]
    payload["payload"].pop("subscription", None)
    payment = payload["payload"]["payment"]["entity"]
    payment["id"] = payment_id
    payment["amount"] = amount_minor
    payment["currency"] = currency
    payment.pop("subscription_id", None)
    if order_id is None:
        payment.pop("order_id", None)
    else:
        payment["order_id"] = order_id
    return payload


@pytest.mark.asyncio
async def test_status_is_safe_and_explicitly_test_only(
    razorpay_harness: RazorpayHarness,
) -> None:
    response = await razorpay_harness.client.get("/api/integrations/razorpay/status")
    body = response.json()

    assert response.status_code == 200
    assert body["execution_environment"] == "RAZORPAY_TEST"
    assert body["provider_mode"] == "test"
    assert body["api_configured"] is True
    assert body["live_mode_available"] is False
    assert not any("secret" in key or "key_id" in key for key in body)
    assert body["capabilities"]["CREATE_PAYMENT_LINK"] == "REAL_TEST_EXECUTION"
    assert body["capabilities"]["SEND_NUDGE"] == "RECOMMENDATION_ONLY"


@pytest.mark.asyncio
async def test_recovery_case_explanation_is_allowlisted_and_non_authoritative(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness, "evt_explanation_case")

    response = await razorpay_harness.client.post(
        f"/api/recovery-cases/{recovery_case.id}/explanation"
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"summary", "factors", "confidence", "limitations"}
    assert body["summary"]
    assert body["factors"]
    assert body["limitations"]
    assert 0 <= body["confidence"] <= 1
    forbidden = {
        "selected_action",
        "policy_result",
        "execute",
        "payment_link",
        "recovery_outcome",
    }
    assert not forbidden.intersection(body)


@pytest.mark.asyncio
async def test_invalid_request_shapes_and_unknown_case_ids_are_safe(
    razorpay_harness: RazorpayHarness,
) -> None:
    invalid_limit = await razorpay_harness.client.get("/api/recovery-cases?limit=0")
    invalid_uuid = await razorpay_harness.client.get("/api/recovery-cases/not-a-uuid")
    missing_case = await razorpay_harness.client.get(
        "/api/recovery-cases/00000000-0000-0000-0000-000000000001"
    )
    missing_execution = await razorpay_harness.client.post(
        "/api/recovery-cases/00000000-0000-0000-0000-000000000001/test-payment-link"
    )

    assert invalid_limit.status_code == 422
    assert invalid_uuid.status_code == 422
    assert missing_case.status_code == 404
    assert missing_case.json() == {"detail": "recovery case not found"}
    assert missing_execution.status_code == 404
    assert missing_execution.json() == {"detail": "recovery case not found"}
    assert razorpay_harness.gateway.create_calls == 0


@pytest.mark.asyncio
async def test_malformed_non_object_and_oversized_webhooks_are_rejected(
    razorpay_harness: RazorpayHarness,
) -> None:
    malformed = await _post_event(
        razorpay_harness,
        {},
        "evt_malformed_json",
        raw_body=b"{not-json",
    )
    non_object = await _post_event(
        razorpay_harness,
        {},
        "evt_non_object_json",
        raw_body=b"[]",
    )
    oversized = await razorpay_harness.client.post(
        "/webhooks/razorpay",
        content=b"x" * 1_048_577,
        headers={
            "x-razorpay-event-id": "evt_oversized",
            "x-razorpay-signature": "not-evaluated-before-size-rejection",
            "content-type": "application/json",
        },
    )

    assert malformed.status_code == 400
    assert malformed.json() == {"detail": "invalid JSON webhook body"}
    assert non_object.status_code == 400
    assert non_object.json() == {"detail": "webhook body must be a JSON object"}
    assert oversized.status_code == 413
    assert oversized.json() == {"detail": "webhook body exceeds size limit"}
    with razorpay_harness.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ExternalWebhookEvent)) == 0


@pytest.mark.asyncio
async def test_missing_and_invalid_webhook_signatures_are_rejected(
    razorpay_harness: RazorpayHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _fixture("subscription_pending.json")
    missing = await _post_event(
        razorpay_harness, payload, "evt_missing_sig", include_signature=False
    )
    invalid = await razorpay_harness.client.post(
        "/webhooks/razorpay",
        content=json.dumps(payload).encode(),
        headers={
            "x-razorpay-event-id": "evt_invalid_sig",
            "x-razorpay-signature": "invalid",
            "content-type": "application/json",
        },
    )

    assert missing.status_code == 400
    assert invalid.status_code == 401
    with razorpay_harness.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ExternalWebhookEvent)) == 0
    captured = capsys.readouterr().out
    assert WEBHOOK_SECRET not in captured
    assert "offline-key-secret" not in captured


@pytest.mark.asyncio
async def test_signature_cannot_be_reused_for_different_raw_json_representation(
    razorpay_harness: RazorpayHarness,
) -> None:
    payload = _fixture("subscription_pending.json")
    compact = json.dumps(payload, separators=(",", ":")).encode()
    pretty = json.dumps(payload, indent=2).encode()

    response = await _post_event(
        razorpay_harness,
        payload,
        "evt_raw_mismatch",
        raw_body=pretty,
        signature_body=compact,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unknown_event_is_durably_and_safely_ignored(
    razorpay_harness: RazorpayHarness,
) -> None:
    payload = {"entity": "event", "event": "future.unknown", "created_at": 1700000000}
    response = await _post_event(razorpay_harness, payload, "evt_unknown")

    assert response.status_code == 202
    with razorpay_harness.sessions() as session:
        event = session.scalar(select(ExternalWebhookEvent))
        assert event is not None
        assert event.processing_status is WebhookProcessingStatus.IGNORED
        assert event.failure_reason == "UNKNOWN_EVENT"


@pytest.mark.asyncio
async def test_pending_opens_one_case_and_redacts_unneeded_pii(
    razorpay_harness: RazorpayHarness,
) -> None:
    await _open_case(razorpay_harness)

    with razorpay_harness.sessions() as session:
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
        recovery_case = session.scalar(select(RecoveryCase))
        event = session.scalar(select(ExternalWebhookEvent))
        assert recovery_case is not None
        assert recovery_case.status is RecoveryCaseStatus.HUMAN_REVIEW
        assert event is not None
        serialized = json.dumps(event.redacted_payload)
        assert "redacted-test@example.invalid" not in serialized
        assert "+910000000000" not in serialized

    response = await razorpay_harness.client.get(f"/api/recovery-cases/{recovery_case.id}")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "HUMAN_REVIEW"
    assert body["decisions"][0]["reason"] == "INSUFFICIENT_CONTEXT"
    assert body["decisions"][0]["context_metadata"]["inference_permitted"] is False


@pytest.mark.asyncio
async def test_subscription_payment_failed_still_opens_one_case(
    razorpay_harness: RazorpayHarness,
) -> None:
    payload = _fixture("subscription_pending.json")
    payload["event"] = "payment.failed"

    response = await _post_event(razorpay_harness, payload, "evt_subscription_failed")

    assert response.status_code == 202
    with razorpay_harness.sessions() as session:
        event = session.scalar(select(ExternalWebhookEvent))
        recovery_case = session.scalar(select(RecoveryCase))
        assert event is not None and recovery_case is not None
        assert event.processing_status is WebhookProcessingStatus.PROCESSED
        assert event.failure_reason is None
        assert recovery_case.status is RecoveryCaseStatus.HUMAN_REVIEW
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
        assert session.scalar(select(func.count()).select_from(FailureEvent)) == 1


@pytest.mark.asyncio
async def test_duplicate_event_id_is_acknowledged_without_duplicate_side_effects(
    razorpay_harness: RazorpayHarness,
) -> None:
    payload = _fixture("subscription_pending.json")
    first = await _post_event(razorpay_harness, payload, "evt_duplicate")
    with razorpay_harness.sessions() as session:
        audit_count = session.scalar(select(func.count()).select_from(AuditEvent))
    second = await _post_event(razorpay_harness, payload, "evt_duplicate")

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json() == {"status": "duplicate"}
    with razorpay_harness.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ExternalWebhookEvent)) == 1
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count


@pytest.mark.asyncio
async def test_operator_payment_link_is_idempotent_and_auditable(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    path = f"/api/recovery-cases/{recovery_case.id}/test-payment-link"

    first = await razorpay_harness.client.post(path)
    second = await razorpay_harness.client.post(path)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["state"] == "SUCCEEDED"
    assert first.json()["payment_link_status"] == "ISSUED"
    assert razorpay_harness.gateway.create_calls == 1
    with razorpay_harness.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ExternalExecution)) == 1
        plans = session.scalars(select(RecoveryExecutionPlan)).all()
        operator_plans = [plan for plan in plans if plan.action == "CREATE_PAYMENT_LINK"]
        assert len(operator_plans) == 1
        assert operator_plans[0].initiator.value == "OPERATOR_INITIATED"
        audit_types = set(session.scalars(select(AuditEvent.event_type)).all())
        assert "OPERATOR_APPROVED_EXECUTION_FALLBACK" in audit_types
        assert "PAYMENT_LINK_RETURNED" in audit_types


@pytest.mark.asyncio
async def test_mapped_order_failure_attaches_to_existing_executing_case_once(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness, "evt_order_failure_case")
    link_response = await razorpay_harness.client.post(
        f"/api/recovery-cases/{recovery_case.id}/test-payment-link"
    )
    assert link_response.status_code == 200
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        order_mapping = session.scalar(
            select(ExternalEntityMapping).where(
                ExternalEntityMapping.external_entity_type == "order"
            )
        )
        assert execution is not None and order_mapping is not None
        assert order_mapping.local_entity_type == "ExternalExecution"
        assert order_mapping.local_entity_id == execution.id
        payload = _order_failure_event(
            order_id=order_mapping.external_entity_id,
            amount_minor=execution.amount_minor,
            currency=execution.currency,
        )

    first = await _post_event(razorpay_harness, payload, "evt_order_failure")
    duplicate = await _post_event(razorpay_harness, payload, "evt_order_failure")

    assert first.status_code == 202
    assert duplicate.status_code == 200
    assert duplicate.json() == {"status": "duplicate"}
    assert razorpay_harness.gateway.create_calls == 1
    with razorpay_harness.sessions() as session:
        stored_case = session.get(RecoveryCase, recovery_case.id)
        event = session.scalar(
            select(ExternalWebhookEvent).where(
                ExternalWebhookEvent.provider_event_id == "evt_order_failure"
            )
        )
        assert stored_case is not None and event is not None
        assert stored_case.status is RecoveryCaseStatus.EXECUTING
        assert event.processing_status is WebhookProcessingStatus.PROCESSED
        assert event.correlation_id == stored_case.correlation_id
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
        assert session.scalar(select(func.count()).select_from(ExternalExecution)) == 1
        assert session.scalar(select(func.count()).select_from(ExternalOutcome)) == 0
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(FailureEvent)
                .where(FailureEvent.webhook_event_id == event.id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(PaymentAttempt)
                .where(
                    PaymentAttempt.external_id
                    == "razorpay-attempt:pay_test_recovery_attempt_failed"
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.correlation_id == stored_case.correlation_id,
                    AuditEvent.event_type == "RECOVERY_PAYMENT_ATTEMPT_FAILED",
                )
            )
            == 1
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("order_id", "expected_reason"),
    [
        (None, "MISSING_SUBSCRIPTION_AND_ORDER_ID"),
        ("order_unknown", "UNMATCHED_PAYMENT_ORDER"),
    ],
)
async def test_unmapped_order_failures_are_safely_ignored(
    razorpay_harness: RazorpayHarness,
    order_id: str | None,
    expected_reason: str,
) -> None:
    recovery_case = await _open_case(razorpay_harness, f"evt_unmapped_case_{expected_reason}")
    await razorpay_harness.client.post(f"/api/recovery-cases/{recovery_case.id}/test-payment-link")
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        assert execution is not None
        payload = _order_failure_event(
            order_id=order_id,
            amount_minor=execution.amount_minor,
            currency=execution.currency,
        )

    response = await _post_event(
        razorpay_harness, payload, f"evt_unmapped_failure_{expected_reason}"
    )

    assert response.status_code == 202
    assert razorpay_harness.gateway.create_calls == 1
    with razorpay_harness.sessions() as session:
        event = session.scalar(
            select(ExternalWebhookEvent).where(
                ExternalWebhookEvent.provider_event_id == f"evt_unmapped_failure_{expected_reason}"
            )
        )
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert event is not None and stored_case is not None
        assert event.processing_status is WebhookProcessingStatus.IGNORED
        assert event.failure_reason == expected_reason
        assert stored_case.status is RecoveryCaseStatus.EXECUTING
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
        assert session.scalar(select(func.count()).select_from(ExternalExecution)) == 1
        assert session.scalar(select(func.count()).select_from(ExternalOutcome)) == 0
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "RECOVERY_PAYMENT_ATTEMPT_FAILED")
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mismatch", "expected_reason"),
    [
        ("amount", "PAYMENT_FAILURE_AMOUNT_MISMATCH"),
        ("currency", "PAYMENT_FAILURE_CURRENCY_MISMATCH"),
    ],
)
async def test_mapped_order_failure_mismatches_are_rejected(
    razorpay_harness: RazorpayHarness,
    mismatch: str,
    expected_reason: str,
) -> None:
    recovery_case = await _open_case(razorpay_harness, f"evt_mismatch_case_{mismatch}")
    await razorpay_harness.client.post(f"/api/recovery-cases/{recovery_case.id}/test-payment-link")
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        order_mapping = session.scalar(
            select(ExternalEntityMapping).where(
                ExternalEntityMapping.external_entity_type == "order"
            )
        )
        assert execution is not None and order_mapping is not None
        payload = _order_failure_event(
            order_id=order_mapping.external_entity_id,
            amount_minor=(
                execution.amount_minor + 1 if mismatch == "amount" else execution.amount_minor
            ),
            currency="USD" if mismatch == "currency" else execution.currency,
        )

    response = await _post_event(razorpay_harness, payload, f"evt_mismatch_{mismatch}")

    assert response.status_code == 202
    with razorpay_harness.sessions() as session:
        event = session.scalar(
            select(ExternalWebhookEvent).where(
                ExternalWebhookEvent.provider_event_id == f"evt_mismatch_{mismatch}"
            )
        )
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert event is not None and stored_case is not None
        assert event.processing_status is WebhookProcessingStatus.IGNORED
        assert event.failure_reason == expected_reason
        assert stored_case.status is RecoveryCaseStatus.EXECUTING
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
        assert session.scalar(select(func.count()).select_from(ExternalExecution)) == 1
        assert session.scalar(select(func.count()).select_from(ExternalOutcome)) == 0
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(FailureEvent)
                .where(FailureEvent.webhook_event_id == event.id)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_operator_payment_link_is_unavailable_in_simulation(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    simulation_settings = razorpay_harness.settings.model_copy(
        update={"execution_environment": "SIMULATION"}
    )
    app.dependency_overrides[get_settings] = lambda: simulation_settings

    response = await razorpay_harness.client.post(
        f"/api/recovery-cases/{recovery_case.id}/test-payment-link"
    )

    assert response.status_code == 409
    assert razorpay_harness.gateway.create_calls == 0


@pytest.mark.asyncio
async def test_paid_payment_link_recovers_once_and_preserves_subscription_state(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    link_response = await razorpay_harness.client.post(
        f"/api/recovery-cases/{recovery_case.id}/test-payment-link"
    )
    assert link_response.status_code == 200
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert execution is not None and stored_case is not None
        payload = _link_event("payment_link_paid.json", execution, stored_case)
    first = await _post_event(razorpay_harness, payload, "evt_link_paid")
    duplicate_id = await _post_event(razorpay_harness, payload, "evt_link_paid")
    replay_new_id = await _post_event(razorpay_harness, payload, "evt_link_paid_replay")

    assert first.status_code == 202
    assert duplicate_id.status_code == 200
    assert replay_new_id.status_code == 202
    with razorpay_harness.sessions() as session:
        stored_case = session.get(RecoveryCase, recovery_case.id)
        execution = session.scalar(select(ExternalExecution))
        assert stored_case is not None and execution is not None
        assert stored_case.status is RecoveryCaseStatus.RECOVERED
        assert stored_case.payment.subscription.status == "pending"
        assert execution.payment_link_status is PaymentLinkStatus.PAID
        outcome = session.scalar(select(ExternalOutcome))
        assert outcome is not None
        assert outcome.status is ExternalOutcomeStatus.PAID
        assert outcome.verified is True
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 1
        audit_types = set(
            session.scalars(
                select(AuditEvent.event_type).where(
                    AuditEvent.correlation_id == stored_case.correlation_id
                )
            ).all()
        )
        assert {
            "WEBHOOK_RECEIVED",
            "WEBHOOK_SIGNATURE_VALIDATED",
            "EXTERNAL_ENTITY_NORMALIZED",
            "RECOVERY_CASE_CREATED",
            "FEATURE_CONTEXT_ADAPTED",
            "MODEL_V2_INFERENCE_REVIEWED",
            "POLICY_V2_DECISION_RECORDED",
            "EXECUTION_CAPABILITY_RESOLVED",
            "OPERATOR_APPROVED_EXECUTION_FALLBACK",
            "PAYMENT_LINK_CREATE_REQUESTED",
            "PAYMENT_LINK_RETURNED",
            "EXTERNAL_OUTCOME_VERIFIED",
            "RAZORPAY_TEST_RECOVERY_ATTRIBUTED",
            "RECOVERY_CASE_TRANSITIONED_RECOVERED",
        }.issubset(audit_types)


@pytest.mark.asyncio
async def test_paid_link_uses_completion_time_and_exposes_real_last_activity(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness, "evt_timestamp_case")
    await razorpay_harness.client.post(f"/api/recovery-cases/{recovery_case.id}/test-payment-link")
    link_created_at = 1_690_000_000
    payment_created_at = 1_700_000_100
    link_paid_at = 1_700_000_200
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert execution is not None and stored_case is not None
        payload = _link_event("payment_link_paid.json", execution, stored_case)
        expected_amount_minor = execution.amount_minor
    payload["created_at"] = link_created_at
    link_entity = payload["payload"]["payment_link"]["entity"]
    link_entity["created_at"] = link_created_at
    link_entity["updated_at"] = link_paid_at
    payload["payload"]["payment"]["entity"]["created_at"] = payment_created_at

    response = await _post_event(razorpay_harness, payload, "evt_paid_later_than_link")

    assert response.status_code == 202
    expected_completion_utc = datetime.fromtimestamp(link_paid_at, UTC)
    expected_completion = expected_completion_utc.replace(tzinfo=None)
    old_link_creation = datetime.fromtimestamp(link_created_at, UTC).replace(tzinfo=None)
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        outcome = session.scalar(select(ExternalOutcome))
        attribution = session.scalar(select(RecoveryAttribution))
        assert execution is not None and outcome is not None and attribution is not None
        assert execution.completed_at == expected_completion
        assert outcome.occurred_at == expected_completion
        assert attribution.created_at > old_link_creation
        expected_attribution_created_at = attribution.created_at

        # Simulate the pre-hardening row without rewriting provider payload evidence.
        outcome.occurred_at = old_link_creation
        session.commit()

    detail = await razorpay_harness.client.get(f"/api/recovery-cases/{recovery_case.id}")
    summary = await razorpay_harness.client.get("/api/recovery-cases")

    assert detail.status_code == 200
    detail_body = detail.json()
    assert (
        datetime.fromisoformat(detail_body["outcomes"][0]["occurred_at"]) == expected_completion_utc
    )
    assert detail_body["outcomes"][0]["occurred_at"] != old_link_creation.isoformat()
    assert detail_body["outcomes"][0]["created_at"]
    assert detail_body["attribution"]["created_at"]
    assert summary.status_code == 200
    summary_body = summary.json()[0]
    assert summary_body["verified_recovery_minor"] == expected_amount_minor
    assert (
        datetime.fromisoformat(summary_body["verified_recovery_at"])
        == expected_attribution_created_at
    )
    assert datetime.fromisoformat(summary_body["last_activity_at"]) > datetime.fromisoformat(
        summary_body["created_at"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["reference", "amount"])
async def test_paid_link_mismatch_does_not_recover_case(
    razorpay_harness: RazorpayHarness,
    mismatch: str,
) -> None:
    recovery_case = await _open_case(razorpay_harness, f"evt_pending_{mismatch}")
    await razorpay_harness.client.post(f"/api/recovery-cases/{recovery_case.id}/test-payment-link")
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert execution is not None and stored_case is not None
        payload = _link_event("payment_link_paid.json", execution, stored_case)
    entity = payload["payload"]["payment_link"]["entity"]
    if mismatch == "reference":
        entity["reference_id"] = "unrelated_reference"
    else:
        entity["amount"] = entity["amount"] + 1
        entity["amount_paid"] = entity["amount"]
    await _post_event(razorpay_harness, payload, f"evt_paid_mismatch_{mismatch}")

    with razorpay_harness.sessions() as session:
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert stored_case is not None
        assert stored_case.status is not RecoveryCaseStatus.RECOVERED
        assert session.scalar(select(func.count()).select_from(ExternalOutcome)) == 0
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture_name", "event_id", "expected_state", "expected_link_status"),
    [
        (
            "payment_link_expired.json",
            "evt_link_expired",
            ExternalExecutionState.FAILED,
            PaymentLinkStatus.EXPIRED,
        ),
        (
            "payment_link_cancelled.json",
            "evt_link_cancelled",
            ExternalExecutionState.CANCELLED,
            PaymentLinkStatus.CANCELLED,
        ),
    ],
)
async def test_terminal_payment_link_is_not_recovered(
    razorpay_harness: RazorpayHarness,
    fixture_name: str,
    event_id: str,
    expected_state: ExternalExecutionState,
    expected_link_status: PaymentLinkStatus,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    await razorpay_harness.client.post(f"/api/recovery-cases/{recovery_case.id}/test-payment-link")
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert execution is not None and stored_case is not None
        payload = _link_event(fixture_name, execution, stored_case)
    await _post_event(razorpay_harness, payload, event_id)

    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert execution is not None and stored_case is not None
        assert execution.state is expected_state
        assert execution.payment_link_status is expected_link_status
        assert stored_case.status is RecoveryCaseStatus.FAILED
        assert session.scalar(select(func.count()).select_from(ExternalOutcome)) == 1
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 0


@pytest.mark.asyncio
async def test_subscription_charged_attributes_recovery_exactly_once(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    charged = _fixture("subscription_charged.json")
    await _post_event(razorpay_harness, charged, "evt_charged")
    await _post_event(razorpay_harness, charged, "evt_charged_replay")

    with razorpay_harness.sessions() as session:
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert stored_case is not None
        assert stored_case.status is RecoveryCaseStatus.RECOVERED
        assert stored_case.payment.subscription.status == "active"
        outcome = session.scalar(select(ExternalOutcome))
        assert outcome is not None
        assert outcome.status is ExternalOutcomeStatus.CHARGED
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 1


@pytest.mark.asyncio
async def test_newer_charged_then_older_pending_does_not_regress_or_open_case(
    razorpay_harness: RazorpayHarness,
) -> None:
    charged = _fixture("subscription_charged.json")
    pending = _fixture("subscription_pending.json")
    await _post_event(razorpay_harness, charged, "evt_out_of_order_charged")
    await _post_event(razorpay_harness, pending, "evt_out_of_order_pending")

    with razorpay_harness.sessions() as session:
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 0
        events = session.scalars(select(ExternalWebhookEvent)).all()
        ignored = [event for event in events if event.event_type == "subscription.pending"]
        assert ignored[0].processing_status is WebhookProcessingStatus.IGNORED
        assert ignored[0].failure_reason == "STALE_SUBSCRIPTION_EVENT"


@pytest.mark.asyncio
async def test_timeout_after_create_reconciles_without_second_create(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    razorpay_harness.gateway.create_failure = "timeout_after"

    response = await razorpay_harness.client.post(
        f"/api/recovery-cases/{recovery_case.id}/test-payment-link"
    )

    assert response.status_code == 200
    assert response.json()["state"] == "SUCCEEDED"
    assert razorpay_harness.gateway.create_calls == 1
    assert razorpay_harness.gateway.fetch_calls == 1


@pytest.mark.asyncio
async def test_timeout_before_create_stays_unknown_and_blocks_replacement(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    razorpay_harness.gateway.create_failure = "timeout_before"
    path = f"/api/recovery-cases/{recovery_case.id}/test-payment-link"

    first = await razorpay_harness.client.post(path)
    second = await razorpay_harness.client.post(path)

    assert first.json()["state"] == "UNKNOWN"
    assert second.json()["state"] == "UNKNOWN"
    assert razorpay_harness.gateway.create_calls == 1
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        assert execution is not None
        assert execution.failure_category == "RECONCILIATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_permanent_payment_link_failure_is_not_retried(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    razorpay_harness.gateway.create_failure = "permanent"
    path = f"/api/recovery-cases/{recovery_case.id}/test-payment-link"

    first = await razorpay_harness.client.post(path)
    second = await razorpay_harness.client.post(path)

    assert first.json()["state"] == "FAILED"
    assert second.json()["state"] == "FAILED"
    assert razorpay_harness.gateway.create_calls == 1


@pytest.mark.asyncio
async def test_paid_then_stale_pending_cannot_regress_recovered_case(
    razorpay_harness: RazorpayHarness,
) -> None:
    recovery_case = await _open_case(razorpay_harness)
    await razorpay_harness.client.post(f"/api/recovery-cases/{recovery_case.id}/test-payment-link")
    with razorpay_harness.sessions() as session:
        execution = session.scalar(select(ExternalExecution))
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert execution is not None and stored_case is not None
        paid = _link_event("payment_link_paid.json", execution, stored_case)
    await _post_event(razorpay_harness, paid, "evt_paid_before_stale")
    stale = copy.deepcopy(_fixture("subscription_pending.json"))
    stale["created_at"] = 1699999999
    await _post_event(razorpay_harness, stale, "evt_stale_pending_after_paid")

    with razorpay_harness.sessions() as session:
        stored_case = session.get(RecoveryCase, recovery_case.id)
        assert stored_case is not None
        assert stored_case.status is RecoveryCaseStatus.RECOVERED
        assert session.scalar(select(func.count()).select_from(RecoveryAttribution)) == 1


@pytest.mark.asyncio
async def test_reprocessing_completed_event_is_idempotent_worker_retry(
    razorpay_harness: RazorpayHarness,
) -> None:
    await _open_case(razorpay_harness)
    with razorpay_harness.sessions() as session:
        event = session.scalar(select(ExternalWebhookEvent))
        assert event is not None
        event_id = event.id
    with razorpay_harness.sessions() as session:
        from app.services.razorpay_webhooks import process_webhook_event

        process_webhook_event(session, event_id)

    with razorpay_harness.sessions() as session:
        assert session.scalar(select(func.count()).select_from(RecoveryCase)) == 1
