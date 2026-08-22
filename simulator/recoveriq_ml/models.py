from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from recoveriq_ml import FEATURE_SCHEMA_VERSION
from recoveriq_simulator.enums import ActionType


class MLModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecoveryFeatureSnapshot(MLModel):
    feature_schema_version: str = FEATURE_SCHEMA_VERSION

    payment_method: str
    issuer: str
    failure_reason: str
    failure_source: str
    action_type: str

    amount_minor: int = Field(gt=0)
    attempt_number: int = Field(ge=1)
    decision_hour_sin: float = Field(ge=-1, le=1)
    decision_hour_cos: float = Field(ge=-1, le=1)
    decision_day_sin: float = Field(ge=-1, le=1)
    decision_day_cos: float = Field(ge=-1, le=1)
    failure_to_decision_hours: float = Field(ge=0)
    time_since_previous_payment_attempt_hours: float | None = Field(default=None, ge=0)
    delay_hours: float = Field(ge=0, le=24)
    customer_contact_action: bool
    payment_method_change_action: bool
    current_contact_count: int = Field(ge=0)
    current_retry_count: int = Field(ge=0)

    subscription_prior_attempts: int = Field(ge=0)
    subscription_prior_successes: int = Field(ge=0)
    subscription_success_rate: float | None = Field(default=None, ge=0, le=1)
    customer_prior_attempts: int = Field(ge=0)
    customer_prior_successes: int = Field(ge=0)
    customer_prior_failed_renewals: int = Field(ge=0)
    customer_prior_success_rate: float | None = Field(default=None, ge=0, le=1)
    previous_recovery_attempts: int = Field(ge=0)
    previous_successful_recovery_count: int = Field(ge=0)
    previous_nudge_count: int = Field(ge=0)
    previous_retry_count: int = Field(ge=0)
    previous_payment_link_count: int = Field(ge=0)
    subscription_tenure_days: float = Field(ge=0)
    time_since_last_successful_payment_hours: float | None = Field(default=None, ge=0)

    health_issuer_available: bool
    health_issuer_baseline_success: float | None = Field(default=None, ge=0, le=1)
    health_issuer_baseline_attempts: int = Field(ge=0)
    health_issuer_rate_5m: float | None = Field(default=None, ge=0, le=1)
    health_issuer_attempts_5m: int = Field(ge=0)
    health_issuer_delta_5m: float | None = Field(default=None, ge=-1, le=1)
    health_issuer_rate_15m: float | None = Field(default=None, ge=0, le=1)
    health_issuer_attempts_15m: int = Field(ge=0)
    health_issuer_delta_15m: float | None = Field(default=None, ge=-1, le=1)
    health_issuer_rate_60m: float | None = Field(default=None, ge=0, le=1)
    health_issuer_attempts_60m: int = Field(ge=0)
    health_issuer_delta_60m: float | None = Field(default=None, ge=-1, le=1)
    health_issuer_maximum_llr: float = Field(ge=0)
    health_issuer_recovery_llr: float = Field(ge=0)
    health_issuer_failure_js: float | None = Field(default=None, ge=0, le=1)
    health_issuer_dominant_current_share: float | None = Field(default=None, ge=0, le=1)
    health_issuer_dominant_baseline_share: float | None = Field(default=None, ge=0, le=1)
    health_issuer_dominant_absolute_increase: float | None = Field(default=None, ge=-1, le=1)
    health_issuer_dominant_relative_lift: float | None = Field(default=None, ge=0)
    health_issuer_dominant_support: int = Field(ge=0)
    health_issuer_watch: bool
    health_issuer_confirmed: bool
    health_issuer_time_since_watch_hours: float | None = Field(default=None, ge=0)
    health_issuer_time_since_confirmed_hours: float | None = Field(default=None, ge=0)
    health_issuer_parent_method_watch: bool
    health_issuer_parent_global_watch: bool

    health_method_available: bool
    health_method_baseline_success: float | None = Field(default=None, ge=0, le=1)
    health_method_baseline_attempts: int = Field(ge=0)
    health_method_rate_5m: float | None = Field(default=None, ge=0, le=1)
    health_method_attempts_5m: int = Field(ge=0)
    health_method_delta_5m: float | None = Field(default=None, ge=-1, le=1)
    health_method_rate_15m: float | None = Field(default=None, ge=0, le=1)
    health_method_attempts_15m: int = Field(ge=0)
    health_method_delta_15m: float | None = Field(default=None, ge=-1, le=1)
    health_method_rate_60m: float | None = Field(default=None, ge=0, le=1)
    health_method_attempts_60m: int = Field(ge=0)
    health_method_delta_60m: float | None = Field(default=None, ge=-1, le=1)
    health_method_maximum_llr: float = Field(ge=0)
    health_method_recovery_llr: float = Field(ge=0)
    health_method_failure_js: float | None = Field(default=None, ge=0, le=1)
    health_method_watch: bool
    health_method_confirmed: bool

    health_global_available: bool
    health_global_baseline_success: float | None = Field(default=None, ge=0, le=1)
    health_global_baseline_attempts: int = Field(ge=0)
    health_global_rate_5m: float | None = Field(default=None, ge=0, le=1)
    health_global_attempts_5m: int = Field(ge=0)
    health_global_delta_5m: float | None = Field(default=None, ge=-1, le=1)
    health_global_rate_15m: float | None = Field(default=None, ge=0, le=1)
    health_global_attempts_15m: int = Field(ge=0)
    health_global_delta_15m: float | None = Field(default=None, ge=-1, le=1)
    health_global_rate_60m: float | None = Field(default=None, ge=0, le=1)
    health_global_attempts_60m: int = Field(ge=0)
    health_global_delta_60m: float | None = Field(default=None, ge=-1, le=1)
    health_global_maximum_llr: float = Field(ge=0)
    health_global_recovery_llr: float = Field(ge=0)
    health_global_failure_js: float | None = Field(default=None, ge=0, le=1)
    health_global_watch: bool
    health_global_confirmed: bool

    def model_features(self) -> dict[str, str | int | float | bool | None]:
        return self.model_dump(exclude={"feature_schema_version"}, mode="python")


MODEL_FEATURE_ALLOWLIST = tuple(
    name for name in RecoveryFeatureSnapshot.model_fields if name != "feature_schema_version"
)
CATEGORICAL_FEATURES = (
    "payment_method",
    "issuer",
    "failure_reason",
    "failure_source",
    "action_type",
)
HEALTH_FEATURES = tuple(name for name in MODEL_FEATURE_ALLOWLIST if name.startswith("health_"))
NUMERIC_FEATURES = tuple(
    name for name in MODEL_FEATURE_ALLOWLIST if name not in CATEGORICAL_FEATURES
)
NON_HEALTH_FEATURES = tuple(name for name in MODEL_FEATURE_ALLOWLIST if name not in HEALTH_FEATURES)


def feature_schema_hash() -> str:
    fields = [
        {
            "name": name,
            "annotation": str(RecoveryFeatureSnapshot.model_fields[name].annotation),
        }
        for name in MODEL_FEATURE_ALLOWLIST
    ]
    payload = json.dumps(
        {"version": FEATURE_SCHEMA_VERSION, "fields": fields},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


FEATURE_SCHEMA_HASH = feature_schema_hash()


class LoggedRecoveryExample(MLModel):
    record_version: str = "1.0"
    decision_key: str
    decision_at: datetime
    feature_schema_hash: str = FEATURE_SCHEMA_HASH
    selected_action: ActionType
    delay_hours: float = Field(ge=0, le=24)
    selection_propensity: float = Field(gt=0, le=1)
    candidate_count: int = Field(ge=1)
    recovered_within_48h: bool
    features: RecoveryFeatureSnapshot


class LoggedDatasetManifest(MLModel):
    artifact_type: str = "randomized_exploration_logged_dataset"
    group: str
    seeds: tuple[int, ...]
    example_count: int = Field(ge=0)
    action_counts: dict[str, int]
    positive_count: int = Field(ge=0)
    positive_rate: float | None = Field(default=None, ge=0, le=1)
    feature_schema_version: str = FEATURE_SCHEMA_VERSION
    feature_schema_hash: str = FEATURE_SCHEMA_HASH
    logged_digest: str
    software_versions: dict[str, str]


class CalibrationMap(MLModel):
    method: str
    model_name: str
    artifact_path: str
    artifact_sha256: str


class FrozenModelManifest(MLModel):
    artifact_type: str = "frozen_action_conditioned_recovery_model"
    model_version: str
    feature_schema_version: str
    feature_schema_hash: str
    training_seeds: tuple[int, ...]
    development_seeds: tuple[int, ...]
    selected_lightgbm_candidate_index: int
    selected_lightgbm_hyperparameters: dict[str, Any]
    model_artifacts: dict[str, str]
    model_sha256: dict[str, str]
    development_metrics: dict[str, Any]
    training_example_count: int
    action_counts: dict[str, int]
    training_timestamp: datetime
    software_versions: dict[str, str]
