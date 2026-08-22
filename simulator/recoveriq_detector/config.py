from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field, model_validator

from recoveriq_detector import DETECTOR_VERSION


class EligibilityRule(BaseModel):
    """Pre-registered evaluation rule; never consumed by detector replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_incident_attempts: int = Field(default=5, ge=1)
    min_prior_baseline_attempts: int = Field(default=50, ge=1)
    baseline_lookback_days: int = Field(default=30, ge=1)


class DetectorConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detector_version: str = DETECTOR_VERSION
    windows_minutes: tuple[int, ...] = (5, 15, 60, 360, 1_440)
    baseline_lookback_days: int = Field(default=30, ge=1)
    baseline_exclusion_minutes: int = Field(default=1_440, ge=1)
    min_baseline_attempts: int = Field(default=50, ge=1)
    min_current_attempts: int = Field(default=5, ge=2)
    beta_prior_strength: float = Field(default=12.0, gt=0)
    hierarchical_prior_strength: float = Field(default=8.0, ge=0)
    meaningful_drop: float = Field(default=0.18, gt=0, lt=1)
    posterior_open_probability: float = Field(default=0.975, gt=0.5, lt=1)
    posterior_suspect_probability: float = Field(default=0.85, gt=0.5, lt=1)
    ewma_alpha: float = Field(default=0.12, gt=0, le=1)
    ewma_drop_threshold: float = Field(default=0.10, gt=0, lt=1)
    open_persistence: int = Field(default=2, ge=1)
    recovery_persistence: int = Field(default=4, ge=2)
    recovery_drop: float = Field(default=0.06, ge=0, lt=1)
    dominant_reason_min_failures: int = Field(default=5, ge=1)
    dominant_reason_min_support: int = Field(default=3, ge=1)
    static_success_threshold: float = Field(default=0.70, gt=0, lt=1)
    relative_drop_threshold: float = Field(default=0.18, gt=0, lt=1)

    @model_validator(mode="after")
    def validate_windows(self) -> DetectorConfig:
        if tuple(sorted(set(self.windows_minutes))) != self.windows_minutes:
            raise ValueError("windows must be unique and ascending")
        if self.baseline_exclusion_minutes < max(self.windows_minutes):
            raise ValueError("baseline exclusion must cover the largest analysis window")
        if self.posterior_suspect_probability >= self.posterior_open_probability:
            raise ValueError("suspect probability must be lower than open probability")
        return self

    @property
    def configuration_hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


ELIGIBILITY_RULE = EligibilityRule()


DEVELOPMENT_CANDIDATES: tuple[DetectorConfig, ...] = (
    DetectorConfig(
        min_current_attempts=5,
        hierarchical_prior_strength=4.0,
        meaningful_drop=0.08,
        posterior_open_probability=0.75,
        posterior_suspect_probability=0.60,
        ewma_drop_threshold=0.04,
        open_persistence=1,
    ),
    DetectorConfig(
        min_current_attempts=8,
        hierarchical_prior_strength=4.0,
        meaningful_drop=0.08,
        posterior_open_probability=0.75,
        posterior_suspect_probability=0.60,
        ewma_drop_threshold=0.04,
        open_persistence=1,
    ),
    DetectorConfig(
        min_current_attempts=10,
        hierarchical_prior_strength=4.0,
        meaningful_drop=0.08,
        posterior_open_probability=0.75,
        posterior_suspect_probability=0.60,
        ewma_drop_threshold=0.04,
        open_persistence=1,
    ),
    DetectorConfig(
        min_current_attempts=8,
        hierarchical_prior_strength=4.0,
        meaningful_drop=0.08,
        posterior_open_probability=0.80,
        posterior_suspect_probability=0.60,
        ewma_drop_threshold=0.04,
        open_persistence=1,
    ),
    DetectorConfig(
        min_current_attempts=10,
        hierarchical_prior_strength=4.0,
        meaningful_drop=0.08,
        posterior_open_probability=0.80,
        posterior_suspect_probability=0.60,
        ewma_drop_threshold=0.04,
        open_persistence=1,
    ),
    DetectorConfig(
        min_current_attempts=5,
        hierarchical_prior_strength=8.0,
        meaningful_drop=0.14,
        posterior_open_probability=0.90,
        posterior_suspect_probability=0.80,
        ewma_drop_threshold=0.08,
        open_persistence=2,
    ),
)
