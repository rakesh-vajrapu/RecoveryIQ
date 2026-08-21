from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from recoveriq_simulator.enums import (
    ActionType,
    FailureReason,
    FailureSource,
    PaymentMethod,
)


class ObservableModel(BaseModel):
    """Base for immutable, extra-field-rejecting policy-visible structures."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class MerchantRecord(ObservableModel):
    merchant_id: str
    display_name: str


class CustomerRecord(ObservableModel):
    customer_id: str
    merchant_id: str


class SubscriptionRecord(ObservableModel):
    subscription_id: str
    customer_id: str
    merchant_id: str
    amount_minor: int = Field(gt=0)
    currency: str = "INR"
    cadence_days: int = Field(gt=0)
    created_at: datetime
    payment_method: PaymentMethod
    issuer: str


class PaymentRecord(ObservableModel):
    payment_id: str
    subscription_id: str
    customer_id: str
    merchant_id: str
    amount_minor: int = Field(gt=0)
    currency: str = "INR"
    due_at: datetime
    initial_status: str
    observable_failure_reason: FailureReason | None = None


class ObservedPaymentEvent(ObservableModel):
    event_id: str
    payment_id: str
    subscription_id: str
    customer_id: str
    merchant_id: str
    occurred_at: datetime
    observed_at: datetime
    success: bool
    payment_method: PaymentMethod
    issuer: str | None
    failure_reason: FailureReason | None = None
    failure_source: FailureSource | None = None
    attempt_number: int = Field(ge=1)
    amount_minor: int = Field(gt=0)


class PaymentObservation(ObservableModel):
    """The complete policy input at the moment an initial failure becomes observable."""

    payment_id: str
    subscription_id: str
    customer_id: str
    merchant_id: str
    observed_at: datetime
    failure_occurred_at: datetime
    amount_minor: int = Field(gt=0)
    currency: str = "INR"
    payment_method: PaymentMethod
    issuer: str | None
    failure_reason: FailureReason
    failure_source: FailureSource
    attempt_number: int = Field(ge=1)
    subscription_prior_attempts: int = Field(ge=0)
    subscription_prior_successes: int = Field(ge=0)
    customer_prior_attempts: int = Field(ge=0)
    customer_prior_success_rate: float | None = Field(default=None, ge=0, le=1)
    recent_scope_attempts: int = Field(ge=0)
    recent_scope_success_rate: float | None = Field(default=None, ge=0, le=1)
    prior_events: tuple[ObservedPaymentEvent, ...] = ()


class RecoveryAction(ObservableModel):
    action_id: str
    action_type: ActionType
    execute_at: datetime
    scheduled_delay_hours: float = Field(ge=0)
    attempt_number: int = Field(ge=0)
    intervention_cost_minor: int = Field(ge=0)
    friction_cost_minor: int = Field(ge=0)


class PublicScenario(ObservableModel):
    experiment_id: str
    merchants: tuple[MerchantRecord, ...]
    customers: tuple[CustomerRecord, ...]
    subscriptions: tuple[SubscriptionRecord, ...]
    payments: tuple[PaymentRecord, ...]
    observable_events: tuple[ObservedPaymentEvent, ...]
    failure_observations: tuple[PaymentObservation, ...]


PAYMENT_OBSERVATION_FIELD_ALLOWLIST = frozenset(
    {
        "payment_id",
        "subscription_id",
        "customer_id",
        "merchant_id",
        "observed_at",
        "failure_occurred_at",
        "amount_minor",
        "currency",
        "payment_method",
        "issuer",
        "failure_reason",
        "failure_source",
        "attempt_number",
        "subscription_prior_attempts",
        "subscription_prior_successes",
        "customer_prior_attempts",
        "customer_prior_success_rate",
        "recent_scope_attempts",
        "recent_scope_success_rate",
        "prior_events",
    }
)


def assert_observation_schema_allowlisted() -> None:
    actual = frozenset(PaymentObservation.model_fields)
    if actual != PAYMENT_OBSERVATION_FIELD_ALLOWLIST:
        added = sorted(actual - PAYMENT_OBSERVATION_FIELD_ALLOWLIST)
        removed = sorted(PAYMENT_OBSERVATION_FIELD_ALLOWLIST - actual)
        raise RuntimeError(
            f"observation schema allowlist mismatch: added={added}, removed={removed}"
        )
