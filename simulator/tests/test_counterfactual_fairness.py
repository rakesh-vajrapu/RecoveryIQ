from __future__ import annotations

from datetime import timedelta

from recoveriq_simulator.config import SimulationCosts, SimulatorConfig
from recoveriq_simulator.enums import ActionType, CostRegime
from recoveriq_simulator.environment import RecoveryEnvironment
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.observation import PaymentObservation, RecoveryAction
from recoveriq_simulator.policies import FixedRetryPolicy, ReminderThenRetryPolicy
from recoveriq_simulator.policies.base import build_action
from recoveriq_simulator.results import PolicyEvaluation
from recoveriq_simulator.scenario import scenario_digest


class FixedRetryWithUnusedCandidate(FixedRetryPolicy):
    name = "fixed_retry_with_unused_candidate"

    def plan(
        self,
        observation: PaymentObservation,
        costs: SimulationCosts,
    ) -> tuple[RecoveryAction, ...]:
        actions = list(super().plan(observation, costs))
        actions.append(
            build_action(
                policy_name=self.name,
                observation=observation,
                ordinal=99,
                action_type=ActionType.WAIT,
                execute_at=actions[-1].execute_at + timedelta(hours=72),
                costs=costs,
            )
        )
        return tuple(actions)


def _outcome_semantics(evaluation: PolicyEvaluation) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            outcome.payment_id,
            outcome.recovered,
            outcome.recovery_action,
            outcome.recovered_at,
            outcome.retry_count,
        )
        for outcome in evaluation.outcomes
    )


def test_unused_candidate_does_not_change_outcomes(
    shared_scenario: GeneratedScenario,
    shared_config: SimulatorConfig,
) -> None:
    environment = RecoveryEnvironment(shared_scenario, shared_config)
    normal = environment.evaluate(FixedRetryPolicy())
    with_unused = environment.evaluate(FixedRetryWithUnusedCandidate())
    assert _outcome_semantics(normal) == _outcome_semantics(with_unused)


def test_semantically_identical_retry_uses_same_keyed_draw(
    shared_scenario: GeneratedScenario,
    shared_config: SimulatorConfig,
) -> None:
    observation = shared_scenario.public.failure_observations[0]
    fixed_retry = FixedRetryPolicy().plan(observation, shared_config.resolved_costs)[0]
    reminder_retry = ReminderThenRetryPolicy().plan(observation, shared_config.resolved_costs)[1]
    environment = RecoveryEnvironment(shared_scenario, shared_config)
    assert fixed_retry.action_type is reminder_retry.action_type
    assert fixed_retry.execute_at == reminder_retry.execute_at
    assert environment.outcome_uniform(
        observation.payment_id, fixed_retry, 1
    ) == environment.outcome_uniform(observation.payment_id, reminder_retry, 1)


def test_both_policies_share_one_unchanged_hidden_world(
    shared_scenario: GeneratedScenario,
    shared_config: SimulatorConfig,
) -> None:
    before = scenario_digest(shared_scenario)
    environment = RecoveryEnvironment(shared_scenario, shared_config)
    fixed = environment.evaluate(FixedRetryPolicy())
    reminder = environment.evaluate(ReminderThenRetryPolicy())
    assert scenario_digest(shared_scenario) == before
    assert {outcome.payment_id for outcome in fixed.outcomes} == {
        outcome.payment_id for outcome in reminder.outcomes
    }
    assert shared_scenario.ground_truth.seed == shared_config.seed


def test_cost_regime_changes_net_not_raw_outcomes(
    shared_scenario: GeneratedScenario,
    shared_config: SimulatorConfig,
) -> None:
    low = shared_config.model_copy(update={"cost_regime": CostRegime.LOW_FRICTION})
    high = shared_config.model_copy(update={"cost_regime": CostRegime.HIGH_FRICTION})
    for policy in (FixedRetryPolicy(), ReminderThenRetryPolicy()):
        low_result = RecoveryEnvironment(shared_scenario, low).evaluate(policy)
        high_result = RecoveryEnvironment(shared_scenario, high).evaluate(policy)
        assert _outcome_semantics(low_result) == _outcome_semantics(high_result)
        assert (
            low_result.metrics.gross_recovered_amount_minor
            == high_result.metrics.gross_recovered_amount_minor
        )
        assert (
            low_result.metrics.net_recovered_value_minor
            > high_result.metrics.net_recovered_value_minor
        )


def test_repeated_contact_friction_increases_and_is_bounded(
    shared_scenario: GeneratedScenario,
) -> None:
    observation = shared_scenario.public.failure_observations[0]
    costs = SimulatorConfig(cost_regime=CostRegime.HIGH_FRICTION).resolved_costs
    friction = [
        build_action(
            policy_name="friction_test",
            observation=observation,
            ordinal=ordinal,
            action_type=ActionType.SEND_NUDGE,
            execute_at=observation.observed_at + timedelta(hours=ordinal),
            costs=costs,
        ).friction_cost_minor
        for ordinal in (1, 2, 3, 20)
    ]
    assert friction[0] < friction[1] < friction[2] <= friction[3]
    assert friction[-1] == costs.max_contact_friction_minor
