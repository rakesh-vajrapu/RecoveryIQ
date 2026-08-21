from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from recoveriq_simulator.enums import InstrumentState, PaymentMethod, TrueFailureCause
from recoveriq_simulator.observation import PublicScenario


class HiddenModel(BaseModel):
    """Base for environment-owned structures that policies must never receive."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class MerchantGroundTruth(HiddenModel):
    merchant_id: str
    median_amount_minor: int = Field(gt=0)
    amount_sigma: float = Field(gt=0)
    baseline_success_rate: float = Field(gt=0, lt=1)
    payment_method_mix: dict[PaymentMethod, float]


class CustomerGroundTruth(HiddenModel):
    customer_id: str
    liquidity_propensity: float = Field(ge=0, le=1)
    historical_reliability: float = Field(ge=0, le=1)
    nudge_responsiveness: float = Field(ge=0, le=1)
    payment_method_stability: float = Field(ge=0, le=1)
    instrument_update_propensity: float = Field(ge=0, le=1)
    retry_sensitivity: float = Field(ge=0, le=1)


class SubscriptionGroundTruth(HiddenModel):
    subscription_id: str
    instrument_state: InstrumentState


class DegradationIncidentGroundTruth(HiddenModel):
    incident_id: str
    start_at: datetime
    end_at: datetime
    payment_method: PaymentMethod
    issuer: str
    severity: float = Field(gt=0, lt=1)
    baseline_health: float = Field(gt=0, le=1)
    degraded_health: float = Field(ge=0, lt=1)
    dominant_failure_cause: TrueFailureCause


class PaymentGroundTruth(HiddenModel):
    payment_id: str
    initial_success: bool
    initial_success_probability: float = Field(ge=0, le=1)
    true_failure_cause: TrueFailureCause | None
    instrument_state: InstrumentState
    incident_id: str | None


class EnvironmentGroundTruth(HiddenModel):
    seed: int
    merchants: dict[str, MerchantGroundTruth]
    customers: dict[str, CustomerGroundTruth]
    subscriptions: dict[str, SubscriptionGroundTruth]
    payments: dict[str, PaymentGroundTruth]
    incidents: tuple[DegradationIncidentGroundTruth, ...]


class GeneratedScenario(HiddenModel):
    """Environment bundle; only `.public` may cross the future strategy boundary."""

    public: PublicScenario
    ground_truth: EnvironmentGroundTruth
