from __future__ import annotations

from statistics import fmean

from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import IncidentSeverity
from recoveriq_simulator.scenario import ScenarioGenerator


def test_incident_windows_are_valid(shared_scenario) -> None:  # type: ignore[no-untyped-def]
    assert shared_scenario.ground_truth.incidents
    assert all(
        incident.start_at < incident.end_at and incident.degraded_health < incident.baseline_health
        for incident in shared_scenario.ground_truth.incidents
    )


def test_incidents_reduce_initial_success_distribution(shared_scenario) -> None:  # type: ignore[no-untyped-def]
    during = [
        payment.initial_success_probability
        for payment in shared_scenario.ground_truth.payments.values()
        if payment.incident_id is not None
    ]
    outside = [
        payment.initial_success_probability
        for payment in shared_scenario.ground_truth.payments.values()
        if payment.incident_id is None
    ]
    assert during
    assert outside
    assert fmean(during) < fmean(outside)


def test_incident_severity_and_duration_are_heterogeneous() -> None:
    config = SimulatorConfig(
        seed=909_090,
        num_payment_attempts=300,
        merchant_count=3,
        customer_count=80,
        subscription_count=120,
        horizon_days=90,
        incident_count=100,
    )
    incidents = ScenarioGenerator(config).generate().ground_truth.incidents
    durations = [
        (incident.end_at - incident.start_at).total_seconds() / 3600.0 for incident in incidents
    ]
    assert {incident.severity_class for incident in incidents} == set(IncidentSeverity)
    assert min(durations) < 4.5
    assert max(durations) > 19
