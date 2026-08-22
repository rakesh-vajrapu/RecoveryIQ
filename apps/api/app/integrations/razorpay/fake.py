from __future__ import annotations

import hashlib
import hmac
from typing import Literal

from app.integrations.razorpay.gateway import (
    PaymentLinkRequest,
    PaymentLinkResult,
    RazorpayPermanentError,
    RazorpayTransientError,
    RazorpayUnknownOutcomeError,
)


class FakeRazorpayGateway:
    """Deterministic offline gateway; it never opens a network connection."""

    def __init__(self, webhook_secret: str = "test-webhook-secret") -> None:
        self.webhook_secret = webhook_secret
        self.create_calls = 0
        self.fetch_calls = 0
        self.create_failure: Literal[
            "none", "permanent", "timeout_before", "timeout_after", "unexpected"
        ] = "none"
        self._links_by_id: dict[str, PaymentLinkResult] = {}
        self._links_by_reference: dict[str, PaymentLinkResult] = {}

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        self.create_calls += 1
        if self.create_failure == "permanent":
            raise RazorpayPermanentError("injected permanent create failure", status_code=400)
        if self.create_failure == "timeout_before":
            raise RazorpayUnknownOutcomeError("injected timeout before provider creation")
        provider_id = f"plink_test_{hashlib.sha256(request.reference_id.encode()).hexdigest()[:14]}"
        result = PaymentLinkResult(
            id=provider_id,
            amount_minor=request.amount_minor,
            currency=request.currency,
            reference_id=request.reference_id,
            status="created",
            short_url=f"https://rzp.io/i/{provider_id[-8:]}",
        )
        if self.create_failure != "unexpected":
            self._links_by_id[result.id] = result
            self._links_by_reference[result.reference_id] = result
        if self.create_failure == "timeout_after":
            raise RazorpayUnknownOutcomeError("injected timeout after provider creation")
        if self.create_failure == "unexpected":
            raise RazorpayTransientError("injected invalid response")
        return result

    def fetch_payment_link(self, payment_link_id: str) -> PaymentLinkResult:
        self.fetch_calls += 1
        try:
            return self._links_by_id[payment_link_id]
        except KeyError as exc:
            raise RazorpayPermanentError("fake Payment Link not found", status_code=404) from exc

    def find_payment_link_by_reference(self, reference_id: str) -> PaymentLinkResult | None:
        self.fetch_calls += 1
        return self._links_by_reference.get(reference_id)
