"""Baseline A: retry on a fixed schedule without customer contact."""

from __future__ import annotations

from datetime import timedelta

from recoveriq_simulator.config import SimulationCosts
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.observation import PaymentObservation, RecoveryAction
from recoveriq_simulator.policies.base import build_action


class FixedRetryPolicy:
    name = "fixed_retry"

    def __init__(self, *, retry_delay_hours: float = 6.0, max_retries: int = 2) -> None:
        self.retry_delay_hours = retry_delay_hours
        self.max_retries = max_retries

    def plan(
        self, observation: PaymentObservation, costs: SimulationCosts
    ) -> tuple[RecoveryAction, ...]:
        actions = [
            build_action(
                policy_name=self.name,
                observation=observation,
                ordinal=retry_number,
                action_type=ActionType.RETRY_LATER,
                execute_at=observation.observed_at
                + timedelta(hours=self.retry_delay_hours * retry_number),
                costs=costs,
            )
            for retry_number in range(1, self.max_retries + 1)
        ]
        stop_at = (
            actions[-1].execute_at + timedelta(microseconds=1)
            if actions
            else observation.observed_at
        )
        actions.append(
            build_action(
                policy_name=self.name,
                observation=observation,
                ordinal=self.max_retries + 1,
                action_type=ActionType.STOP,
                execute_at=stop_at,
                costs=costs,
            )
        )
        return tuple(actions)
