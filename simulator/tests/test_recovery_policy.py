from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from recoveriq_policy.config import (
    OVERALL_FINAL_SEEDS,
    PHASE4_HELDOUT_SEEDS,
    POLICY_DEVELOPMENT_SEEDS,
    POLICY_VALIDATION_SEEDS,
)
from recoveriq_policy.economics import economic_score, expected_recovered_minor
from recoveriq_policy.engine import RecoverIQPolicyEngine
from recoveriq_policy.models import (
    CandidateAction,
    CandidatePrediction,
    DecisionKind,
    DecisionPolicyFacts,
    FrozenBaselineArtifact,
    FrozenPolicyArtifact,
    PolicyOperationalProfile,
    RuleResult,
    SupportDiagnostic,
)
from recoveriq_policy.rules import hard_feasibility_checks
from recoveriq_policy_evaluation.validation import evaluate_validation_frame, run_validation_once
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.observation import RecoveryAction

REPOSITORY = Path(__file__).resolve().parents[2]
POLICY_ROOT = REPOSITORY / "artifacts" / "policy" / "recoveriq-policy-v1"


def _facts(
    *,
    retries: int = 0,
    contacts: int = 0,
    contact_allowed: bool = True,
    active_link: bool = False,
    alternate_available: bool = True,
    quiet_hours: bool = False,
) -> DecisionPolicyFacts:
    return DecisionPolicyFacts(
        decision_key="test-decision",
        decision_at=datetime(2027, 1, 1, 12, tzinfo=UTC),
        payment_amount_minor=100_000,
        failure_to_decision_hours=1,
        current_retry_count=retries,
        current_contact_count=contacts,
        operational=PolicyOperationalProfile(
            customer_contact_allowed=contact_allowed,
            existing_active_payment_link=active_link,
            alternate_method_available=alternate_available,
            quiet_hours=quiet_hours,
        ),
    )


def _prediction(
    label: str,
    action_type: ActionType,
    probability: str,
    *,
    delay: float = 0,
    intervention: int = 0,
    friction: int = 0,
    low_support: bool = False,
) -> CandidatePrediction:
    decision_at = datetime(2027, 1, 1, 12, tzinfo=UTC)
    contact = action_type in {
        ActionType.SEND_NUDGE,
        ActionType.CREATE_PAYMENT_LINK,
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        ActionType.OFFER_ALTERNATE_METHOD,
    }
    return CandidatePrediction(
        candidate=CandidateAction(
            label=label,
            recovery_action=RecoveryAction(
                action_id=f"action-{label}",
                action_type=action_type,
                execute_at=decision_at + timedelta(hours=delay),
                scheduled_delay_hours=delay,
                attempt_number=1
                if action_type in {ActionType.RETRY_NOW, ActionType.RETRY_LATER}
                else 0,
                intervention_cost_minor=intervention,
                friction_cost_minor=friction,
            ),
            is_customer_contact=contact,
            requests_method_change=action_type
            in {
                ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
                ActionType.OFFER_ALTERNATE_METHOD,
            },
        ),
        raw_probability=Decimal("0.99"),
        calibrated_probability=Decimal(probability),
        support=SupportDiagnostic(
            action_training_count=10_000,
            calibration_bin=5,
            calibration_bin_count=1_000,
            low_support=low_support,
            reasons=("CALIBRATION_BIN_SUPPORT",) if low_support else (),
        ),
        model_name="lightgbm",
    )


def _checks(prediction: CandidatePrediction, facts: DecisionPolicyFacts) -> dict[str, RuleResult]:
    return {check.policy_id: check.result for check in hard_feasibility_checks(prediction, facts)}


def test_money_arithmetic_is_decimal_half_up_and_uses_calibrated_probability() -> None:
    assert expected_recovered_minor(Decimal("0.005"), 100) == 1
    prediction = _prediction(
        "RETRY_NOW",
        ActionType.RETRY_NOW,
        "0.25",
        intervention=250,
        friction=100,
    )
    score = economic_score(prediction, 100_000)
    assert score.expected_recovered_minor == 25_000
    assert score.erv_minor == 24_650
    assert prediction.raw_probability == Decimal("0.99")


def test_policy_package_has_no_oracle_or_ground_truth_import() -> None:
    policy_root = REPOSITORY / "simulator" / "recoveriq_policy"
    core_files = (
        "candidates.py",
        "config.py",
        "economics.py",
        "engine.py",
        "models.py",
        "rules.py",
        "scoring.py",
    )
    source = "\n".join((policy_root / name).read_text(encoding="utf-8") for name in core_files)
    assert "recoveriq_policy_evaluation" not in source
    assert "ground_truth" not in source
    assert "oracle" not in source.lower()


@pytest.mark.parametrize(
    ("facts", "prediction", "policy_id"),
    (
        (
            _facts(retries=2),
            _prediction("RETRY_NOW", ActionType.RETRY_NOW, "0.8"),
            "MAX_RETRY_COUNT",
        ),
        (
            _facts(contacts=2),
            _prediction("SEND_NUDGE", ActionType.SEND_NUDGE, "0.8"),
            "MAX_CONTACT_COUNT",
        ),
        (
            _facts(contact_allowed=False),
            _prediction("SEND_NUDGE", ActionType.SEND_NUDGE, "0.8"),
            "CUSTOMER_OPT_OUT",
        ),
        (
            _facts(quiet_hours=True),
            _prediction("SEND_NUDGE", ActionType.SEND_NUDGE, "0.8"),
            "QUIET_HOURS",
        ),
        (
            _facts(active_link=True),
            _prediction("CREATE_PAYMENT_LINK", ActionType.CREATE_PAYMENT_LINK, "0.8"),
            "DUPLICATE_PAYMENT_LINK",
        ),
        (
            _facts(alternate_available=False),
            _prediction("OFFER_ALTERNATE_METHOD", ActionType.OFFER_ALTERNATE_METHOD, "0.8"),
            "ALTERNATE_METHOD_UNAVAILABLE",
        ),
    ),
)
def test_infeasible_actions_receive_explicit_blocks(
    facts: DecisionPolicyFacts,
    prediction: CandidatePrediction,
    policy_id: str,
) -> None:
    assert _checks(prediction, facts)[policy_id] is RuleResult.BLOCK


def test_blocked_candidate_is_never_selected() -> None:
    blocked = _prediction("SEND_NUDGE", ActionType.SEND_NUDGE, "0.99")
    allowed = _prediction("RETRY_LATER_6H", ActionType.RETRY_LATER, "0.40", delay=6)
    decision = RecoverIQPolicyEngine(
        policy_config_hash="test",
        normalized_margin_threshold=Decimal("0"),
    ).decide(_facts(contact_allowed=False), (blocked, allowed))
    assert decision.decision_kind is DecisionKind.ACTION
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.prediction.candidate.label == "RETRY_LATER_6H"


def test_all_nonpositive_actions_stop_without_intervention() -> None:
    prediction = _prediction(
        "RETRY_NOW",
        ActionType.RETRY_NOW,
        "0",
        intervention=250,
        friction=100,
    )
    decision = RecoverIQPolicyEngine(
        policy_config_hash="test",
        normalized_margin_threshold=Decimal("0"),
    ).decide(_facts(), (prediction,))
    assert decision.decision_kind is DecisionKind.STOP
    assert decision.selected_candidate is None


def test_small_margin_reviews_without_automated_side_effect() -> None:
    predictions = (
        _prediction("RETRY_NOW", ActionType.RETRY_NOW, "0.500"),
        _prediction("RETRY_LATER_2H", ActionType.RETRY_LATER, "0.499", delay=2),
    )
    decision = RecoverIQPolicyEngine(
        policy_config_hash="test",
        normalized_margin_threshold=Decimal("0.01"),
    ).decide(_facts(), predictions)
    assert decision.decision_kind is DecisionKind.HUMAN_REVIEW
    assert decision.selected_candidate is None
    assert decision.decision_rules[0].policy_id == "LOW_DECISION_MARGIN"


def test_low_support_reviews_instead_of_falling_through() -> None:
    unsupported = _prediction("RETRY_NOW", ActionType.RETRY_NOW, "0.8", low_support=True)
    supported = _prediction("RETRY_LATER_2H", ActionType.RETRY_LATER, "0.7", delay=2)
    decision = RecoverIQPolicyEngine(
        policy_config_hash="test",
        normalized_margin_threshold=Decimal("0"),
    ).decide(_facts(), (unsupported, supported))
    assert decision.decision_kind is DecisionKind.HUMAN_REVIEW
    assert decision.selected_candidate is None


def test_detector_watch_and_confirmed_have_no_hard_policy_authority() -> None:
    facts_fields = set(DecisionPolicyFacts.model_fields)
    assert not any("health" in field or "detector" in field for field in facts_fields)
    rules_source = (REPOSITORY / "simulator" / "recoveriq_policy" / "rules.py").read_text(
        encoding="utf-8"
    )
    assert "WATCH" not in rules_source
    assert "CONFIRMED" not in rules_source


def test_empty_prediction_schema_abstains() -> None:
    decision = RecoverIQPolicyEngine(
        policy_config_hash="test",
        normalized_margin_threshold=Decimal("0"),
    ).decide(_facts(), ())
    assert decision.decision_kind is DecisionKind.HUMAN_REVIEW
    assert decision.selected_candidate is None
    assert decision.decision_rules[0].policy_id == "MODEL_SCHEMA_INVALID"


def test_frozen_seed_groups_and_baselines_are_guarded() -> None:
    assert set(POLICY_DEVELOPMENT_SEEDS).isdisjoint(POLICY_VALIDATION_SEEDS)
    assert set(POLICY_VALIDATION_SEEDS).isdisjoint(PHASE4_HELDOUT_SEEDS)
    assert set(POLICY_VALIDATION_SEEDS).isdisjoint(OVERALL_FINAL_SEEDS)
    baselines = FrozenBaselineArtifact.model_validate_json(
        (POLICY_ROOT / "development-baselines-v1.json").read_text(encoding="utf-8")
    )
    assert baselines.development_seeds == POLICY_DEVELOPMENT_SEEDS
    assert baselines.reason_min_support == 200
    assert baselines.reason_method_min_support == 500


def test_policy_config_hash_is_reproducible() -> None:
    policy = FrozenPolicyArtifact.model_validate_json(
        (POLICY_ROOT / "recoveriq-policy-v1.json").read_text(encoding="utf-8")
    )
    payload = policy.model_dump(mode="json")
    for key in ("artifact_type", "config_hash", "validation_status"):
        payload.pop(key)
    payload["normalized_erv_margin_threshold"] = str(policy.normalized_erv_margin_threshold)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=list).encode()
    ).hexdigest()
    assert digest == policy.config_hash


def test_same_context_model_and_config_is_deterministic() -> None:
    predictions = (
        _prediction("RETRY_NOW", ActionType.RETRY_NOW, "0.55"),
        _prediction("RETRY_LATER_2H", ActionType.RETRY_LATER, "0.50", delay=2),
    )
    engine = RecoverIQPolicyEngine(
        policy_config_hash="test",
        normalized_margin_threshold=Decimal("0"),
    )
    first = engine.decide(_facts(), predictions)
    second = engine.decide(_facts(), predictions)
    assert first == second


def test_tuning_code_cannot_execute_registered_validation() -> None:
    audit_source = (
        REPOSITORY / "simulator" / "recoveriq_policy_evaluation" / "audit.py"
    ).read_text(encoding="utf-8")
    development_source = (
        REPOSITORY / "simulator" / "recoveriq_policy_evaluation" / "development.py"
    ).read_text(encoding="utf-8")
    assert "POLICY_VALIDATION_SEEDS" not in audit_source
    assert "generate_candidate_evaluation_frame" not in development_source
    assert evaluate_validation_frame.__doc__ is not None


def test_validation_harness_smoke_preserves_first_action_attribution() -> None:
    full = pd.read_parquet(POLICY_ROOT / "development-candidates-v1.parquet")
    decision_keys = full["decision_key"].drop_duplicates().head(25)
    frame = full[full["decision_key"].isin(decision_keys)].copy()
    policy = FrozenPolicyArtifact.model_validate_json(
        (POLICY_ROOT / "recoveriq-policy-v1.json").read_text(encoding="utf-8")
    )
    baselines = FrozenBaselineArtifact.model_validate_json(
        (POLICY_ROOT / "development-baselines-v1.json").read_text(encoding="utf-8")
    )
    report, records, trace, _ = evaluate_validation_frame(
        frame,
        policy=policy,
        baselines=baselines,
        workflows={},
        capture_trace=True,
    )
    assert records.groupby("strategy").size().nunique() == 1
    assert records.groupby(["strategy", "decision_key"]).size().max() == 1
    no_action = records[records["decision_kind"] != DecisionKind.ACTION.value]
    assert not no_action["recovered"].any()
    assert (no_action["gross_recovered_minor"] == 0).all()
    assert (no_action["action_count"] == 0).all()
    assert report["validation_gates"]["deterministic_safety"]["pass"]
    assert trace is not None
    assert trace["outcome"] is not None


def test_completed_registered_validation_refuses_rerun() -> None:
    with pytest.raises(FileExistsError, match="already attempted"):
        run_validation_once(
            artifact_root=POLICY_ROOT,
            model_root=REPOSITORY / "artifacts" / "ml" / "models" / "recovery-model-v1",
            calibration_root=REPOSITORY / "artifacts" / "ml" / "calibration" / "recovery-model-v1",
            frozen_detector_path=REPOSITORY
            / "artifacts"
            / "detector_v2"
            / "degradation-detector-v2.json",
        )


def test_validation_artifact_is_compact_and_digest_sealed() -> None:
    report_path = POLICY_ROOT / "validation-evaluation-v1.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    workflow = report["existing_workflow_view"]
    assert "per_seed_raw_evaluations" not in workflow
    assert len(workflow["per_seed_metrics"]) == 10
    attempt = json.loads((POLICY_ROOT / "validation-attempt-v1.json").read_text())
    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == attempt["result_sha256"]
