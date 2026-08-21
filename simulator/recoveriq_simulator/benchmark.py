"""Paired benchmark orchestration for Phase 2 policies."""

from __future__ import annotations

from recoveriq_simulator import SIMULATOR_VERSION
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.environment import RecoveryEnvironment
from recoveriq_simulator.policies import FixedRetryPolicy, ReminderThenRetryPolicy
from recoveriq_simulator.results import BenchmarkResult
from recoveriq_simulator.scenario import GeneratedScenario, ScenarioGenerator


def run_benchmark(
    config: SimulatorConfig, scenario: GeneratedScenario | None = None
) -> tuple[GeneratedScenario, BenchmarkResult]:
    """Evaluate both baselines against one shared hidden environment."""

    generated = scenario if scenario is not None else ScenarioGenerator(config).generate()
    environment = RecoveryEnvironment(generated, config)
    policies = (
        FixedRetryPolicy(
            retry_delay_hours=config.fixed_retry_delay_hours,
            max_retries=config.max_retries,
        ),
        ReminderThenRetryPolicy(
            reminder_delay_minutes=config.reminder_delay_minutes,
            retry_delay_hours=config.fixed_retry_delay_hours,
            max_retries=config.max_retries,
        ),
    )
    return generated, BenchmarkResult(
        experiment_id=config.experiment_id,
        simulator_version=SIMULATOR_VERSION,
        seed=config.seed,
        policies=tuple(environment.evaluate(policy) for policy in policies),
    )
