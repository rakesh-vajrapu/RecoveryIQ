"""Policy boundary and shared deterministic action construction."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from recoveriq_simulator.config import SimulationCosts
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.observation import PaymentObservation, RecoveryAction


class RecoveryPolicy(Protocol):
    """A policy can observe public history, never hidden ground truth."""

    name: str

    def plan(
        self, observation: PaymentObservation, costs: SimulationCosts
    ) -> tuple[RecoveryAction, ...]: ...


def build_action(
    *,
    policy_name: str,
    observation: PaymentObservation,
    ordinal: int,
    action_type: ActionType,
    execute_at: datetime,
    costs: SimulationCosts,
) -> RecoveryAction:
    intervention_costs = {
        ActionType.WAIT: 0,
        ActionType.RETRY_NOW: costs.retry_operational_minor,
        ActionType.RETRY_LATER: costs.retry_operational_minor,
        ActionType.SEND_NUDGE: costs.message_minor,
        ActionType.CREATE_PAYMENT_LINK: costs.payment_link_minor,
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE: costs.method_update_minor,
        ActionType.OFFER_ALTERNATE_METHOD: costs.alternate_method_minor,
        ActionType.ESCALATE_TO_HUMAN: costs.human_review_minor,
        ActionType.STOP: 0,
    }
    is_contact = action_type in {
        ActionType.SEND_NUDGE,
        ActionType.CREATE_PAYMENT_LINK,
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        ActionType.OFFER_ALTERNATE_METHOD,
        ActionType.ESCALATE_TO_HUMAN,
    }
    retry_friction = (
        costs.retry_friction_minor * ordinal
        if action_type in {ActionType.RETRY_NOW, ActionType.RETRY_LATER}
        else 0
    )
    contact_friction = (
        round(costs.base_contact_friction_minor * costs.friction_growth ** (ordinal - 1))
        if is_contact
        else 0
    )
    return RecoveryAction(
        action_id=f"act_{policy_name}_{observation.payment_id}_{ordinal:02d}",
        action_type=action_type,
        execute_at=execute_at,
        scheduled_delay_hours=max(
            0.0, (execute_at - observation.observed_at).total_seconds() / 3600.0
        ),
        attempt_number=ordinal,
        intervention_cost_minor=intervention_costs[action_type],
        friction_cost_minor=retry_friction + contact_friction,
    )
