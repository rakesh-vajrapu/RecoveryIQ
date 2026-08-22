from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from recoveriq_ml.models import RecoveryFeatureSnapshot
from recoveriq_simulator.observation import RecoveryAction


class PolicyModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DecisionKind(StrEnum):
    ACTION = "ACTION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    STOP = "STOP"


class RuleResult(StrEnum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


class PolicyOperationalProfile(PolicyModel):
    customer_contact_allowed: bool
    existing_active_payment_link: bool
    alternate_method_available: bool
    quiet_hours: bool


class PolicyDecisionContext(PolicyModel):
    decision_key: str
    decision_at: datetime
    base_features: RecoveryFeatureSnapshot
    operational: PolicyOperationalProfile


class DecisionPolicyFacts(PolicyModel):
    decision_key: str
    decision_at: datetime
    payment_amount_minor: int = Field(gt=0)
    failure_to_decision_hours: float = Field(ge=0)
    current_retry_count: int = Field(ge=0)
    current_contact_count: int = Field(ge=0)
    operational: PolicyOperationalProfile


class CandidateAction(PolicyModel):
    label: str
    recovery_action: RecoveryAction
    is_customer_contact: bool
    requests_method_change: bool


class SupportDiagnostic(PolicyModel):
    action_training_count: int = Field(ge=0)
    calibration_bin: int = Field(ge=0, le=9)
    calibration_bin_count: int = Field(ge=0)
    unknown_categories: tuple[str, ...] = ()
    low_support: bool
    reasons: tuple[str, ...] = ()


class CandidatePrediction(PolicyModel):
    candidate: CandidateAction
    raw_probability: Decimal = Field(ge=0, le=1)
    calibrated_probability: Decimal = Field(ge=0, le=1)
    support: SupportDiagnostic
    model_name: str


class EconomicScore(PolicyModel):
    expected_recovered_minor: int
    intervention_cost_minor: int
    friction_cost_minor: int
    erv_minor: int


class PolicyRuleEvidence(PolicyModel):
    policy_id: str
    result: RuleResult
    observed_value: str
    threshold: str
    reason: str


class DecisionCandidate(PolicyModel):
    prediction: CandidatePrediction
    economic: EconomicScore
    policy_checks: tuple[PolicyRuleEvidence, ...]
    final_policy_result: RuleResult


class RecoveryDecision(PolicyModel):
    policy_version: str
    policy_config_hash: str
    decision_key: str
    decision_kind: DecisionKind
    selected_candidate: DecisionCandidate | None
    candidates: tuple[DecisionCandidate, ...]
    absolute_erv_margin_minor: int | None
    normalized_erv_margin: Decimal | None
    decision_rules: tuple[PolicyRuleEvidence, ...]
    reason: str


class FrozenBaselineArtifact(PolicyModel):
    artifact_type: str = "policy_development_frozen_baselines"
    development_seeds: tuple[int, ...]
    selection_metric: str
    global_best_action: str
    global_action_order: tuple[str, ...]
    failure_reason_mapping: dict[str, str]
    failure_reason_method_mapping: dict[str, str]
    reason_min_support: int
    reason_method_min_support: int
    source_digest: str
    config_hash: str


class FrozenPolicyArtifact(PolicyModel):
    artifact_type: str = "frozen_recoveriq_erv_policy"
    policy_version: str
    policy_schema_version: str
    config_hash: str
    recovery_model_version: str
    recovery_model_sha256: str
    feature_schema_hash: str
    calibration_method: str
    calibration_sha256: str
    development_seeds: tuple[int, ...]
    validation_seeds: tuple[int, ...]
    final_seeds: tuple[int, ...]
    cost_regime: str
    candidate_labels: tuple[str, ...]
    max_retry_count: int
    max_contact_count: int
    min_retry_interval_hours: float
    quiet_hours_start_utc: int
    quiet_hours_end_utc: int
    min_action_training_support: int
    min_calibration_bin_support: int
    normalized_erv_margin_threshold: Decimal
    baseline_artifact_sha256: str
    validation_status: str = "NOT_RUN"
