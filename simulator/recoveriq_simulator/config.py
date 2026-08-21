from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from recoveriq_simulator import SIMULATOR_VERSION


class SimulationCosts(BaseModel):
    """Synthetic evaluation costs in minor INR units; not Razorpay pricing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retry_operational_minor: int = Field(default=80, ge=0)
    message_minor: int = Field(default=35, ge=0)
    payment_link_minor: int = Field(default=100, ge=0)
    method_update_minor: int = Field(default=140, ge=0)
    alternate_method_minor: int = Field(default=180, ge=0)
    human_review_minor: int = Field(default=1_200, ge=0)
    base_contact_friction_minor: int = Field(default=60, ge=0)
    retry_friction_minor: int = Field(default=20, ge=0)
    friction_growth: float = Field(default=1.8, ge=1.0, le=5.0)


class SimulatorConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    simulator_version: str = SIMULATOR_VERSION
    seed: int = 20_260_821
    num_payment_attempts: int = Field(default=20_000, ge=100)
    merchant_count: int = Field(default=5, ge=3, le=8)
    customer_count: int = Field(default=4_000, ge=50)
    subscription_count: int = Field(default=5_000, ge=50)
    horizon_days: int = Field(default=120, ge=30, le=730)
    incident_count: int = Field(default=18, ge=1, le=200)
    start_time: datetime = datetime(2026, 1, 1, tzinfo=UTC)

    min_payment_amount_minor: int = Field(default=9_900, gt=0)
    max_payment_amount_minor: int = Field(default=1_000_000, gt=0)
    missing_issuer_rate: float = Field(default=0.025, ge=0, le=0.25)
    unknown_failure_rate: float = Field(default=0.03, ge=0, le=0.25)
    delayed_event_rate: float = Field(default=0.05, ge=0, le=0.25)
    max_event_delay_minutes: int = Field(default=30, ge=1, le=240)

    fixed_retry_delay_hours: float = Field(default=6.0, gt=0, le=168)
    max_retries: int = Field(default=2, ge=1, le=10)
    reminder_delay_minutes: int = Field(default=5, ge=0, le=1_440)

    plausible_failure_rate_min: float = Field(default=0.05, ge=0, lt=1)
    plausible_failure_rate_max: float = Field(default=0.45, gt=0, le=1)
    costs: SimulationCosts = Field(default_factory=SimulationCosts)

    @model_validator(mode="after")
    def validate_scale(self) -> SimulatorConfig:
        if self.subscription_count < self.customer_count:
            raise ValueError("subscription_count must be at least customer_count")
        available_attempts = self.subscription_count * max(1, self.horizon_days // 30)
        if self.num_payment_attempts > available_attempts:
            raise ValueError(
                "num_payment_attempts exceeds subscription renewals available in horizon"
            )
        if self.max_payment_amount_minor <= self.min_payment_amount_minor:
            raise ValueError("max payment amount must exceed minimum payment amount")
        if self.plausible_failure_rate_min >= self.plausible_failure_rate_max:
            raise ValueError("plausible failure bounds are invalid")
        return self

    def canonical_json(self) -> str:
        return self.model_dump_json(exclude_none=False)

    @property
    def configuration_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @property
    def experiment_id(self) -> str:
        version = self.simulator_version.replace(".", "")
        return f"sim-v{version}-{self.seed}-{self.configuration_hash[:12]}"
