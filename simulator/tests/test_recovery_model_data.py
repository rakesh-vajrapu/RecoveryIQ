from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from recoveriq_ml.artifacts import examples_digest, frozen_detector_v2_path
from recoveriq_ml.config import TARGET_HORIZON_HOURS
from recoveriq_ml.exploration import select_exploration_action
from recoveriq_ml.features import build_feature_snapshot
from recoveriq_ml.logged_data import LoggedDatasetGenerator
from recoveriq_ml.models import (
    FEATURE_SCHEMA_HASH,
    HEALTH_FEATURES,
    MODEL_FEATURE_ALLOWLIST,
    LoggedRecoveryExample,
    RecoveryFeatureSnapshot,
)
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import FailureReason, FailureSource, PaymentMethod
from recoveriq_simulator.observation import PaymentObservation
from recoveriq_simulator.scenario import ScenarioGenerator

FORBIDDEN_MODEL_FIELDS = {
    "customer_id",
    "payment_id",
    "subscription_id",
    "event_id",
    "merchant_id",
    "seed",
    "true_failure_cause",
    "hidden_incident_severity",
    "incident_id",
    "incident_end_time",
    "instrument_state",
    "oracle_probability",
    "counterfactual_outcome",
}


@pytest.fixture(scope="module")
def logged_result():  # type: ignore[no-untyped-def]
    config = _small_config(20_270_101)
    scenario = ScenarioGenerator(config).generate()
    return scenario, LoggedDatasetGenerator(config, frozen_detector_v2_path()).generate(scenario)


def _small_config(seed: int) -> SimulatorConfig:
    return SimulatorConfig(
        seed=seed,
        num_payment_attempts=800,
        customer_count=200,
        subscription_count=200,
        incident_count=6,
    )


def _observation(payment_id: str) -> PaymentObservation:
    now = datetime(2027, 1, 1, tzinfo=UTC)
    return PaymentObservation(
        payment_id=payment_id,
        subscription_id="SIM_SUBSCRIPTION_TEST",
        customer_id="SIM_CUSTOMER_TEST",
        merchant_id="SIM_MERCHANT_TEST",
        observed_at=now,
        failure_occurred_at=now,
        amount_minor=49_900,
        payment_method=PaymentMethod.UPI,
        issuer="ISSUER_A",
        failure_reason=FailureReason.TEMPORARY_NETWORK_ERROR,
        failure_source=FailureSource.NETWORK,
        attempt_number=1,
        subscription_prior_attempts=1,
        subscription_prior_successes=1,
        customer_prior_attempts=1,
        customer_prior_success_rate=1.0,
        recent_scope_attempts=1,
        recent_scope_success_rate=1.0,
    )


def test_feature_allowlist_excludes_ground_truth_and_identity() -> None:
    assert set(MODEL_FEATURE_ALLOWLIST).isdisjoint(FORBIDDEN_MODEL_FIELDS)
    assert set(RecoveryFeatureSnapshot.model_fields) == {
        "feature_schema_version",
        *MODEL_FEATURE_ALLOWLIST,
    }
    snapshot = RecoveryFeatureSnapshot(**_minimal_feature_values())
    assert snapshot.feature_schema_version == "1.0"
    assert len(FEATURE_SCHEMA_HASH) == 64


def test_logged_data_contains_one_selected_outcome_per_decision(logged_result) -> None:  # type: ignore[no-untyped-def]
    scenario, result = logged_result
    assert len(result.examples) == len(scenario.public.failure_observations)
    assert len({example.decision_key for example in result.examples}) == len(result.examples)
    assert all(example.candidate_count == 9 for example in result.examples)
    assert all(
        example.features.action_type == example.selected_action.value for example in result.examples
    )


def test_unselected_counterfactuals_are_absent_from_logged_rows(logged_result) -> None:  # type: ignore[no-untyped-def]
    _, result = logged_result
    serialized = "\n".join(example.model_dump_json() for example in result.examples)
    assert "oracle_probability" not in serialized
    assert "counterfactual" not in serialized
    assert "true_failure_cause" not in serialized
    assert set(LoggedRecoveryExample.model_fields).isdisjoint(
        {"oracle_probabilities", "nonselected_outcomes", "hidden_cause"}
    )


def test_exploration_selection_does_not_accept_hidden_state() -> None:
    signature = inspect.signature(select_exploration_action)
    assert set(signature.parameters) == {"observation", "costs", "seed"}
    source = inspect.getsource(select_exploration_action)
    assert "ground_truth" not in source
    assert "probability" not in source


def test_exploration_propensities_are_valid_and_deterministic() -> None:
    observation = _observation("SIM_PAYMENT_PROPENSITY")
    costs = SimulatorConfig().resolved_costs
    first = select_exploration_action(observation, costs, 20_270_101)
    second = select_exploration_action(observation, costs, 20_270_101)
    assert first == second
    assert first.propensity in {1 / 6, 1 / 24}
    assert 0 < first.propensity <= 1
    assert first.candidate_count == 9


def test_same_seed_produces_identical_logged_data(logged_result) -> None:  # type: ignore[no-untyped-def]
    _, first = logged_result
    config = _small_config(20_270_101)
    scenario = ScenarioGenerator(config).generate()
    second = LoggedDatasetGenerator(config, frozen_detector_v2_path()).generate(scenario)
    assert examples_digest(first.examples) == examples_digest(second.examples)


def test_different_seeds_produce_different_logged_data(logged_result) -> None:  # type: ignore[no-untyped-def]
    _, first = logged_result
    config = _small_config(20_270_102)
    scenario = ScenarioGenerator(config).generate()
    second = LoggedDatasetGenerator(config, frozen_detector_v2_path()).generate(scenario)
    assert examples_digest(first.examples) != examples_digest(second.examples)


def test_health_builder_accepts_observable_context_not_scenario_truth() -> None:
    signature = inspect.signature(build_feature_snapshot)
    assert "health" in signature.parameters
    assert "scenario" not in signature.parameters
    assert "ground_truth" not in signature.parameters
    assert HEALTH_FEATURES


def test_feature_decision_times_and_target_horizon_are_bounded(logged_result) -> None:  # type: ignore[no-untyped-def]
    _, result = logged_result
    assert TARGET_HORIZON_HOURS == 48
    for example in result.examples:
        assert example.features.failure_to_decision_hours >= 0
        assert example.delay_hours <= 24
        assert example.features.time_since_previous_payment_attempt_hours is None or (
            example.features.time_since_previous_payment_attempt_hours >= 0
        )


def test_detector_v2_implementation_and_config_remain_frozen() -> None:
    repository = Path(__file__).resolve().parents[2]
    expected = {
        repository / "simulator" / "recoveriq_detector_v2" / "detector.py": (
            "cbff72c1178aebffc07478b990dcf7dda2fd639cfc512e52e66a9785712a800d"
        ),
        repository / "simulator" / "recoveriq_detector_v2" / "config.py": (
            "188abf0f604a34e80a4e2747d67d7e425d7c1d3339fd8b466ecbe8cdf7f73043"
        ),
        repository / "simulator" / "recoveriq_detector_v2" / "models.py": (
            "32efe30934fb4d4892c6184cb1a16d3d3cf136558ac10c61fe7518bce09fa2c8"
        ),
        frozen_detector_v2_path(): (
            "fb2945c3c9f14f934af17d59d190eb70472ac7dba7328ee698620a5d8e07dcef"
        ),
    }
    for path, digest in expected.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def _minimal_feature_values() -> dict[str, object]:
    values: dict[str, object] = {}
    for name, field in RecoveryFeatureSnapshot.model_fields.items():
        if name == "feature_schema_version":
            continue
        annotation = str(field.annotation)
        if name in {"payment_method", "issuer", "failure_reason", "failure_source", "action_type"}:
            values[name] = "TEST"
        elif "bool" in annotation:
            values[name] = False
        elif "None" in annotation:
            values[name] = None
        elif "int" in annotation:
            values[name] = 1
        else:
            values[name] = 0.0
    values["amount_minor"] = 100
    values["attempt_number"] = 1
    return values
