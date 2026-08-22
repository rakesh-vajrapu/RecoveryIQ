from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DetectorModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScopeLevel(StrEnum):
    ISSUER = "ISSUER"
    PAYMENT_METHOD = "PAYMENT_METHOD"
    GLOBAL = "GLOBAL"


class HealthStatus(StrEnum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    HEALTHY = "HEALTHY"
    SUSPECTED = "SUSPECTED"
    OPEN = "OPEN"
    RECOVERING = "RECOVERING"
    RESOLVED = "RESOLVED"


class PredictedSeverity(StrEnum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class DetectorScope(DetectorModel):
    level: ScopeLevel
    payment_method: str | None = None
    issuer: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> DetectorScope:
        if self.level is ScopeLevel.GLOBAL and (self.payment_method or self.issuer):
            raise ValueError("global scope cannot have method or issuer")
        if self.level is ScopeLevel.PAYMENT_METHOD and (
            self.payment_method is None or self.issuer is not None
        ):
            raise ValueError("payment-method scope requires only payment_method")
        if self.level is ScopeLevel.ISSUER and (self.payment_method is None or self.issuer is None):
            raise ValueError("issuer scope requires method and issuer")
        return self

    @property
    def key(self) -> str:
        if self.level is ScopeLevel.GLOBAL:
            return "GLOBAL"
        if self.level is ScopeLevel.PAYMENT_METHOD:
            return f"METHOD:{self.payment_method}"
        return f"ISSUER:{self.payment_method}:{self.issuer}"


class PaymentResultEvent(DetectorModel):
    """Narrow event contract: every field is available at processing time."""

    event_id: str
    timestamp: datetime
    merchant_id: str
    payment_method: str
    issuer: str | None = None
    success: bool
    failure_reason: str | None = None
    failure_source: str | None = None

    @model_validator(mode="after")
    def validate_failure_fields(self) -> PaymentResultEvent:
        if self.success and (self.failure_reason is not None or self.failure_source is not None):
            raise ValueError("successful events cannot contain failure diagnostics")
        return self


class FailureShift(DetectorModel):
    reason: str
    current_share: float = Field(ge=0, le=1)
    baseline_share: float = Field(ge=0, le=1)
    absolute_change: float
    relative_lift: float | None = Field(default=None, ge=0)
    support_count: int = Field(ge=0)


class WindowEvidence(DetectorModel):
    window_minutes: int = Field(gt=0)
    attempts: int = Field(ge=0)
    successes: int = Field(ge=0)
    success_rate: float | None = Field(default=None, ge=0, le=1)
    posterior_mean: float | None = Field(default=None, ge=0, le=1)


class PaymentHealthSnapshot(DetectorModel):
    scope: DetectorScope
    timestamp: datetime
    windows: tuple[WindowEvidence, ...]
    historical_attempts: int = Field(ge=0)
    historical_success_rate: float | None = Field(default=None, ge=0, le=1)
    historical_posterior_mean: float | None = Field(default=None, ge=0, le=1)
    baseline_source: ScopeLevel | None = None
    rate_delta: float | None = None
    posterior_degradation_probability: float | None = Field(default=None, ge=0, le=1)
    ewma_success_rate: float | None = Field(default=None, ge=0, le=1)
    ewma_drop: float | None = None
    health_score: float | None = Field(default=None, ge=0, le=100)
    status: HealthStatus
    severity: PredictedSeverity | None = None
    dominant_failure_shifts: tuple[FailureShift, ...] = ()
    active_incident_id: str | None = None
    selected_window_minutes: int | None = None


class IncidentTransition(DetectorModel):
    timestamp: datetime
    status: HealthStatus
    severity: PredictedSeverity | None = None


class PredictedIncident(DetectorModel):
    incident_id: str
    scope: DetectorScope
    opened_at: datetime
    detected_at: datetime
    current_severity: PredictedSeverity
    baseline_attempts: int = Field(ge=0)
    current_attempts: int = Field(ge=0)
    baseline_success_rate: float
    current_success_rate: float
    posterior_degradation_probability: float
    evidence_window_minutes: int
    dominant_failure_shifts: tuple[FailureShift, ...] = ()
    transitions: tuple[IncidentTransition, ...]
    resolved_at: datetime | None = None


class PaymentHealthContext(DetectorModel):
    """Observable-only query result for a future recovery decision component."""

    timestamp: datetime
    requested_payment_method: str
    requested_issuer: str | None
    issuer_health: PaymentHealthSnapshot | None
    method_health: PaymentHealthSnapshot | None
    global_health: PaymentHealthSnapshot | None
