from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from recoveriq_ml.artifacts import sha256_file
from recoveriq_ml_v2.models import FEATURE_SCHEMA_V2_HASH
from recoveriq_sequential.config import (
    MAX_AUTONOMOUS_INTERVENTIONS,
    MAX_CONTACTS,
    MAX_RETRIES,
    OVERALL_FINAL_SEEDS,
    SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
    SEQUENTIAL_POLICY_VALIDATION_SEEDS,
)
from recoveriq_sequential.episodes import (
    build_episode_templates,
    generate_sequential_candidates,
    initial_episode_state,
)
from recoveriq_sequential.oracle import SequentialScenarioOracle
from recoveriq_sequential_policy import SEQUENTIAL_POLICY_V2_VERSION
from recoveriq_sequential_policy.development import load_frozen_baselines
from recoveriq_sequential_policy.engine import RecoverIQSequentialPolicyEngine
from recoveriq_sequential_policy.evaluation import RECOVERIQ, execute_strategy
from recoveriq_sequential_policy.models import (
    FrozenSequentialPolicy,
    SequentialCandidateScore,
    SequentialDecisionKind,
)
from recoveriq_sequential_policy.scoring import SequentialModelV2Scorer
from recoveriq_sequential_policy.validation import run_policy_validation_once
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator

REPOSITORY = Path(__file__).resolve().parents[2]
MODEL_ROOT = REPOSITORY / "artifacts" / "ml" / "models" / "recovery-model-v2"
CALIBRATION_ROOT = REPOSITORY / "artifacts" / "ml" / "calibration" / "recovery-model-v2"
POLICY_ROOT = REPOSITORY / "artifacts" / "policy" / "recoveriq-sequential-v2"


@pytest.fixture(scope="module")
def policy_world():  # type: ignore[no-untyped-def]
    config = SimulatorConfig(
        seed=20_280_304,
        num_payment_attempts=800,
        customer_count=200,
        subscription_count=200,
        incident_count=6,
    )
    scenario = ScenarioGenerator(config).generate()
    template = build_episode_templates(scenario, config.seed)[0]
    state = initial_episode_state(template)
    candidates = generate_sequential_candidates(template, state, config.resolved_costs)
    return config, scenario, template, state, candidates


def test_model_v2_scoring_is_deterministic(policy_world) -> None:  # type: ignore[no-untyped-def]
    _, _, template, state, candidates = policy_world
    scorer = SequentialModelV2Scorer(
        model_root=MODEL_ROOT,
        calibration_root=CALIBRATION_ROOT,
    )
    rows = [(template, state, candidate) for candidate in candidates]
    assert scorer.score(rows) == scorer.score(rows)


def test_sequential_policy_decisions_are_deterministic(policy_world) -> None:  # type: ignore[no-untyped-def]
    _, _, template, state, candidates = policy_world
    candidate = candidates[0]
    score = SequentialCandidateScore(
        candidate=candidate,
        probability=0.5,
        incremental_erv_minor=10_000,
        normalized_erv=0.2,
        action_stage_support=5_000,
        calibration_bin=5,
        calibration_bin_support=5_000,
    )
    engine = RecoverIQSequentialPolicyEngine(0.0)
    assert engine.decide(state, (score,)) == engine.decide(state, (score,))
    assert engine.decide(state, (score,)).kind is SequentialDecisionKind.ACTION
    assert template.observation.amount_minor > 0


def test_explicit_stop_and_support_review_have_no_selected_action(policy_world) -> None:  # type: ignore[no-untyped-def]
    _, _, _, state, candidates = policy_world
    engine = RecoverIQSequentialPolicyEngine(0.0)
    stopped = engine.decide(state, ())
    assert stopped.kind is SequentialDecisionKind.STOP
    assert stopped.selected is None

    unsupported = SequentialCandidateScore(
        candidate=candidates[0],
        probability=0.8,
        incremental_erv_minor=50_000,
        normalized_erv=0.5,
        action_stage_support=499,
        calibration_bin=8,
        calibration_bin_support=99,
    )
    reviewed = engine.decide(state, (unsupported,))
    assert reviewed.kind is SequentialDecisionKind.HUMAN_REVIEW
    assert reviewed.selected is None
    assert reviewed.reason == "MODEL_SUPPORT"


def test_human_review_terminates_autonomous_execution(policy_world) -> None:  # type: ignore[no-untyped-def]
    config, scenario, _, _, _ = policy_world
    templates = build_episode_templates(scenario, config.seed)[:50]
    records, _ = execute_strategy(
        seed=config.seed,
        strategy=RECOVERIQ,
        templates=templates,
        config=config,
        oracle=SequentialScenarioOracle(scenario, config),
        scorer=SequentialModelV2Scorer(
            model_root=MODEL_ROOT,
            calibration_root=CALIBRATION_ROOT,
        ),
        baselines=load_frozen_baselines(POLICY_ROOT),
        normalized_margin_threshold=1.0,
        capture_traces=False,
    )
    reviews = [row for row in records if row["human_review"]]
    assert reviews
    assert all(not row["stop_outcome"] for row in reviews)
    assert all(row["decision_count"] == row["action_count"] + 1 for row in reviews)


def test_frozen_policy_hash_limits_costs_and_model_binding() -> None:
    policy_path = POLICY_ROOT / "recoveriq-sequential-policy-v2.json"
    policy = FrozenSequentialPolicy.model_validate_json(policy_path.read_text(encoding="utf-8"))
    assert policy.policy_version == SEQUENTIAL_POLICY_V2_VERSION
    assert policy.feature_schema_hash == FEATURE_SCHEMA_V2_HASH
    assert policy.max_interventions == MAX_AUTONOMOUS_INTERVENTIONS == 3
    assert policy.max_retries == MAX_RETRIES == 2
    assert policy.max_contacts == MAX_CONTACTS == 2
    assert policy.cost_regime == "BALANCED"
    assert sha256_file(MODEL_ROOT / "lightgbm-v2.joblib") == policy.model_sha256
    assert sha256_file(POLICY_ROOT / policy.baseline_artifact) == policy.baseline_sha256
    payload = policy.model_dump(mode="json")
    for key in ("artifact_type", "config_hash", "validation_status"):
        payload.pop(key)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=list).encode()
    ).hexdigest()
    assert digest == policy.config_hash


def test_development_kept_validation_and_final_seeds_inaccessible() -> None:
    import recoveriq_sequential_policy.development as development

    source = inspect.getsource(development)
    assert "SEQUENTIAL_POLICY_VALIDATION_SEEDS" not in source
    assert "OVERALL_FINAL_SEEDS" not in source
    assert set(SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS).isdisjoint(SEQUENTIAL_POLICY_VALIDATION_SEEDS)
    assert set(SEQUENTIAL_POLICY_VALIDATION_SEEDS).isdisjoint(OVERALL_FINAL_SEEDS)


def test_full_horizon_development_used_one_initial_cohort_and_zero_violations() -> None:
    report = json.loads((POLICY_ROOT / "development-policy-v2.json").read_text(encoding="utf-8"))[
        "full_horizon_development"
    ]
    assert report["same_initial_hidden_episode_for_all_strategies"]
    assert all(row["policy_violations"] == 0 for row in report["strategies"].values())


def test_success_and_bounded_failure_traces_are_complete() -> None:
    success = json.loads(
        (POLICY_ROOT / "development-successful-trace-v2.json").read_text(encoding="utf-8")
    )
    failure = json.loads(
        (POLICY_ROOT / "development-failure-trace-v2.json").read_text(encoding="utf-8")
    )
    assert success["final"]["recovered"]
    assert len(success["decisions"]) >= 2
    assert not failure["final"]["recovered"]
    assert failure["final"]["action_count"] == 3
    assert failure["final"]["no_fourth_autonomous_action"]
    assert len(failure["decisions"]) == 3


def test_registered_validation_is_sealed_and_refuses_rerun() -> None:
    attempt = json.loads((POLICY_ROOT / "validation-attempt-v2.json").read_text(encoding="utf-8"))
    report = json.loads((POLICY_ROOT / "validation-evaluation-v2.json").read_text(encoding="utf-8"))
    assert attempt["status"] == "COMPLETED"
    assert report["validation_run_count"] == 1
    assert report["final_seeds_untouched"]
    assert report["full_horizon_evaluation"]["same_initial_hidden_episode_for_all_strategies"]
    assert all(
        claim["status"] == "PASS" for claim in report["preregistered_validation_claims"].values()
    )
    with pytest.raises(FileExistsError, match="already attempted"):
        run_policy_validation_once(
            artifact_root=POLICY_ROOT,
            model_root=MODEL_ROOT,
            calibration_root=CALIBRATION_ROOT,
        )
