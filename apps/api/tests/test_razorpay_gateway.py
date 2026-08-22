from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
from pydantic import SecretStr

from app.integrations.razorpay.fake import FakeRazorpayGateway
from app.integrations.razorpay.gateway import (
    HttpRazorpayGateway,
    PaymentLinkRequest,
    RazorpayCredentials,
    RazorpayPermanentError,
    RazorpayUnknownOutcomeError,
)


def _credentials() -> RazorpayCredentials:
    return RazorpayCredentials(
        key_id=SecretStr("rzp_test_fake_key"),
        key_secret=SecretStr("fake-key-secret"),
        webhook_secret=SecretStr("fake-webhook-secret"),
    )


def _request() -> PaymentLinkRequest:
    return PaymentLinkRequest(
        amount_minor=49900,
        currency="INR",
        reference_id="riq_123",
        description="RecoverIQ Test Mode payment",
        notes={"recoveriq_case": "case-id"},
    )


def test_webhook_signature_is_hmac_sha256_over_exact_raw_bytes() -> None:
    gateway = HttpRazorpayGateway(_credentials())
    compact = b'{"event":"subscription.pending"}'
    pretty = b'{ "event": "subscription.pending" }'
    signature = hmac.new(b"fake-webhook-secret", compact, hashlib.sha256).hexdigest()

    assert gateway.verify_webhook(compact, signature) is True
    assert gateway.verify_webhook(pretty, signature) is False


def test_http_gateway_creates_non_partial_test_payment_link_contract() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization", "")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "plink_test_001",
                "amount": 49900,
                "amount_paid": 0,
                "currency": "INR",
                "reference_id": "riq_123",
                "status": "created",
                "short_url": "https://rzp.io/i/test001",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = HttpRazorpayGateway(_credentials(), client=client).create_payment_link(_request())

    assert captured["url"] == "https://api.razorpay.com/v1/payment_links/"
    assert str(captured["authorization"]).startswith("Basic ")
    assert captured["payload"] == {
        "amount": 49900,
        "currency": "INR",
        "accept_partial": False,
        "reference_id": "riq_123",
        "description": "RecoverIQ Test Mode payment",
        "notes": {"recoveriq_case": "case-id"},
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
    }
    assert result.id == "plink_test_001"


def test_http_gateway_does_not_retry_permanent_create_failure() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": {"description": "bad request"}})

    gateway = HttpRazorpayGateway(
        _credentials(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(RazorpayPermanentError):
        gateway.create_payment_link(_request())
    assert calls == 1


def test_http_gateway_treats_create_transport_timeout_as_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("injected", request=request)

    gateway = HttpRazorpayGateway(
        _credentials(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(RazorpayUnknownOutcomeError):
        gateway.create_payment_link(_request())


def test_fake_gateway_is_deterministic_and_supports_timeout_after_create() -> None:
    gateway = FakeRazorpayGateway()
    first = gateway.create_payment_link(_request())
    second = FakeRazorpayGateway().create_payment_link(_request())

    assert first == second
    gateway.create_failure = "timeout_after"
    unknown_request = _request().model_copy(update={"reference_id": "riq_unknown"})
    with pytest.raises(RazorpayUnknownOutcomeError):
        gateway.create_payment_link(unknown_request)
    assert gateway.find_payment_link_by_reference("riq_unknown") is not None
