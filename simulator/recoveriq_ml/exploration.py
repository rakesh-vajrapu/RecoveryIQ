from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from recoveriq_ml.config import RETRY_LATER_DELAYS_HOURS
from recoveriq_simulator.config import SimulationCosts
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.observation import PaymentObservation, RecoveryAction
from recoveriq_simulator.policies.base import build_action
from recoveriq_simulator.randomness import keyed_uniform

EXPLORATION_ACTION_TYPES = (
    ActionType.RETRY_NOW,
    ActionType.RETRY_LATER,
    ActionType.SEND_NUDGE,
    ActionType.CREATE_PAYMENT_LINK,
    ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
    ActionType.OFFER_ALTERNATE_METHOD,
)


@dataclass(frozen=True, slots=True)
class ExplorationSelection:
    action: RecoveryAction
    propensity: float
    candidate_count: int


def feasible_actions(
    observation: PaymentObservation,
    costs: SimulationCosts,
) -> tuple[RecoveryAction, ...]:
    specifications = (
        (ActionType.RETRY_NOW, 0.0),
        *((ActionType.RETRY_LATER, delay) for delay in RETRY_LATER_DELAYS_HOURS),
        (ActionType.SEND_NUDGE, 0.0),
        (ActionType.CREATE_PAYMENT_LINK, 0.0),
        (ActionType.REQUEST_PAYMENT_METHOD_UPDATE, 0.0),
        (ActionType.OFFER_ALTERNATE_METHOD, 0.0),
    )
    return tuple(
        build_action(
            policy_name="ML_EXPLORE_V1",
            observation=observation,
            ordinal=index,
            action_type=action_type,
            execute_at=observation.observed_at + timedelta(hours=delay),
            costs=costs,
        )
        for index, (action_type, delay) in enumerate(specifications, start=1)
    )


def select_exploration_action(
    observation: PaymentObservation,
    costs: SimulationCosts,
    seed: int,
) -> ExplorationSelection:
    candidates = feasible_actions(observation, costs)
    type_draw = keyed_uniform(
        seed,
        "ml-exploration-action-type-v1",
        observation.payment_id,
        observation.observed_at.isoformat(),
    )
    type_index = min(int(type_draw * len(EXPLORATION_ACTION_TYPES)), 5)
    selected_type = EXPLORATION_ACTION_TYPES[type_index]
    matching = [action for action in candidates if action.action_type is selected_type]
    if selected_type is ActionType.RETRY_LATER:
        delay_draw = keyed_uniform(
            seed,
            "ml-exploration-retry-delay-v1",
            observation.payment_id,
            observation.observed_at.isoformat(),
        )
        delay_index = min(int(delay_draw * len(matching)), len(matching) - 1)
        selected = matching[delay_index]
        propensity = 1 / (len(EXPLORATION_ACTION_TYPES) * len(matching))
    else:
        selected = matching[0]
        propensity = 1 / len(EXPLORATION_ACTION_TYPES)
    return ExplorationSelection(
        action=selected,
        propensity=propensity,
        candidate_count=len(candidates),
    )


def decision_key(seed: int, observation: PaymentObservation) -> str:
    payload = (
        f"{seed}|{observation.payment_id}|{observation.observed_at.isoformat()}|ml-decision-v1"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
