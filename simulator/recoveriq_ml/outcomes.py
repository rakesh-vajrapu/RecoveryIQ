from __future__ import annotations

from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.environment import RecoveryProbabilityModel
from recoveriq_simulator.ground_truth import (
    DegradationIncidentGroundTruth,
    GeneratedScenario,
)
from recoveriq_simulator.observation import PaymentObservation, RecoveryAction
from recoveriq_simulator.randomness import keyed_uniform

RETRY_ACTIONS = frozenset({ActionType.RETRY_NOW, ActionType.RETRY_LATER})


def selected_action_outcome(
    *,
    scenario: GeneratedScenario,
    config: SimulatorConfig,
    observation: PaymentObservation,
    action: RecoveryAction,
) -> bool:
    probability = oracle_action_probability(
        scenario=scenario,
        config=config,
        observation=observation,
        action=action,
    )
    retry_count = int(action.action_type in RETRY_ACTIONS)
    draw = keyed_uniform(
        config.seed,
        "recovery-outcome-v1",
        observation.payment_id,
        action.action_type.value,
        action.execute_at.isoformat(),
        retry_count,
        "RECOVERY_ACTION_EXECUTED",
    )
    return draw < probability


def oracle_action_probability(
    *,
    scenario: GeneratedScenario,
    config: SimulatorConfig,
    observation: PaymentObservation,
    action: RecoveryAction,
) -> float:
    truth = scenario.ground_truth.payments[observation.payment_id]
    customer = scenario.ground_truth.customers[observation.customer_id]
    hours = max(
        0.0,
        (action.execute_at - observation.failure_occurred_at).total_seconds() / 3600,
    )
    return RecoveryProbabilityModel(config.nudge_effect_strength).probability(
        truth=truth,
        customer=customer,
        action=action,
        incident=_active_incident(scenario, config, observation, action),
        hours_since_failure=hours,
        retry_number=int(action.action_type in RETRY_ACTIONS),
        prior_contacts=0,
    )


def _active_incident(
    scenario: GeneratedScenario,
    config: SimulatorConfig,
    observation: PaymentObservation,
    action: RecoveryAction,
) -> DegradationIncidentGroundTruth | None:
    subscriptions = {
        subscription.subscription_id: subscription for subscription in scenario.public.subscriptions
    }
    subscription = subscriptions[observation.subscription_id]
    matching = [
        incident
        for incident in scenario.ground_truth.incidents
        if incident.issuer == subscription.issuer
        and incident.payment_method is observation.payment_method
        and incident.start_at <= action.execute_at < incident.end_at
        and keyed_uniform(
            config.seed,
            "incident-exposure",
            incident.incident_id,
            observation.payment_id,
        )
        < incident.traffic_exposure_fraction
    ]
    return max(matching, key=lambda incident: incident.severity, default=None)
