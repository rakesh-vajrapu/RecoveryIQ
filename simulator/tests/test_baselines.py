from __future__ import annotations

from recoveriq_simulator.config import SimulationCosts
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.policies import FixedRetryPolicy


def test_retry_cap_and_stop_are_enforced(shared_scenario) -> None:  # type: ignore[no-untyped-def]
    observation = shared_scenario.public.failure_observations[0]
    actions = FixedRetryPolicy(max_retries=2).plan(observation, SimulationCosts())
    assert sum(action.action_type is ActionType.RETRY_LATER for action in actions) == 2
    assert actions[-1].action_type is ActionType.STOP


def test_fixed_retry_baseline_runs_and_stops(shared_benchmark) -> None:  # type: ignore[no-untyped-def]
    evaluation = next(
        item for item in shared_benchmark.policies if item.policy_name == "fixed_retry"
    )
    assert evaluation.metrics.failed_payment_count > 0
    assert evaluation.metrics.retry_count <= 2 * evaluation.metrics.failed_payment_count
    assert all(outcome.stopped for outcome in evaluation.outcomes if not outcome.recovered)
    assert all(not outcome.stopped for outcome in evaluation.outcomes if outcome.recovered)


def test_reminder_baseline_runs_with_one_contact_per_failure(shared_benchmark) -> None:  # type: ignore[no-untyped-def]
    evaluation = next(
        item
        for item in shared_benchmark.policies
        if item.policy_name == "reminder_then_fixed_retry"
    )
    assert evaluation.metrics.recovered_payment_count > 0
    assert evaluation.metrics.customer_contact_count == evaluation.metrics.failed_payment_count


def test_both_baselines_evaluate_same_failed_payments(shared_benchmark) -> None:  # type: ignore[no-untyped-def]
    fixed, reminder = shared_benchmark.policies
    fixed_ids = {outcome.payment_id for outcome in fixed.outcomes}
    reminder_ids = {outcome.payment_id for outcome in reminder.outcomes}
    assert fixed_ids == reminder_ids


def test_net_recovery_value_arithmetic(shared_benchmark) -> None:  # type: ignore[no-untyped-def]
    for evaluation in shared_benchmark.policies:
        metrics = evaluation.metrics
        assert metrics.net_recovered_value_minor == (
            metrics.gross_recovered_amount_minor
            - metrics.intervention_cost_minor
            - metrics.friction_cost_minor
        )
