"""Baseline B: send one reminder, then use the fixed retry schedule."""

from __future__ import annotations

from datetime import timedelta

from recoveriq_simulator.config import SimulationCosts
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.observation import PaymentObservation, RecoveryAction
from recoveriq_simulator.policies.base import build_action


class ReminderThenRetryPolicy:
    name = "reminder_then_fixed_retry"

    def __init__(
        self,
        *,
        reminder_delay_minutes: int = 5,
        retry_delay_hours: float = 6.0,
        max_retries: int = 2,
    ) -> None:
        self.reminder_delay_minutes = reminder_delay_minutes
        self.retry_delay_hours = retry_delay_hours
        self.max_retries = max_retries

    def plan(
        self, observation: PaymentObservation, costs: SimulationCosts
    ) -> tuple[RecoveryAction, ...]:
        actions = [
            build_action(
                policy_name=self.name,
                observation=observation,
                ordinal=1,
                action_type=ActionType.SEND_NUDGE,
                execute_at=observation.observed_at + timedelta(minutes=self.reminder_delay_minutes),
                costs=costs,
            )
        ]
        for retry_number in range(1, self.max_retries + 1):
            actions.append(
                build_action(
                    policy_name=self.name,
                    observation=observation,
                    ordinal=retry_number + 1,
                    action_type=ActionType.RETRY_LATER,
                    execute_at=observation.observed_at
                    + timedelta(hours=self.retry_delay_hours * retry_number),
                    costs=costs,
                )
            )
        actions.append(
            build_action(
                policy_name=self.name,
                observation=observation,
                ordinal=self.max_retries + 2,
                action_type=ActionType.STOP,
                execute_at=actions[-1].execute_at + timedelta(microseconds=1),
                costs=costs,
            )
        )
        return tuple(actions)
