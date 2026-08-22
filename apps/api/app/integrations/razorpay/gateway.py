from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class GatewayModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PaymentLinkRequest(GatewayModel):
    amount_minor: int = Field(gt=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    reference_id: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=2048)
    notes: dict[str, str] = Field(default_factory=dict)


class PaymentLinkResult(GatewayModel):
    id: str
    amount_minor: int
    amount_paid_minor: int = 0
    currency: str
    reference_id: str
    status: str
    short_url: str | None = None


class RazorpayGatewayError(RuntimeError):
    category = "RAZORPAY_ERROR"


class RazorpayNotConfiguredError(RazorpayGatewayError):
    category = "NOT_CONFIGURED"


class RazorpayPermanentError(RazorpayGatewayError):
    category = "PERMANENT"

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RazorpayTransientError(RazorpayGatewayError):
    category = "TRANSIENT"


class RazorpayUnknownOutcomeError(RazorpayGatewayError):
    category = "UNKNOWN_OUTCOME"


class RazorpayGateway(Protocol):
    def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult: ...

    def fetch_payment_link(self, payment_link_id: str) -> PaymentLinkResult: ...

    def find_payment_link_by_reference(self, reference_id: str) -> PaymentLinkResult | None: ...

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class RazorpayCredentials:
    key_id: SecretStr | None
    key_secret: SecretStr | None
    webhook_secret: SecretStr | None


class HttpRazorpayGateway:
    """Small explicit client for the documented Razorpay Payment Links API."""

    API_BASE_URL = "https://api.razorpay.com/v1"

    def __init__(
        self,
        credentials: RazorpayCredentials,
        *,
        client: httpx.Client | None = None,
        fetch_attempts: int = 3,
    ) -> None:
        self._credentials = credentials
        self._client = client or httpx.Client(timeout=10.0)
        self._fetch_attempts = fetch_attempts

    def close(self) -> None:
        self._client.close()

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        secret = self._credentials.webhook_secret
        if secret is None:
            raise RazorpayNotConfiguredError("Razorpay webhook secret is not configured")
        expected = hmac.new(
            secret.get_secret_value().encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        auth = self._auth()
        payload: dict[str, Any] = {
            "amount": request.amount_minor,
            "currency": request.currency,
            "accept_partial": False,
            "reference_id": request.reference_id,
            "description": request.description,
            "notes": request.notes,
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
        }
        try:
            response = self._client.post(
                f"{self.API_BASE_URL}/payment_links/", json=payload, auth=auth
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise RazorpayUnknownOutcomeError(
                "Payment Link create outcome is unknown after transport failure"
            ) from exc
        if response.status_code in {401, 403}:
            raise RazorpayPermanentError(
                "Razorpay rejected Test Mode credentials", status_code=response.status_code
            )
        if response.status_code == 429 or response.status_code >= 500:
            raise RazorpayUnknownOutcomeError(
                f"Payment Link create outcome is unknown after HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            raise RazorpayPermanentError(
                f"Razorpay rejected Payment Link request with HTTP {response.status_code}",
                status_code=response.status_code,
            )
        return self._parse_payment_link(response)

    def fetch_payment_link(self, payment_link_id: str) -> PaymentLinkResult:
        response = self._bounded_get(f"{self.API_BASE_URL}/payment_links/{payment_link_id}")
        return self._parse_payment_link(response)

    def find_payment_link_by_reference(self, reference_id: str) -> PaymentLinkResult | None:
        response = self._bounded_get(
            f"{self.API_BASE_URL}/payment_links/", params={"reference_id": reference_id}
        )
        payload = self._json_object(response)
        links = payload.get("payment_links", [])
        if not isinstance(links, list):
            raise RazorpayTransientError("Razorpay returned an invalid Payment Link list")
        matching = [item for item in links if isinstance(item, dict)]
        if not matching:
            return None
        return self._payment_link_from_payload(matching[0])

    def _bounded_get(self, url: str, *, params: dict[str, str] | None = None) -> httpx.Response:
        auth = self._auth()
        last_error: Exception | None = None
        for _ in range(self._fetch_attempts):
            try:
                response = self._client.get(url, params=params, auth=auth)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                continue
            if response.status_code in {401, 403, 404}:
                raise RazorpayPermanentError(
                    f"Razorpay fetch failed with HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            if response.status_code == 429 or response.status_code >= 500:
                last_error = RazorpayTransientError(
                    f"Razorpay fetch failed with HTTP {response.status_code}"
                )
                continue
            if response.status_code >= 400:
                raise RazorpayPermanentError(
                    f"Razorpay fetch failed with HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            return response
        raise RazorpayTransientError(
            "Razorpay fetch exhausted its bounded attempts"
        ) from last_error

    def _auth(self) -> httpx.BasicAuth:
        if self._credentials.key_id is None or self._credentials.key_secret is None:
            raise RazorpayNotConfiguredError(
                "Razorpay Test Mode API credentials are not configured"
            )
        return httpx.BasicAuth(
            self._credentials.key_id.get_secret_value(),
            self._credentials.key_secret.get_secret_value(),
        )

    @classmethod
    def _parse_payment_link(cls, response: httpx.Response) -> PaymentLinkResult:
        return cls._payment_link_from_payload(cls._json_object(response))

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RazorpayTransientError("Razorpay returned non-JSON content") from exc
        if not isinstance(payload, dict):
            raise RazorpayTransientError("Razorpay returned an invalid JSON object")
        return cast(dict[str, Any], payload)

    @staticmethod
    def _payment_link_from_payload(payload: dict[str, Any]) -> PaymentLinkResult:
        try:
            return PaymentLinkResult(
                id=str(payload["id"]),
                amount_minor=int(payload["amount"]),
                amount_paid_minor=int(payload.get("amount_paid", 0)),
                currency=str(payload["currency"] or "INR"),
                reference_id=str(payload["reference_id"]),
                status=str(payload["status"]),
                short_url=str(payload["short_url"]) if payload.get("short_url") else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RazorpayTransientError(
                "Razorpay Payment Link response failed validation"
            ) from exc
