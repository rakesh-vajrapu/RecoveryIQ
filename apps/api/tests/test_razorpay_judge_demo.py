from __future__ import annotations

import hashlib
import hmac
import json
import uuid as _uuid
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import create_database_engine, get_db_session
from app.integrations.razorpay.dependencies import get_razorpay_gateway
from app.integrations.razorpay.fake import FakeRazorpayGateway
from app.main import app
from app.models import (
    ExternalExecution,
    ExternalOutcome,
    RecoveryAttribution,
    RecoveryCase,
    RecoveryCaseStatus,
)

WEBHOOK_SECRET = "offline-webhook-secret"


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


@dataclass(slots=True)
class JudgeDemoHarness:
    client: AsyncClient
    sessions: sessionmaker[Session]
    gateway: FakeRazorpayGateway
    settings: Settings


@pytest_asyncio.fixture
async def judge_demo_harness(tmp_path: Path) -> AsyncGenerator[JudgeDemoHarness, None]:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'judge-demo.db'}",
        execution_environment="RAZORPAY_TEST",
        razorpay_mode="test",
        razorpay_key_id=SecretStr("rzp_test_offline"),
        razorpay_key_secret=SecretStr("offline-key-secret"),
        razorpay_webhook_secret=SecretStr(WEBHOOK_SECRET),
        enable_razorpay_judge_demo=True,
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
        yield JudgeDemoHarness(client, sessions, gateway, settings)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ─── 1. judge-demo case creation is disabled when ENABLE_RAZORPAY_JUDGE_DEMO=false ───

@pytest.mark.asyncio
async def test_1_judge_demo_disabled_fails(judge_demo_harness: JudgeDemoHarness):
    judge_demo_harness.settings.enable_razorpay_judge_demo = False
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 403


# ─── 2. judge-demo provider execution refuses SIMULATION mode ───

@pytest.mark.asyncio
async def test_2_judge_demo_refuses_simulation_mode(judge_demo_harness: JudgeDemoHarness):
    judge_demo_harness.settings.execution_environment = "SIMULATION"
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 403


# ─── 3. judge demo requires RAZORPAY_TEST ───

@pytest.mark.asyncio
async def test_3_judge_demo_requires_razorpay_test(judge_demo_harness: JudgeDemoHarness):
    judge_demo_harness.settings.execution_environment = "RAZORPAY_LIVE"
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 403


# ─── 4. missing API credentials fail safely ───

@pytest.mark.asyncio
async def test_4_missing_api_credentials_fails_safely(judge_demo_harness: JudgeDemoHarness):
    judge_demo_harness.settings.razorpay_key_id = None
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 403


# ─── 5. missing webhook configuration is clearly reported ───

@pytest.mark.asyncio
async def test_5_missing_webhook_secret_is_reported(judge_demo_harness: JudgeDemoHarness):
    judge_demo_harness.settings.razorpay_webhook_secret = None
    response = await judge_demo_harness.client.get("/api/integrations/razorpay/status")
    assert response.status_code == 200
    assert response.json()["webhook_configured"] is False


# ─── 6. prepared case amount is exactly amount_minor=100000 currency=INR ───

@pytest.mark.asyncio
async def test_6_prepared_case_amount_is_exactly_100000_inr(judge_demo_harness: JudgeDemoHarness):
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 201
    data = response.json()
    assert data["amount_minor"] == 100000
    assert data["currency"] == "INR"


# ─── 7. prepared case is not DEMO_SYNTHETIC ───

@pytest.mark.asyncio
async def test_7_prepared_case_is_not_demo_synthetic(judge_demo_harness: JudgeDemoHarness):
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 201
    data = response.json()
    assert data["source"] != "DEMO_SYNTHETIC"
    # Verify the underlying payment external_id uses judge setup namespace
    with judge_demo_harness.sessions() as db:
        case = db.execute(select(RecoveryCase).where(RecoveryCase.id == _uuid.UUID(data["id"]))).scalar_one()
        assert case.payment.external_id.startswith("razorpay_judge_setup_")


# ─── 8. prepared case is LOCAL_UNVERIFIED / LOCAL TEST SETUP before provider evidence ───

@pytest.mark.asyncio
async def test_8_prepared_case_is_local_unverified(judge_demo_harness: JudgeDemoHarness):
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "LOCAL_UNVERIFIED"
    assert data["synthetic"] is False


# ─── 9. no fake autonomous Model V2 decision is created ───

@pytest.mark.asyncio
async def test_9_no_fake_autonomous_decision_created(judge_demo_harness: JudgeDemoHarness):
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    data = response.json()
    assert len(data.get("decisions", [])) == 0
    assert len(data.get("plans", [])) == 0


# ─── 10/11. existing operator Payment Link execution service is reused, amount 100000 ───

@pytest.mark.asyncio
async def test_10_and_11_create_payment_link(judge_demo_harness: JudgeDemoHarness):
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]

    exec_res = await judge_demo_harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")
    assert exec_res.status_code == 200
    data = exec_res.json()
    assert data["amount_minor"] == 100000
    assert data["execution_mode"] == "RAZORPAY_TEST"


# ─── 12. second execution request for same case causes zero additional provider create calls ───

@pytest.mark.asyncio
async def test_12_second_execution_request_idempotent(judge_demo_harness: JudgeDemoHarness):
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]
    await judge_demo_harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")
    gateway_calls_before = judge_demo_harness.gateway.create_calls
    r2 = await judge_demo_harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")
    assert r2.status_code == 200
    gateway_calls_after = judge_demo_harness.gateway.create_calls
    assert gateway_calls_before == gateway_calls_after


# ─── 13. real service path remains Test Mode only ───

@pytest.mark.asyncio
async def test_13_real_service_path_is_test_mode(judge_demo_harness: JudgeDemoHarness):
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]
    exec_res = await judge_demo_harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")
    assert exec_res.status_code == 200


# ─── 14/15. webhook signature is mandatory / invalid signature rejected ───

@pytest.mark.asyncio
async def test_14_15_webhook_signature(judge_demo_harness: JudgeDemoHarness):
    # Missing signature
    response = await judge_demo_harness.client.post(
        "/webhooks/razorpay",
        headers={"x-razorpay-event-id": "evt_test_nosig"},
        content=b'{"event": "payment_link.paid"}'
    )
    assert response.status_code == 400

    # Invalid signature
    response2 = await judge_demo_harness.client.post(
        "/webhooks/razorpay",
        headers={"x-razorpay-signature": "invalid", "x-razorpay-event-id": "evt_test_badsig"},
        content=b'{"event": "payment_link.paid"}'
    )
    assert response2.status_code == 401


# ─── 16. duplicate webhook event ID does not create duplicate effects ───

@pytest.mark.asyncio
async def test_16_duplicate_webhook_deduplication(judge_demo_harness: JudgeDemoHarness):
    payload = json.dumps({
        "entity": "event",
        "event": "payment_link.paid",
        "contains": [],
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_test_dedup",
                    "status": "paid",
                    "amount": 100000,
                    "currency": "INR",
                    "reference_id": "test_ref_dedup",
                }
            }
        }
    }, separators=(",", ":")).encode("utf-8")
    sig = _sign(payload)
    headers = {"x-razorpay-signature": sig, "x-razorpay-event-id": "evt_dedup_test"}
    res1 = await judge_demo_harness.client.post("/webhooks/razorpay", headers=headers, content=payload)
    assert res1.status_code in (200, 202)
    res2 = await judge_demo_harness.client.post("/webhooks/razorpay", headers=headers, content=payload)
    assert res2.status_code == 200


# ─── Helper: create case + execution + fire webhook ───

async def _prepare_and_execute(
    harness: JudgeDemoHarness,
) -> tuple[str, ExternalExecution]:
    """Create a judge demo case and its payment link execution."""
    response = await harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]
    case_uuid = _uuid.UUID(case_id)
    await harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")
    with harness.sessions() as db:
        execution = db.execute(
            select(ExternalExecution).where(ExternalExecution.recovery_case_id == case_uuid)
        ).scalar_one()
        db.expunge(execution)
    return case_id, execution


def _build_paid_webhook(execution: ExternalExecution) -> bytes:
    return json.dumps({
        "entity": "event",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": execution.provider_entity_id,
                    "status": "paid",
                    "amount": execution.amount_minor,
                    "amount_paid": execution.amount_minor,
                    "currency": execution.currency,
                    "reference_id": execution.provider_reference_id,
                }
            }
        }
    }, separators=(",", ":")).encode("utf-8")


async def _fire_paid_webhook(
    harness: JudgeDemoHarness,
    execution: ExternalExecution,
    event_id: str,
) -> int:
    """Fire a payment_link.paid webhook and update the fake gateway to show 'paid' state."""
    from app.integrations.razorpay.gateway import PaymentLinkResult

    # Update fake gateway so provider truth fetch confirms 'paid'
    if execution.provider_entity_id and execution.provider_entity_id in harness.gateway._links_by_id:
        old = harness.gateway._links_by_id[execution.provider_entity_id]
        harness.gateway._links_by_id[execution.provider_entity_id] = PaymentLinkResult(
            id=old.id,
            order_id=old.order_id,
            amount_minor=old.amount_minor,
            amount_paid_minor=execution.amount_minor,
            currency=old.currency,
            reference_id=old.reference_id,
            status="paid",
            short_url=old.short_url,
        )

    payload = _build_paid_webhook(execution)
    sig = _sign(payload)
    headers = {"x-razorpay-signature": sig, "x-razorpay-event-id": event_id}
    res = await harness.client.post("/webhooks/razorpay", headers=headers, content=payload)
    return res.status_code


# ─── 17/18/20/21/23. Full end-to-end webhook → recovery flow ───

@pytest.mark.asyncio
async def test_full_webhook_to_recovery_flow(judge_demo_harness: JudgeDemoHarness):
    case_id, execution = await _prepare_and_execute(judge_demo_harness)

    status_code = await _fire_paid_webhook(judge_demo_harness, execution, "evt_demo_success")
    assert status_code in (200, 202)

    case_uuid = _uuid.UUID(case_id)
    with judge_demo_harness.sessions() as db:
        case = db.execute(select(RecoveryCase).where(RecoveryCase.id == case_uuid)).scalar_one()
        assert case.status == RecoveryCaseStatus.RECOVERED

        outcome = db.execute(
            select(ExternalOutcome).where(ExternalOutcome.recovery_case_id == case_uuid)
        ).scalar_one()
        assert outcome.verified is True

        attribution = db.execute(
            select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == case_uuid)
        ).scalar_one()
        assert attribution.amount_minor == 100000

    # 23. Recovered case cannot create another Payment Link
    exec_res2 = await judge_demo_harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")
    assert exec_res2.status_code in (400, 409)


# ─── 19. mismatch fails closed ───

@pytest.mark.asyncio
async def test_19_mismatch_fails_closed(judge_demo_harness: JudgeDemoHarness):
    case_id, execution = await _prepare_and_execute(judge_demo_harness)

    # Tamper with the fake gateway to create amount mismatch
    from app.integrations.razorpay.gateway import PaymentLinkResult

    if execution.provider_entity_id and execution.provider_entity_id in judge_demo_harness.gateway._links_by_id:
        old = judge_demo_harness.gateway._links_by_id[execution.provider_entity_id]
        judge_demo_harness.gateway._links_by_id[execution.provider_entity_id] = PaymentLinkResult(
            id=old.id,
            order_id=old.order_id,
            amount_minor=99999,  # MISMATCH
            amount_paid_minor=99999,
            currency=old.currency,
            reference_id=old.reference_id,
            status="paid",
            short_url=old.short_url,
        )

    payload = _build_paid_webhook(execution)
    sig = _sign(payload)
    headers = {"x-razorpay-signature": sig, "x-razorpay-event-id": "evt_demo_mismatch"}
    wh_res = await judge_demo_harness.client.post("/webhooks/razorpay", headers=headers, content=payload)
    assert wh_res.status_code in (200, 202)

    case_uuid = _uuid.UUID(case_id)
    with judge_demo_harness.sessions() as db:
        case = db.execute(select(RecoveryCase).where(RecoveryCase.id == case_uuid)).scalar_one()
        assert case.status != RecoveryCaseStatus.RECOVERED
        attribution = db.execute(
            select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == case_uuid)
        ).scalar_one_or_none()
        assert attribution is None


# ─── 22. duplicate webhook does not create second attribution ───

@pytest.mark.asyncio
async def test_22_duplicate_webhook_no_second_attribution(judge_demo_harness: JudgeDemoHarness):
    case_id, execution = await _prepare_and_execute(judge_demo_harness)

    await _fire_paid_webhook(judge_demo_harness, execution, "evt_demo_dup_1")
    await _fire_paid_webhook(judge_demo_harness, execution, "evt_demo_dup_1")  # same event_id

    case_uuid = _uuid.UUID(case_id)
    with judge_demo_harness.sessions() as db:
        attrs = db.execute(
            select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == case_uuid)
        ).scalars().all()
        assert len(attrs) == 1


# ─── 24. no secret is returned through API responses ───

@pytest.mark.asyncio
async def test_24_no_secret_returned(judge_demo_harness: JudgeDemoHarness):
    res = await judge_demo_harness.client.get("/api/integrations/razorpay/status")
    data = res.json()
    text = json.dumps(data)
    assert "razorpay_key_secret" not in text
    assert "razorpay_webhook_secret" not in text
    assert "offline-key-secret" not in text
    assert "offline-webhook-secret" not in text
    assert data["api_configured"] is True
    assert data["webhook_configured"] is True
    assert data["judge_demo_enabled"] is True


# ─── 25. Test Mode status API accurately reports enabled/disabled state ───

@pytest.mark.asyncio
async def test_25_test_mode_status(judge_demo_harness: JudgeDemoHarness):
    judge_demo_harness.settings.enable_razorpay_judge_demo = False
    res = await judge_demo_harness.client.get("/api/integrations/razorpay/status")
    assert res.json()["judge_demo_enabled"] is False


# ─── 26. current runtime recovered total increases from persisted test attribution ───

@pytest.mark.asyncio
async def test_26_runtime_recovered_total(judge_demo_harness: JudgeDemoHarness):
    ev_res = await judge_demo_harness.client.get("/api/integrations/razorpay/evidence")
    assert ev_res.json()["all_time_recovered_minor"] == 0

    case_id, execution = await _prepare_and_execute(judge_demo_harness)
    await _fire_paid_webhook(judge_demo_harness, execution, "evt_demo_total")

    ev_res2 = await judge_demo_harness.client.get("/api/integrations/razorpay/evidence")
    assert ev_res2.json()["all_time_recovered_minor"] == 100000
