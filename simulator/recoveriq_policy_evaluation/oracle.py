from __future__ import annotations

from collections import defaultdict

from recoveriq_policy.models import CandidateAction
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.environment import RecoveryProbabilityModel
from recoveriq_simulator.ground_truth import (
    DegradationIncidentGroundTruth,
    GeneratedScenario,
)
from recoveriq_simulator.observation import PaymentObservation
from recoveriq_simulator.randomness import keyed_uniform


class ScenarioOracle:
    """Evaluation-only hidden truth; never imported by the core policy package."""

    def __init__(self, scenario: GeneratedScenario, config: SimulatorConfig) -> None:
        self.scenario = scenario
        self.config = config
        self.probability_model = RecoveryProbabilityModel(config.nudge_effect_strength)
        self.subscriptions = {item.subscription_id: item for item in scenario.public.subscriptions}
        self.incidents: defaultdict[tuple[object, str], list[DegradationIncidentGroundTruth]] = (
            defaultdict(list)
        )
        for incident in scenario.ground_truth.incidents:
            self.incidents[(incident.payment_method, incident.issuer)].append(incident)

    def probability(
        self,
        observation: PaymentObservation,
        candidate: CandidateAction,
    ) -> float:
        action = candidate.recovery_action
        truth = self.scenario.ground_truth.payments[observation.payment_id]
        customer = self.scenario.ground_truth.customers[observation.customer_id]
        hours = max(
            0.0,
            (action.execute_at - observation.failure_occurred_at).total_seconds() / 3600,
        )
        return self.probability_model.probability(
            truth=truth,
            customer=customer,
            action=action,
            incident=self._active_incident(observation, candidate),
            hours_since_failure=hours,
            retry_number=int(action.action_type.value.startswith("RETRY")),
            prior_contacts=0,
        )

    def realized_outcome(
        self,
        observation: PaymentObservation,
        candidate: CandidateAction,
        probability: float,
    ) -> bool:
        action = candidate.recovery_action
        retry_count = int(action.action_type.value.startswith("RETRY"))
        draw = keyed_uniform(
            self.config.seed,
            "recovery-outcome-v1",
            observation.payment_id,
            action.action_type.value,
            action.execute_at.isoformat(),
            retry_count,
            "RECOVERY_ACTION_EXECUTED",
        )
        return draw < probability

    def hidden_family(self, observation: PaymentObservation) -> str:
        cause = self.scenario.ground_truth.payments[observation.payment_id].true_failure_cause
        if cause is None:
            raise ValueError("failed observation has no hidden failure family")
        return cause.value

    def during_hidden_incident(self, observation: PaymentObservation) -> bool:
        return self.scenario.ground_truth.payments[observation.payment_id].incident_id is not None

    def _active_incident(
        self,
        observation: PaymentObservation,
        candidate: CandidateAction,
    ) -> DegradationIncidentGroundTruth | None:
        subscription = self.subscriptions[observation.subscription_id]
        action = candidate.recovery_action
        matching = [
            incident
            for incident in self.incidents[(observation.payment_method, subscription.issuer)]
            if incident.start_at <= action.execute_at < incident.end_at
            and keyed_uniform(
                self.config.seed,
                "incident-exposure",
                incident.incident_id,
                observation.payment_id,
            )
            < incident.traffic_exposure_fraction
        ]
        return max(matching, key=lambda incident: incident.severity, default=None)
