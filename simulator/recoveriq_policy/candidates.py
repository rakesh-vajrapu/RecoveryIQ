from __future__ import annotations

import hashlib
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from recoveriq_policy.config import CANDIDATE_SPECS, TARGET_HORIZON_HOURS
from recoveriq_policy.models import CandidateAction, PolicyDecisionContext
from recoveriq_simulator.config import SimulationCosts
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.observation import RecoveryAction

CONTACT_ACTIONS = frozenset(
    {
        ActionType.SEND_NUDGE,
        ActionType.CREATE_PAYMENT_LINK,
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        ActionType.OFFER_ALTERNATE_METHOD,
    }
)
METHOD_CHANGE_ACTIONS = frozenset(
    {
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        ActionType.OFFER_ALTERNATE_METHOD,
    }
)
RETRY_ACTIONS = frozenset({ActionType.RETRY_NOW, ActionType.RETRY_LATER})


def generate_candidate_actions(
    context: PolicyDecisionContext,
    costs: SimulationCosts,
) -> tuple[CandidateAction, ...]:
    actions: list[CandidateAction] = []
    for spec in CANDIDATE_SPECS:
        if spec.delay_hours > TARGET_HORIZON_HOURS:
            continue
        contact = spec.action_type in CONTACT_ACTIONS
        retry = spec.action_type in RETRY_ACTIONS
        friction = (
            _contact_friction(costs, context.base_features.current_contact_count + 1)
            if contact
            else costs.retry_friction_minor * (context.base_features.current_retry_count + 1)
            if retry
            else 0
        )
        action = RecoveryAction(
            action_id=_action_id(context.decision_key, spec.label),
            action_type=spec.action_type,
            execute_at=context.decision_at + _hours(spec.delay_hours),
            scheduled_delay_hours=spec.delay_hours,
            attempt_number=(context.base_features.current_retry_count + 1 if retry else 0),
            intervention_cost_minor=_intervention_cost(spec.action_type, costs),
            friction_cost_minor=friction,
        )
        actions.append(
            CandidateAction(
                label=spec.label,
                recovery_action=action,
                is_customer_contact=contact,
                requests_method_change=spec.action_type in METHOD_CHANGE_ACTIONS,
            )
        )
    return tuple(actions)


def _action_id(decision_key: str, label: str) -> str:
    payload = f"policy-v1|{decision_key}|{label}"
    return f"pact_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def _hours(value: float) -> timedelta:
    return timedelta(hours=value)


def _contact_friction(costs: SimulationCosts, contact_number: int) -> int:
    growth = Decimal(str(costs.friction_growth)) ** max(0, contact_number - 1)
    amount = (Decimal(costs.base_contact_friction_minor) * growth).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return min(costs.max_contact_friction_minor, int(amount))


def _intervention_cost(action_type: ActionType, costs: SimulationCosts) -> int:
    return {
        ActionType.RETRY_NOW: costs.retry_operational_minor,
        ActionType.RETRY_LATER: costs.retry_operational_minor,
        ActionType.SEND_NUDGE: costs.message_minor,
        ActionType.CREATE_PAYMENT_LINK: costs.payment_link_minor,
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE: costs.method_update_minor,
        ActionType.OFFER_ALTERNATE_METHOD: costs.alternate_method_minor,
    }[action_type]
