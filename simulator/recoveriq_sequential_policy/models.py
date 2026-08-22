from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from recoveriq_sequential.models import SequentialCandidate


class PolicyV2Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SequentialDecisionKind(StrEnum):
    ACTION = "ACTION"
    STOP = "STOP"
    HUMAN_REVIEW = "HUMAN_REVIEW"


@dataclass(frozen=True, slots=True)
class SequentialCandidateScore:
    candidate: SequentialCandidate
    probability: float
    incremental_erv_minor: int
    normalized_erv: float
    action_stage_support: int
    calibration_bin: int
    calibration_bin_support: int

    @property
    def supported(self) -> bool:
        return self.action_stage_support >= 500 and self.calibration_bin_support >= 100


@dataclass(frozen=True, slots=True)
class SequentialPolicyDecision:
    kind: SequentialDecisionKind
    selected: SequentialCandidateScore | None
    reason: str
    normalized_margin: float | None


class FrozenSequentialBaselines(PolicyV2Base):
    artifact_type: str = "frozen_sequential_observable_baselines"
    development_seeds: tuple[int, ...]
    target: str
    simple_min_support: int
    global_min_support: int
    simple_mapping: dict[str, str]
    stage_rankings: dict[str, tuple[str, ...]]
    cell_diagnostics: dict[str, Any]


class FrozenSequentialPolicy(PolicyV2Base):
    artifact_type: str = "frozen_bounded_sequential_policy"
    policy_version: str
    model_version: str
    model_sha256: str
    feature_schema_hash: str
    calibration_method: str
    calibration_sha256: str
    candidate_labels: tuple[str, ...]
    cost_regime: str
    costs_minor: dict[str, int | float]
    horizon_hours: float
    max_interventions: int
    max_retries: int
    max_contacts: int
    min_retry_interval_hours: float
    action_stage_min_support: int
    calibration_bin_min_support: int
    normalized_erv_margin_threshold: float
    stopping_rules: tuple[str, ...]
    development_seeds: tuple[int, ...]
    validation_seeds: tuple[int, ...]
    baseline_artifact: str
    baseline_sha256: str
    config_hash: str
    validation_status: str
