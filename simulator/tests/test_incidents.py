from __future__ import annotations

from statistics import fmean


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
