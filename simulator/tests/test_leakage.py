from __future__ import annotations

import inspect

from recoveriq_simulator.observation import PaymentObservation
from recoveriq_simulator.policies.base import RecoveryPolicy

FORBIDDEN_FIELDS = {
    "true_failure_cause",
    "latent_customer_state",
    "hidden_recovery_probability",
    "active_hidden_incident_flag",
    "future_outcome",
    "incident_id",
    "instrument_state",
}


def test_observation_schema_excludes_hidden_state() -> None:
    fields = set(PaymentObservation.model_fields)
    assert fields.isdisjoint(FORBIDDEN_FIELDS)


def test_policy_protocol_accepts_observation_only() -> None:
    signature = inspect.signature(RecoveryPolicy.plan)
    assert signature.parameters["observation"].annotation in {
        "PaymentObservation",
        PaymentObservation,
    }
    assert "ground_truth" not in signature.parameters


def test_observations_contain_no_future_events(shared_scenario) -> None:  # type: ignore[no-untyped-def]
    for observation in shared_scenario.public.failure_observations:
        assert observation.failure_occurred_at <= observation.observed_at
        assert all(
            event.observed_at <= observation.observed_at
            and event.occurred_at <= observation.observed_at
            for event in observation.prior_events
        )
        serialized = observation.model_dump_json()
        assert "end_at" not in serialized
        assert "RECOVERY_SUCCEEDED" not in serialized
