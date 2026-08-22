from __future__ import annotations

import hashlib
import inspect
import json
from datetime import timedelta

import pytest

from recoveriq_ml_v2.features import build_feature_snapshot_v2
from recoveriq_ml_v2.logging import (
    UniformObservableSequentialBehavior,
    generate_sequential_trajectories,
)
from recoveriq_ml_v2.models import MODEL_V2_FEATURE_ALLOWLIST, RecoveryFeatureSnapshotV2
from recoveriq_sequential.config import (
    EPISODE_HORIZON_HOURS,
    MAX_AUTONOMOUS_INTERVENTIONS,
    MAX_CONTACTS,
    MAX_RETRIES,
    MODEL_V2_CALIBRATION_SEEDS,
    MODEL_V2_DEVELOPMENT_SEEDS,
    MODEL_V2_HELDOUT_SEEDS,
    OVERALL_FINAL_SEEDS,
    SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
    SEQUENTIAL_POLICY_VALIDATION_SEEDS,
    SEQUENTIAL_TRAINING_SEEDS,
)
from recoveriq_sequential.episodes import (
    advance_episode_state,
    build_episode_templates,
    generate_sequential_candidates,
    initial_episode_state,
)
from recoveriq_sequential.models import (
    EpisodeTermination,
    SequentialActionOutcome,
    SequentialCandidate,
    SequentialEpisodeState,
    SequentialEpisodeTemplate,
)
from recoveriq_sequential.oracle import SequentialScenarioOracle
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.scenario import ScenarioGenerator

FORBIDDEN_V2_FEATURES = {
    "seed",
    "customer_id",
    "payment_id",
    "subscription_id",
    "merchant_id",
    "true_failure_cause",
    "hidden_failure_family",
    "incident_id",
    "instrument_state",
    "oracle_probability",
    "counterfactual_outcome",
}


@pytest.fixture(scope="module")
def sequential_world() -> tuple[SimulatorConfig, GeneratedScenario]:
    config = SimulatorConfig(
        seed=20_280_301,
        num_payment_attempts=800,
        customer_count=200,
        subscription_count=200,
        incident_count=6,
    )
    return config, ScenarioGenerator(config).generate()


@pytest.fixture(scope="module")
def sequential_result(sequential_world):  # type: ignore[no-untyped-def]
    config, scenario = sequential_world
    return generate_sequential_trajectories(
        scenario,
        config,
        include_candidate_truth=False,
    )


def test_logging_policy_has_no_hidden_oracle_input() -> None:
    signature = inspect.signature(UniformObservableSequentialBehavior.select)
    assert set(signature.parameters) == {
        "self",
        "seed",
        "episode_id",
        "decision_index",
        "candidates",
    }
    source = inspect.getsource(UniformObservableSequentialBehavior.select)
    assert "oracle" not in source
    assert "ground_truth" not in source
    assert "probability" not in source


def test_one_action_propensity_and_current_action_attribution(sequential_result) -> None:  # type: ignore[no-untyped-def]
    rows = sequential_result.logged_rows
    assert rows
    assert len({str(row["decision_key"]) for row in rows}) == len(rows)
    assert all(
        float(row["selection_propensity"]) == 1 / int(row["feasible_candidate_count"])
        for row in rows
    )
    assert all(1 / 9 <= float(row["selection_propensity"]) <= 1 for row in rows)
    positives = [row for row in rows if row["action_recovered_before_next_decision"]]
    assert all(row["episode_termination_after_action"] == "RECOVERED" for row in positives)
    positive_episodes = [str(row["episode_id"]) for row in positives]
    assert len(positive_episodes) == len(set(positive_episodes))
    assert sequential_result.candidate_truth_rows == ()


def test_same_seed_generates_identical_trajectories(sequential_world, sequential_result) -> None:  # type: ignore[no-untyped-def]
    config, scenario = sequential_world
    repeated = generate_sequential_trajectories(
        scenario,
        config,
        include_candidate_truth=False,
    )
    first = json.dumps(sequential_result.logged_rows, sort_keys=True, default=str)
    second = json.dumps(repeated.logged_rows, sort_keys=True, default=str)
    assert hashlib.sha256(first.encode()).hexdigest() == hashlib.sha256(second.encode()).hexdigest()


def test_model_v2_schema_excludes_health_hidden_and_identity() -> None:
    fields = set(MODEL_V2_FEATURE_ALLOWLIST)
    assert fields.isdisjoint(FORBIDDEN_V2_FEATURES)
    assert not any("health" in field or "detector" in field for field in fields)
    assert set(RecoveryFeatureSnapshotV2.model_fields) == {
        "feature_schema_version",
        *MODEL_V2_FEATURE_ALLOWLIST,
    }


def test_later_decision_features_use_updated_past_state(sequential_world) -> None:  # type: ignore[no-untyped-def]
    config, scenario = sequential_world
    template = build_episode_templates(scenario, config.seed)[0]
    state = initial_episode_state(template)
    selected = _candidate(template, state, config, "RETRY_LATER_2H")
    failed = _outcome(state, selected, recovered=False)
    later = advance_episode_state(template, state, selected, failed)
    next_candidate = generate_sequential_candidates(template, later, config.resolved_costs)[0]
    features = build_feature_snapshot_v2(template, later, next_candidate)
    assert features.decision_index == 2
    assert features.prior_autonomous_interventions == 1
    assert features.retries_executed == 1
    assert features.last_action_label == "RETRY_LATER_2H"
    assert features.previous_intervention_result == "FAILED"
    assert features.hours_since_last_action == pytest.approx(2.0)


def test_caps_opt_out_duplicate_link_and_quiet_hour_scheduling(sequential_world) -> None:  # type: ignore[no-untyped-def]
    config, scenario = sequential_world
    template = build_episode_templates(scenario, config.seed)[0]
    state = initial_episode_state(template)
    capped = state.model_copy(update={"retry_count": MAX_RETRIES, "contact_count": MAX_CONTACTS})
    assert generate_sequential_candidates(template, capped, config.resolved_costs) == ()

    opted_out = template.model_copy(
        update={
            "operational": template.operational.model_copy(
                update={"customer_contact_allowed": False}
            )
        }
    )
    labels = {
        candidate.label
        for candidate in generate_sequential_candidates(opted_out, state, config.resolved_costs)
    }
    assert labels
    assert labels.isdisjoint(
        {
            "SEND_NUDGE",
            "CREATE_PAYMENT_LINK",
            "REQUEST_PAYMENT_METHOD_UPDATE",
            "OFFER_ALTERNATE_METHOD",
        }
    )

    linked = state.model_copy(update={"active_payment_link": True, "payment_link_count": 1})
    labels = {
        candidate.label
        for candidate in generate_sequential_candidates(template, linked, config.resolved_costs)
    }
    assert "CREATE_PAYMENT_LINK" not in labels

    quiet_at = state.decision_at.replace(hour=23, minute=0, second=0, microsecond=0)
    quiet = state.model_copy(
        update={"decision_at": quiet_at, "horizon_at": quiet_at + timedelta(hours=48)}
    )
    contacts = [
        candidate
        for candidate in generate_sequential_candidates(template, quiet, config.resolved_costs)
        if candidate.is_customer_contact
    ]
    assert contacts
    assert all(candidate.quiet_hours_delay_applied for candidate in contacts)
    assert all(candidate.recovery_action.execute_at.hour == 7 for candidate in contacts)


def test_recovery_terminates_immediately_and_attribution_is_once(sequential_world) -> None:  # type: ignore[no-untyped-def]
    config, scenario = sequential_world
    template = build_episode_templates(scenario, config.seed)[0]
    state = initial_episode_state(template)
    selected = generate_sequential_candidates(template, state, config.resolved_costs)[0]
    recovered = advance_episode_state(template, state, selected, _outcome(state, selected, True))
    assert recovered.termination is EpisodeTermination.RECOVERED
    assert recovered.recovery_action_id == selected.recovery_action.action_id
    assert recovered.recovery_decision_index == 1
    assert generate_sequential_candidates(template, recovered, config.resolved_costs) == ()
    with pytest.raises(ValueError, match="terminated episode"):
        advance_episode_state(template, recovered, selected, _outcome(recovered, selected, True))


def test_horizon_and_three_intervention_bound_are_enforced(sequential_world) -> None:  # type: ignore[no-untyped-def]
    config, scenario = sequential_world
    template = build_episode_templates(scenario, config.seed)[0]
    state = initial_episode_state(template)
    assert (state.horizon_at - state.decision_at).total_seconds() / 3600 == EPISODE_HORIZON_HOURS
    for _ in range(MAX_AUTONOMOUS_INTERVENTIONS):
        selected = generate_sequential_candidates(template, state, config.resolved_costs)[0]
        state = advance_episode_state(template, state, selected, _outcome(state, selected, False))
    assert state.intervention_count == MAX_AUTONOMOUS_INTERVENTIONS
    assert state.termination is EpisodeTermination.MAX_INTERVENTIONS
    assert generate_sequential_candidates(template, state, config.resolved_costs) == ()

    state = initial_episode_state(template)
    near_horizon = state.model_copy(update={"decision_at": state.horizon_at - timedelta(hours=1)})
    selected = _candidate(template, near_horizon, config, "RETRY_NOW")
    ended = advance_episode_state(
        template,
        near_horizon,
        selected,
        _outcome(near_horizon, selected, False),
    )
    assert ended.termination is EpisodeTermination.HORIZON_EXHAUSTED
    assert ended.decision_at == ended.horizon_at


def test_registered_seed_groups_are_disjoint_and_final_is_inaccessible() -> None:
    groups = (
        SEQUENTIAL_TRAINING_SEEDS,
        MODEL_V2_DEVELOPMENT_SEEDS,
        MODEL_V2_CALIBRATION_SEEDS,
        MODEL_V2_HELDOUT_SEEDS,
        SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
        SEQUENTIAL_POLICY_VALIDATION_SEEDS,
    )
    for index, group in enumerate(groups):
        assert set(group).isdisjoint(OVERALL_FINAL_SEEDS)
        for other in groups[index + 1 :]:
            assert set(group).isdisjoint(other)
    tuning_sources = "\n".join(
        inspect.getsource(item)
        for item in (
            generate_sequential_trajectories,
            UniformObservableSequentialBehavior,
        )
    )
    assert "MODEL_V2_HELDOUT_SEEDS" not in tuning_sources
    assert "SEQUENTIAL_POLICY_VALIDATION_SEEDS" not in tuning_sources
    assert "OVERALL_FINAL_SEEDS" not in tuning_sources


def test_oracle_is_a_separate_evaluation_only_adapter() -> None:
    logging_source = inspect.getsource(generate_sequential_trajectories)
    behavior_source = inspect.getsource(UniformObservableSequentialBehavior)
    assert "SequentialScenarioOracle" in logging_source
    assert "SequentialScenarioOracle" not in behavior_source
    assert (
        SequentialScenarioOracle.__doc__ is None
        or "policy" not in SequentialScenarioOracle.__doc__.lower()
    )


def _candidate(
    template: SequentialEpisodeTemplate,
    state: SequentialEpisodeState,
    config: SimulatorConfig,
    label: str,
) -> SequentialCandidate:
    return next(
        candidate
        for candidate in generate_sequential_candidates(template, state, config.resolved_costs)
        if candidate.label == label
    )


def _outcome(
    state: SequentialEpisodeState,
    candidate: SequentialCandidate,
    recovered: bool,
) -> SequentialActionOutcome:
    return SequentialActionOutcome(
        episode_id=state.episode_id,
        decision_index=state.decision_index,
        candidate_label=candidate.label,
        action_id=candidate.recovery_action.action_id,
        executed_at=candidate.recovery_action.execute_at,
        recovered=recovered,
        oracle_probability=0.5,
        recovered_amount_minor=49_900 if recovered else 0,
    )
