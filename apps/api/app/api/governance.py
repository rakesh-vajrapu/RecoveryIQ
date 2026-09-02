import json
from enum import StrEnum
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError

router = APIRouter()


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GovernanceLimits(ApiModel):
    recovery_horizon_hours: float
    max_autonomous_interventions: int
    max_retries: int
    max_contacts: int
    minimum_retry_interval_hours: float


class EnforcementAction(StrEnum):
    STOP = "STOP"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    FILTER_ACTION = "FILTER_ACTION"
    SCHEDULE_ACTION = "SCHEDULE_ACTION"
    ACCOUNTING_INVARIANT = "ACCOUNTING_INVARIANT"


class RuleCategory(StrEnum):
    AUTONOMY_BOUND = "AUTONOMY_BOUND"
    CUSTOMER_PROTECTION = "CUSTOMER_PROTECTION"
    ACTION_FEASIBILITY = "ACTION_FEASIBILITY"
    EVIDENCE_GATE = "EVIDENCE_GATE"
    ECONOMIC_STOP = "ECONOMIC_STOP"
    ACCOUNTING_SAFETY = "ACCOUNTING_SAFETY"


class EpisodeTermination(StrEnum):
    YES = "YES"
    NO = "NO"
    CONDITIONAL = "CONDITIONAL"


class GovernanceRule(ApiModel):
    id: str
    category: RuleCategory
    effect: str
    enforcement: EnforcementAction
    episode_termination: EpisodeTermination


class GovernanceAuthority(ApiModel):
    model: str = "ESTIMATES"
    erv: str = "RANKS"
    policy: str = "AUTHORIZES"
    provider: str = "VERIFIES"
    llm: str = "EXPLAINS_ONLY"


class GovernanceProfileResponse(ApiModel):
    profile_name: str
    policy_version: str
    model_version: str
    config_hash: str
    evidence_lane: str
    limits: GovernanceLimits
    rules: list[GovernanceRule]
    authority: GovernanceAuthority


class FrozenPolicyArtifact(BaseModel):
    artifact_type: str
    policy_version: str
    model_version: str
    config_hash: str
    cost_regime: str
    horizon_hours: float
    max_interventions: int
    max_retries: int
    max_contacts: int
    min_retry_interval_hours: float
    stopping_rules: list[str]
    validation_status: str


def load_frozen_policy() -> FrozenPolicyArtifact:
    current_dir = Path(__file__).resolve().parent
    repository_root = current_dir.parents[3]
    policy_path = (
        repository_root
        / "artifacts"
        / "policy"
        / "recoveriq-sequential-v2"
        / "recoveriq-sequential-policy-v2.json"
    )
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    try:
        with open(policy_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError("Frozen governance profile artifact is corrupt") from exc

    try:
        artifact = FrozenPolicyArtifact(**data)
    except ValidationError as exc:
        raise ValueError(
            "Frozen governance profile artifact does not match required schema"
        ) from exc

    if artifact.artifact_type != "frozen_bounded_sequential_policy":
        raise ValueError("Invalid artifact_type in policy artifact")

    return artifact


@router.get(
    "/api/governance/profile",
    response_model=GovernanceProfileResponse,
    tags=["governance"],
)
def get_governance_profile() -> GovernanceProfileResponse:
    try:
        policy = load_frozen_policy()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500, detail="Frozen governance profile artifact is missing"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    limits = GovernanceLimits(
        recovery_horizon_hours=policy.horizon_hours,
        max_autonomous_interventions=policy.max_interventions,
        max_retries=policy.max_retries,
        max_contacts=policy.max_contacts,
        minimum_retry_interval_hours=policy.min_retry_interval_hours,
    )

    rules = [
        GovernanceRule(
            id="MAX_INTERVENTIONS",
            category=RuleCategory.AUTONOMY_BOUND,
            effect="Intervention budget exceeded",
            enforcement=EnforcementAction.STOP,
            episode_termination=EpisodeTermination.YES,
        ),
        GovernanceRule(
            id="RECOVERY_HORIZON",
            category=RuleCategory.AUTONOMY_BOUND,
            effect="48h horizon exceeded",
            enforcement=EnforcementAction.STOP,
            episode_termination=EpisodeTermination.YES,
        ),
        GovernanceRule(
            id="NON_POSITIVE_INCREMENTAL_ERV",
            category=RuleCategory.ECONOMIC_STOP,
            effect="Best incremental ERV <= 0",
            enforcement=EnforcementAction.STOP,
            episode_termination=EpisodeTermination.YES,
        ),
        GovernanceRule(
            id="BUDGETS_EXHAUSTED",
            category=RuleCategory.AUTONOMY_BOUND,
            effect="Retry and contact budgets exhausted",
            enforcement=EnforcementAction.STOP,
            episode_termination=EpisodeTermination.YES,
        ),
        GovernanceRule(
            id="NO_FEASIBLE_ACTION",
            category=RuleCategory.ACTION_FEASIBILITY,
            effect="No feasible action remaining",
            enforcement=EnforcementAction.STOP,
            episode_termination=EpisodeTermination.YES,
        ),
        GovernanceRule(
            id="CUSTOMER_OPT_OUT",
            category=RuleCategory.CUSTOMER_PROTECTION,
            effect="Filters contact actions if customer opted out",
            enforcement=EnforcementAction.FILTER_ACTION,
            episode_termination=EpisodeTermination.CONDITIONAL,
        ),
        GovernanceRule(
            id="QUIET_HOURS_SCHEDULE",
            category=RuleCategory.CUSTOMER_PROTECTION,
            effect="Schedules contact actions to end of quiet hours",
            enforcement=EnforcementAction.SCHEDULE_ACTION,
            episode_termination=EpisodeTermination.NO,
        ),
        GovernanceRule(
            id="DUPLICATE_PAYMENT_LINK",
            category=RuleCategory.ACTION_FEASIBILITY,
            effect="Filters payment link creation if active",
            enforcement=EnforcementAction.FILTER_ACTION,
            episode_termination=EpisodeTermination.CONDITIONAL,
        ),
        GovernanceRule(
            id="MAX_RETRIES",
            category=RuleCategory.AUTONOMY_BOUND,
            effect="Filters retry actions",
            enforcement=EnforcementAction.FILTER_ACTION,
            episode_termination=EpisodeTermination.CONDITIONAL,
        ),
        GovernanceRule(
            id="MAX_CONTACTS",
            category=RuleCategory.AUTONOMY_BOUND,
            effect="Filters contact actions",
            enforcement=EnforcementAction.FILTER_ACTION,
            episode_termination=EpisodeTermination.CONDITIONAL,
        ),
        GovernanceRule(
            id="MIN_RETRY_INTERVAL",
            category=RuleCategory.AUTONOMY_BOUND,
            effect="Filters immediate retry if < 2h",
            enforcement=EnforcementAction.FILTER_ACTION,
            episode_termination=EpisodeTermination.CONDITIONAL,
        ),
        GovernanceRule(
            id="ATTRIBUTION_ONCE",
            category=RuleCategory.ACCOUNTING_SAFETY,
            effect="Exactly-once success recording constraint in simulation",
            enforcement=EnforcementAction.ACCOUNTING_INVARIANT,
            episode_termination=EpisodeTermination.NO,
        ),
        GovernanceRule(
            id="MODEL_SCHEMA_VALID",
            category=RuleCategory.EVIDENCE_GATE,
            description="Ensure input context matches exactly what Model V2 was trained on.",
            effect="Pre-engine evaluation gate against required V2 schema",
            enforcement=EnforcementAction.HUMAN_REVIEW,
            episode_termination=EpisodeTermination.CONDITIONAL,
        ),
        GovernanceRule(
            id="MODEL_SUPPORT",
            category=RuleCategory.EVIDENCE_GATE,
            effect="action_stage_support < 500",
            enforcement=EnforcementAction.HUMAN_REVIEW,
            episode_termination=EpisodeTermination.YES,
        ),
        GovernanceRule(
            id="CALIBRATION_SUPPORT",
            category=RuleCategory.EVIDENCE_GATE,
            effect="Insufficient calibration support",
            enforcement=EnforcementAction.HUMAN_REVIEW,
            episode_termination=EpisodeTermination.YES,
        ),
        GovernanceRule(
            id="LOW_DECISION_MARGIN",
            category=RuleCategory.EVIDENCE_GATE,
            effect="Decision margin below threshold",
            enforcement=EnforcementAction.HUMAN_REVIEW,
            episode_termination=EpisodeTermination.YES,
        ),
    ]

    return GovernanceProfileResponse(
        profile_name=policy.cost_regime,
        policy_version=policy.policy_version,
        model_version=policy.model_version,
        config_hash=policy.config_hash,
        evidence_lane="SEALED_SIMULATED",
        limits=limits,
        rules=rules,
        authority=GovernanceAuthority(),
    )
