from __future__ import annotations

import inspect

from recoveriq_simulator.observation import (
    PAYMENT_OBSERVATION_FIELD_ALLOWLIST,
    PaymentObservation,
    assert_observation_schema_allowlisted,
)
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
    assert fields == PAYMENT_OBSERVATION_FIELD_ALLOWLIST
    assert_observation_schema_allowlisted()


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


def test_rolling_aggregates_use_only_preceding_delivered_events(shared_scenario) -> None:  # type: ignore[no-untyped-def]
    events = shared_scenario.public.observable_events
    event_index = {event.event_id: index for index, event in enumerate(events)}
    for observation in shared_scenario.public.failure_observations:
        current_index = event_index[f"{observation.payment_id}:INITIAL"]
        preceding = events[:current_index]
        customer_events = [
            event for event in preceding if event.customer_id == observation.customer_id
        ]
        subscription_events = [
            event for event in preceding if event.subscription_id == observation.subscription_id
        ]
        assert observation.customer_prior_attempts == len(customer_events)
        assert observation.subscription_prior_attempts == len(subscription_events)
        assert all(event.observed_at <= observation.observed_at for event in preceding)
