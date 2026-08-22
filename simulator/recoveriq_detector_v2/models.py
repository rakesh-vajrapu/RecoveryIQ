from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class V2Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScopeLevel(StrEnum):
    ISSUER = "ISSUER"
    PAYMENT_METHOD = "PAYMENT_METHOD"
    GLOBAL = "GLOBAL"


class EvidenceLevel(StrEnum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    CONFIRMED = "CONFIRMED"
    RECOVERING = "RECOVERING"
    RESOLVED = "RESOLVED"


class ObservableSeverity(StrEnum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class PolicyEvidenceRole(StrEnum):
    NONE = "NONE"
    WATCH_ADVISORY = "WATCH_ADVISORY"
    CONFIRMED_CANDIDATE = "CONFIRMED_CANDIDATE"


class DetectorScope(V2Model):
    level: ScopeLevel
    payment_method: str | None = None
    issuer: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> DetectorScope:
        if self.level is ScopeLevel.GLOBAL and (self.payment_method or self.issuer):
            raise ValueError("global scope cannot contain method or issuer")
        if self.level is ScopeLevel.PAYMENT_METHOD and (
            self.payment_method is None or self.issuer is not None
        ):
            raise ValueError("method scope requires payment_method only")
        if self.level is ScopeLevel.ISSUER and (self.payment_method is None or self.issuer is None):
            raise ValueError("issuer scope requires payment_method and issuer")
        return self

    @property
    def key(self) -> str:
        if self.level is ScopeLevel.GLOBAL:
            return "GLOBAL"
        if self.level is ScopeLevel.PAYMENT_METHOD:
            return f"METHOD:{self.payment_method}"
        return f"ISSUER:{self.payment_method}:{self.issuer}"


class PaymentResultEvent(V2Model):
    event_id: str
    timestamp: datetime
    merchant_id: str
    payment_method: str
    issuer: str | None = None
    success: bool
    failure_reason: str | None = None
    failure_source: str | None = None

    @model_validator(mode="after")
    def validate_diagnostics(self) -> PaymentResultEvent:
        if self.success and (self.failure_reason is not None or self.failure_source is not None):
            raise ValueError("successful event cannot carry failure diagnostics")
        return self


class WindowHealth(V2Model):
    minutes: int = Field(gt=0)
    attempts: int = Field(ge=0)
    successes: int = Field(ge=0)
    success_rate: float | None = Field(default=None, ge=0, le=1)


class SequentialHypothesis(V2Model):
    drop: float = Field(gt=0, lt=1)
    alternative_success_probability: float = Field(gt=0, lt=1)
    log_likelihood_ratio: float = Field(ge=0)


class SequentialEvidence(V2Model):
    hypotheses: tuple[SequentialHypothesis, ...]
    maximum_log_likelihood_ratio: float = Field(ge=0)
    strongest_drop: float | None = Field(default=None, gt=0, lt=1)
    recovery_log_likelihood_ratio: float = Field(ge=0)


class ReasonShift(V2Model):
    reason: str
    current_share: float = Field(ge=0, le=1)
    baseline_share: float = Field(ge=0, le=1)
    absolute_increase: float
    relative_lift: float | None = Field(default=None, ge=0)
    support_count: int = Field(ge=0)


class FailureDistributionEvidence(V2Model):
    supported: bool
    current_failure_count: int = Field(ge=0)
    baseline_failure_count: int = Field(ge=0)
    jensen_shannon_divergence: float | None = Field(default=None, ge=0, le=1)
    dominant_shifts: tuple[ReasonShift, ...] = ()


class ParentCorroboration(V2Model):
    method_level: EvidenceLevel | None = None
    method_maximum_llr: float | None = Field(default=None, ge=0)
    global_level: EvidenceLevel | None = None
    global_maximum_llr: float | None = Field(default=None, ge=0)
    corroborated: bool = False


class HealthSnapshotV2(V2Model):
    scope: DetectorScope
    timestamp: datetime
    evidence_level: EvidenceLevel
    observable_severity: ObservableSeverity | None = None
    baseline_success_probability: float | None = Field(default=None, ge=0, le=1)
    baseline_attempts: int = Field(ge=0)
    baseline_source: ScopeLevel | None = None
    recent_windows: tuple[WindowHealth, ...]
    sequential_evidence: SequentialEvidence
    failure_distribution: FailureDistributionEvidence
    parent_corroboration: ParentCorroboration
    active_incident_id: str | None = None
    time_since_watch_seconds: float | None = Field(default=None, ge=0)
    time_since_confirmed_seconds: float | None = Field(default=None, ge=0)
    policy_evidence_role: PolicyEvidenceRole


class EvidenceTransition(V2Model):
    timestamp: datetime
    evidence_level: EvidenceLevel
    severity: ObservableSeverity | None = None
    maximum_llr: float = Field(ge=0)


class DegradationEpisodeV2(V2Model):
    incident_id: str
    scope: DetectorScope
    watch_at: datetime
    confirmed_at: datetime | None = None
    resolved_at: datetime | None = None
    dissipated_without_confirmation: bool = False
    baseline_success_probability: float = Field(ge=0, le=1)
    baseline_attempts: int = Field(ge=0)
    maximum_llr: float = Field(ge=0)
    current_attempts: int = Field(ge=0)
    current_failures: int = Field(ge=0)
    current_severity: ObservableSeverity
    failure_distribution: FailureDistributionEvidence
    parent_corroboration: ParentCorroboration
    confirmation_rule: str | None = None
    transitions: tuple[EvidenceTransition, ...]


class PaymentHealthContextV2(V2Model):
    """Phase-4-facing observable context; WATCH is explicitly advisory."""

    context_version: str = "2.0"
    timestamp: datetime
    requested_payment_method: str
    requested_issuer: str | None
    issuer_health: HealthSnapshotV2 | None
    method_health: HealthSnapshotV2 | None
    global_health: HealthSnapshotV2 | None
    confirmed_hard_policy_gate_passed: bool = False
