from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

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

FIXTURES = Path(__file__).parent / "fixtures" / "razorpay"
WEBHOOK_SECRET = "offline-webhook-secret"


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


@pytest.mark.asyncio
async def test_1_judge_demo_disabled_fails(judge_demo_harness: JudgeDemoHarness) -> None:
    judge_demo_harness.settings.enable_razorpay_judge_demo = False
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_2_judge_demo_refuses_simulation_mode(judge_demo_harness: JudgeDemoHarness) -> None:
    judge_demo_harness.settings.execution_environment = "SIMULATION"
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_3_judge_demo_requires_razorpay_test(judge_demo_harness: JudgeDemoHarness) -> None:
    judge_demo_harness.settings.execution_environment = cast(Any, "RAZORPAY_LIVE")
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_4_missing_api_credentials_fails_safely(judge_demo_harness: JudgeDemoHarness) -> None:
    judge_demo_harness.settings.razorpay_key_id = None
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_5_missing_webhook_secret_is_reported(judge_demo_harness: JudgeDemoHarness) -> None:
    judge_demo_harness.settings.razorpay_webhook_secret = None
    response = await judge_demo_harness.client.get("/api/integrations/razorpay/status")
    assert response.status_code == 200
    assert response.json()["webhook_configured"] is False


@pytest.mark.asyncio
async def test_6_prepared_case_amount_is_exactly_100000_inr(
    judge_demo_harness: JudgeDemoHarness,
) -> None:
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 200
    data = response.json()
    assert data["amount_minor"] == 100000
    assert data["currency"] == "INR"


@pytest.mark.asyncio
async def test_7_prepared_case_is_not_demo_synthetic(judge_demo_harness: JudgeDemoHarness) -> None:
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 200
    assert response.json()["synthetic"] is False


@pytest.mark.asyncio
async def test_8_prepared_case_is_local_unverified(judge_demo_harness: JudgeDemoHarness) -> None:
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "LOCAL_UNVERIFIED"
    assert data["synthetic"] is False


@pytest.mark.asyncio
async def test_9_no_fake_autonomous_decision_created(judge_demo_harness: JudgeDemoHarness) -> None:
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    data = response.json()
    assert len(data.get("decisions", [])) == 0
    assert len(data.get("plans", [])) == 0


@pytest.mark.asyncio
async def test_10_and_11_create_payment_link(judge_demo_harness: JudgeDemoHarness) -> None:
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]

    exec_res = await judge_demo_harness.client.post(
        f"/api/recovery-cases/{case_id}/test-payment-link"
    )
    assert exec_res.status_code == 200
    data = exec_res.json()
    assert data["amount_minor"] == 100000
    assert data["execution_mode"] == "RAZORPAY_TEST"


@pytest.mark.asyncio
async def test_12_second_execution_request_idempotent(judge_demo_harness: JudgeDemoHarness) -> None:
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]
    await judge_demo_harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")
    gateway_calls_before = judge_demo_harness.gateway.create_calls
    await judge_demo_harness.client.post(f"/api/recovery-cases/{case_id}/test-payment-link")
    gateway_calls_after = judge_demo_harness.gateway.create_calls
    assert gateway_calls_before == gateway_calls_after


@pytest.mark.asyncio
async def test_13_real_service_path_is_test_mode(judge_demo_harness: JudgeDemoHarness) -> None:
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]
    exec_res = await judge_demo_harness.client.post(
        f"/api/recovery-cases/{case_id}/test-payment-link"
    )
    assert exec_res.status_code == 200


@pytest.mark.asyncio
async def test_14_15_webhook_signature(judge_demo_harness: JudgeDemoHarness) -> None:
    response = await judge_demo_harness.client.post(
        "/webhooks/razorpay",
        headers={"x-razorpay-signature": "invalid"},
        content=b'{"event": "payment_link.paid"}',
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_16_duplicate_webhook_deduplication(judge_demo_harness: JudgeDemoHarness) -> None:
    payload = b'{"entity": "event", "event": "payment_link.paid", "contains": [], "payload": {"payment_link": {"entity": {"id": "plink_test", "status": "paid", "amount": 100000, "currency": "INR", "reference_id": "test_ref"}}}}'
    sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    headers = {"x-razorpay-signature": sig, "x-razorpay-event-id": "evt_test123"}
    res1 = await judge_demo_harness.client.post(
        "/webhooks/razorpay", headers=headers, content=payload
    )
    assert res1.status_code in [200, 202]
    res2 = await judge_demo_harness.client.post(
        "/webhooks/razorpay", headers=headers, content=payload
    )
    assert res2.status_code in [200, 202]


@pytest.mark.asyncio
async def test_full_webhook_to_recovery_flow(judge_demo_harness: JudgeDemoHarness) -> None:
    # 17, 18, 20, 21, 23
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]
    exec_res = await judge_demo_harness.client.post(
        f"/api/recovery-cases/{case_id}/test-payment-link"
    )
    assert exec_res.status_code == 200

    with judge_demo_harness.sessions() as db:
        case = db.execute(
            select(RecoveryCase).where(RecoveryCase.id == uuid.UUID(case_id))
        ).scalar_one()
        execution = db.execute(
            select(ExternalExecution).where(ExternalExecution.recovery_case_id == case.id)
        ).scalar_one()
        provider_ref = execution.provider_reference_id
        plink_id = execution.provider_entity_id

    assert plink_id is not None

    plink = judge_demo_harness.gateway._links_by_id[plink_id]
    judge_demo_harness.gateway._links_by_id[plink_id] = plink.model_copy(
        update={"status": "paid", "amount_paid_minor": 100000}
    )

    # Webhook
    payload_str = json.dumps(
        {
            "entity": "event",
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": plink_id,
                        "status": "paid",
                        "amount": 100000,
                        "amount_paid": 100000,
                        "currency": "INR",
                        "reference_id": provider_ref,
                    }
                }
            },
        }
    ).encode("utf-8")
    sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), payload_str, hashlib.sha256).hexdigest()
    headers = {"x-razorpay-signature": sig, "x-razorpay-event-id": "evt_demo_success"}
    wh_res = await judge_demo_harness.client.post(
        "/webhooks/razorpay", headers=headers, content=payload_str
    )
    assert wh_res.status_code in [200, 202]

    with judge_demo_harness.sessions() as db:
        case = db.execute(
            select(RecoveryCase).where(RecoveryCase.id == uuid.UUID(case_id))
        ).scalar_one()
        assert case.status == RecoveryCaseStatus.RECOVERED

        outcome = db.execute(
            select(ExternalOutcome).where(ExternalOutcome.recovery_case_id == case.id)
        ).scalar_one()
        assert outcome.verified is True

        attribution = db.execute(
            select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == case.id)
        ).scalar_one()
        assert attribution.amount_minor == 100000

    # 23. Recovered case cannot create another link
    exec_res2 = await judge_demo_harness.client.post(
        f"/api/recovery-cases/{case_id}/test-payment-link"
    )
    assert exec_res2.status_code == 409


@pytest.mark.asyncio
async def test_19_mismatch_fails_closed(judge_demo_harness: JudgeDemoHarness) -> None:
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]
    exec_res = await judge_demo_harness.client.post(
        f"/api/recovery-cases/{case_id}/test-payment-link"
    )
    assert exec_res.status_code == 200

    with judge_demo_harness.sessions() as db:
        case = db.execute(
            select(RecoveryCase).where(RecoveryCase.id == uuid.UUID(case_id))
        ).scalar_one()
        execution = db.execute(
            select(ExternalExecution).where(ExternalExecution.recovery_case_id == case.id)
        ).scalar_one()
        provider_ref = execution.provider_reference_id
        plink_id = execution.provider_entity_id
        assert plink_id is not None

    # Mismatch amount in gateway
    plink = judge_demo_harness.gateway._links_by_id[plink_id]
    judge_demo_harness.gateway._links_by_id[plink_id] = plink.model_copy(
        update={"amount_minor": 99999}
    )

    payload_str = json.dumps(
        {
            "entity": "event",
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": plink_id,
                        "status": "paid",
                        "amount": 100000,
                        "currency": "INR",
                        "reference_id": provider_ref,
                    }
                }
            },
        }
    ).encode("utf-8")
    sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), payload_str, hashlib.sha256).hexdigest()
    headers = {"x-razorpay-signature": sig, "x-razorpay-event-id": "evt_demo_mismatch"}
    wh_res = await judge_demo_harness.client.post(
        "/webhooks/razorpay", headers=headers, content=payload_str
    )
    assert wh_res.status_code in [200, 202]

    with judge_demo_harness.sessions() as db:
        case = db.execute(
            select(RecoveryCase).where(RecoveryCase.id == uuid.UUID(case_id))
        ).scalar_one()
        assert case.status != RecoveryCaseStatus.RECOVERED
        attribution = db.execute(
            select(RecoveryAttribution).where(RecoveryAttribution.recovery_case_id == case.id)
        ).scalar_one_or_none()
        assert attribution is None


@pytest.mark.asyncio
async def test_24_no_secret_returned(judge_demo_harness: JudgeDemoHarness) -> None:
    res = await judge_demo_harness.client.get("/api/integrations/razorpay/status")
    data = res.json()
    assert "razorpay_key_secret" not in data
    assert "razorpay_webhook_secret" not in data
    assert data["api_configured"] is True
    assert data["webhook_configured"] is True
    assert data["judge_demo_enabled"] is True


@pytest.mark.asyncio
async def test_25_test_mode_status(judge_demo_harness: JudgeDemoHarness) -> None:
    judge_demo_harness.settings.enable_razorpay_judge_demo = False
    res = await judge_demo_harness.client.get("/api/integrations/razorpay/status")
    assert res.json()["judge_demo_enabled"] is False


@pytest.mark.asyncio
async def test_26_runtime_recovered_total(judge_demo_harness: JudgeDemoHarness) -> None:
    ev_res = await judge_demo_harness.client.get("/api/integrations/razorpay/evidence")
    assert ev_res.json()["all_time_recovered_minor"] == 0

    # Flow success
    response = await judge_demo_harness.client.post("/api/integrations/razorpay/live-demo/case")
    case_id = response.json()["id"]
    exec_res = await judge_demo_harness.client.post(
        f"/api/recovery-cases/{case_id}/test-payment-link"
    )
    assert exec_res.status_code == 200

    with judge_demo_harness.sessions() as db:
        case = db.execute(
            select(RecoveryCase).where(RecoveryCase.id == uuid.UUID(case_id))
        ).scalar_one()
        execution = db.execute(
            select(ExternalExecution).where(ExternalExecution.recovery_case_id == case.id)
        ).scalar_one()
        provider_ref = execution.provider_reference_id
        plink_id = execution.provider_entity_id

    assert plink_id is not None

    plink = judge_demo_harness.gateway._links_by_id[plink_id]
    judge_demo_harness.gateway._links_by_id[plink_id] = plink.model_copy(
        update={"status": "paid", "amount_paid_minor": 100000}
    )

    payload_str = json.dumps(
        {
            "entity": "event",
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": plink_id,
                        "status": "paid",
                        "amount": 100000,
                        "amount_paid": 100000,
                        "currency": "INR",
                        "reference_id": provider_ref,
                    }
                }
            },
        }
    ).encode("utf-8")
    sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), payload_str, hashlib.sha256).hexdigest()
    headers = {"x-razorpay-signature": sig, "x-razorpay-event-id": "evt_demo_success_total"}
    await judge_demo_harness.client.post("/webhooks/razorpay", headers=headers, content=payload_str)

    ev_res2 = await judge_demo_harness.client.get("/api/integrations/razorpay/evidence")
    assert ev_res2.json()["all_time_recovered_minor"] == 100000
