from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from recoveriq_ml_v2 import FEATURE_SCHEMA_V2_VERSION


class ModelV2Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecoveryFeatureSnapshotV2(ModelV2Base):
    feature_schema_version: str = FEATURE_SCHEMA_V2_VERSION

    payment_method: str
    issuer: str
    failure_reason: str
    failure_source: str
    action_type: str
    action_label: str
    last_action_type: str
    last_action_label: str
    previous_intervention_result: str

    amount_minor: int = Field(gt=0)
    attempt_number: int = Field(ge=1)
    decision_hour_sin: float = Field(ge=-1, le=1)
    decision_hour_cos: float = Field(ge=-1, le=1)
    decision_day_sin: float = Field(ge=-1, le=1)
    decision_day_cos: float = Field(ge=-1, le=1)
    elapsed_episode_hours: float = Field(ge=0, le=48)
    time_since_previous_payment_attempt_hours: float | None = Field(default=None, ge=0)
    time_since_last_successful_payment_hours: float | None = Field(default=None, ge=0)
    subscription_tenure_days: float = Field(ge=0)

    subscription_prior_attempts: int = Field(ge=0)
    subscription_prior_successes: int = Field(ge=0)
    subscription_success_rate: float | None = Field(default=None, ge=0, le=1)
    customer_prior_attempts: int = Field(ge=0)
    customer_prior_successes: int = Field(ge=0)
    customer_prior_failed_renewals: int = Field(ge=0)
    customer_prior_success_rate: float | None = Field(default=None, ge=0, le=1)

    decision_index: int = Field(ge=1, le=3)
    prior_autonomous_interventions: int = Field(ge=0, le=2)
    retries_executed: int = Field(ge=0, le=2)
    contacts_sent: int = Field(ge=0, le=2)
    payment_links_created: int = Field(ge=0)
    method_updates_requested: int = Field(ge=0)
    alternate_methods_used: int = Field(ge=0)
    existing_payment_link: bool
    method_update_requested: bool
    alternate_method_used: bool
    hours_since_last_action: float | None = Field(default=None, ge=0)

    action_delay_hours: float = Field(ge=0, le=24)
    action_observation_window_hours: float = Field(ge=0, le=6)
    customer_contact_action: bool
    payment_method_change_action: bool
    quiet_hours_delay_applied: bool

    def model_features(self) -> dict[str, str | int | float | bool | None]:
        return self.model_dump(exclude={"feature_schema_version"}, mode="python")


MODEL_V2_FEATURE_ALLOWLIST = tuple(
    name for name in RecoveryFeatureSnapshotV2.model_fields if name != "feature_schema_version"
)
MODEL_V2_CATEGORICAL_FEATURES = (
    "payment_method",
    "issuer",
    "failure_reason",
    "failure_source",
    "action_type",
    "action_label",
    "last_action_type",
    "last_action_label",
    "previous_intervention_result",
)


def feature_schema_v2_hash() -> str:
    fields = [
        {
            "name": name,
            "annotation": str(RecoveryFeatureSnapshotV2.model_fields[name].annotation),
        }
        for name in MODEL_V2_FEATURE_ALLOWLIST
    ]
    payload = json.dumps(
        {"version": FEATURE_SCHEMA_V2_VERSION, "fields": fields, "health_features": False},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


FEATURE_SCHEMA_V2_HASH = feature_schema_v2_hash()


class LoggedSequentialDecision(ModelV2Base):
    record_version: str = "2.0"
    episode_id: str
    decision_key: str
    decision_index: int = Field(ge=1, le=3)
    decision_at: datetime
    selected_action_label: str
    selected_action_type: str
    selection_propensity: float = Field(gt=0, le=1)
    feasible_candidate_count: int = Field(ge=1, le=9)
    action_recovered_before_next_decision: bool
    episode_termination_after_action: str
    features: RecoveryFeatureSnapshotV2


class SequentialDatasetManifest(ModelV2Base):
    artifact_type: str = "sequential_randomized_trajectory_dataset"
    group: str
    seeds: tuple[int, ...]
    episode_count: int
    decision_count: int
    decisions_by_index: dict[str, int]
    action_counts: dict[str, int]
    positive_count: int
    positive_rate: float | None
    propensity_distribution: dict[str, int]
    feature_schema_version: str = FEATURE_SCHEMA_V2_VERSION
    feature_schema_hash: str = FEATURE_SCHEMA_V2_HASH
    dataset_sha256: str
    software_versions: dict[str, str]


class FrozenModelV2Manifest(ModelV2Base):
    artifact_type: str = "frozen_trajectory_aware_recovery_model"
    model_version: str
    feature_schema_version: str
    feature_schema_hash: str
    primary_excludes_health: bool = True
    training_seeds: tuple[int, ...]
    development_seeds: tuple[int, ...]
    selected_lightgbm_candidate_index: int
    selected_lightgbm_hyperparameters: dict[str, Any]
    model_artifacts: dict[str, str]
    model_sha256: dict[str, str]
    development_metrics: dict[str, Any]
    training_decision_count: int
    training_episode_count: int
    action_stage_counts: dict[str, int]
    training_timestamp: datetime
    software_versions: dict[str, str]
