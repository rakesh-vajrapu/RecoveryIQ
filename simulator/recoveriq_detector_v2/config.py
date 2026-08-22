from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field, model_validator

from recoveriq_detector_v2 import DETECTOR_V2_VERSION

V2_DEVELOPMENT_SEEDS = tuple(range(20_260_901, 20_260_911))
V1_CONSUMED_VALIDATION_SEEDS = tuple(range(20_261_001, 20_261_011))
FINAL_EVALUATION_SEEDS = tuple(range(20_261_101, 20_261_121))
V2_VALIDATION_SEEDS = tuple(range(20_261_201, 20_261_211))

HARD_POLICY_MIN_PRECISION = 0.70
HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY = 0.005
HARD_POLICY_MIN_CONFIRMED_EPISODES = 5


class HighEvidenceRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    first_horizon_hours: int = 24
    min_attempts_first_horizon: int = 10
    baseline_lookback_days: int = 30
    min_prior_baseline_attempts: int = 100


class DetectorV2Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detector_version: str = DETECTOR_V2_VERSION
    windows_minutes: tuple[int, ...] = (5, 15, 60)
    baseline_lookback_days: int = 14
    min_baseline_attempts: int = 50
    baseline_prior_strength: float = 20.0
    default_success_probability: float = 0.88
    minimum_baseline_probability: float = 0.55
    maximum_baseline_probability: float = 0.995
    drop_hypotheses: tuple[float, ...] = (0.10, 0.20, 0.35)
    minimum_alternative_probability: float = 0.05
    watch_llr_threshold: float = Field(default=2.5, gt=0)
    watch_min_events: int = Field(default=3, ge=1)
    watch_release_llr: float = Field(default=0.35, ge=0)
    watch_release_successes: int = Field(default=3, ge=1)
    confirmed_llr_threshold: float = Field(default=8.0, gt=0)
    confirmed_strong_llr: float = Field(default=5.5, gt=0)
    confirmed_parent_llr: float = Field(default=5.0, gt=0)
    confirmed_min_events: int = Field(default=8, ge=2)
    failure_js_threshold: float = Field(default=0.12, ge=0, le=1)
    failure_min_current: int = Field(default=5, ge=1)
    failure_min_baseline: int = Field(default=10, ge=1)
    failure_reason_min_support: int = Field(default=3, ge=1)
    confirmation_cooldown_days: int = Field(default=7, ge=0)
    recovery_start_llr: float = Field(default=2.5, gt=0)
    recovery_resolve_llr: float = Field(default=5.0, gt=0)
    recovery_min_events: int = Field(default=5, ge=2)

    @model_validator(mode="after")
    def validate_config(self) -> DetectorV2Config:
        if tuple(sorted(set(self.windows_minutes))) != self.windows_minutes:
            raise ValueError("windows must be unique and ascending")
        if tuple(sorted(set(self.drop_hypotheses))) != self.drop_hypotheses:
            raise ValueError("drop hypotheses must be unique and ascending")
        if self.confirmed_strong_llr >= self.confirmed_llr_threshold:
            raise ValueError("strong corroborated boundary must be below extreme boundary")
        if self.watch_llr_threshold >= self.confirmed_strong_llr:
            raise ValueError("WATCH must be less strict than CONFIRMED")
        if self.recovery_start_llr >= self.recovery_resolve_llr:
            raise ValueError("recovery start must be below resolution boundary")
        return self

    @property
    def configuration_hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


HIGH_EVIDENCE_RULE = HighEvidenceRule()


DEVELOPMENT_CANDIDATES: tuple[DetectorV2Config, ...] = (
    DetectorV2Config(
        watch_llr_threshold=2.0,
        confirmed_llr_threshold=7.0,
        confirmed_strong_llr=5.0,
        confirmed_parent_llr=4.5,
        confirmed_min_events=6,
        failure_js_threshold=0.10,
    ),
    DetectorV2Config(
        watch_llr_threshold=2.5,
        confirmed_llr_threshold=8.0,
        confirmed_strong_llr=5.5,
        confirmed_parent_llr=5.0,
        confirmed_min_events=8,
        failure_js_threshold=0.12,
    ),
    DetectorV2Config(
        watch_llr_threshold=3.0,
        confirmed_llr_threshold=9.0,
        confirmed_strong_llr=6.5,
        confirmed_parent_llr=6.0,
        confirmed_min_events=8,
        failure_js_threshold=0.15,
    ),
    DetectorV2Config(
        watch_llr_threshold=2.0,
        confirmed_llr_threshold=9.0,
        confirmed_strong_llr=6.0,
        confirmed_parent_llr=5.5,
        confirmed_min_events=10,
        failure_js_threshold=0.12,
    ),
    DetectorV2Config(
        watch_llr_threshold=2.5,
        confirmed_llr_threshold=10.0,
        confirmed_strong_llr=7.0,
        confirmed_parent_llr=6.5,
        confirmed_min_events=10,
        failure_js_threshold=0.18,
    ),
    DetectorV2Config(
        watch_llr_threshold=3.0,
        confirmed_llr_threshold=12.0,
        confirmed_strong_llr=8.0,
        confirmed_parent_llr=7.5,
        confirmed_min_events=12,
        failure_js_threshold=0.20,
    ),
)
