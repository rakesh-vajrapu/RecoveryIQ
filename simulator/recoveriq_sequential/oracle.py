"""Evaluation-only hidden outcome adapter for sequential episodes."""

from __future__ import annotations

from datetime import datetime

from recoveriq_sequential.config import CONTACT_ACTIONS, RETRY_ACTIONS
from recoveriq_sequential.models import (
    SequentialActionOutcome,
    SequentialCandidate,
    SequentialEpisodeState,
    SequentialEpisodeTemplate,
)
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.environment import RecoveryProbabilityModel
from recoveriq_simulator.ground_truth import (
    DegradationIncidentGroundTruth,
    GeneratedScenario,
)
from recoveriq_simulator.randomness import keyed_uniform


class SequentialScenarioOracle:
    def __init__(self, scenario: GeneratedScenario, config: SimulatorConfig) -> None:
        self.scenario = scenario
        self.config = config
        self.probability_model = RecoveryProbabilityModel(config.nudge_effect_strength)

    def probability(
        self,
        template: SequentialEpisodeTemplate,
        state: SequentialEpisodeState,
        candidate: SequentialCandidate,
    ) -> float:
        observation = template.observation
        action = candidate.recovery_action
        truth = self.scenario.ground_truth.payments[observation.payment_id]
        customer = self.scenario.ground_truth.customers[observation.customer_id]
        return self.probability_model.probability(
            truth=truth,
            customer=customer,
            action=action,
            incident=self._active_incident(template, action.execute_at),
            hours_since_failure=max(
                0.0,
                (action.execute_at - observation.failure_occurred_at).total_seconds() / 3600,
            ),
            retry_number=state.retry_count + int(action.action_type in RETRY_ACTIONS),
            prior_contacts=state.contact_count,
        )

    def execute(
        self,
        template: SequentialEpisodeTemplate,
        state: SequentialEpisodeState,
        candidate: SequentialCandidate,
    ) -> SequentialActionOutcome:
        probability = self.probability(template, state, candidate)
        action = candidate.recovery_action
        draw = keyed_uniform(
            self.config.seed,
            "sequential-recovery-outcome-v2",
            template.observation.payment_id,
            action.action_type.value,
            action.execute_at.isoformat(),
            state.retry_count + int(action.action_type in RETRY_ACTIONS),
            state.contact_count + int(action.action_type in CONTACT_ACTIONS),
        )
        recovered = draw < probability
        return SequentialActionOutcome(
            episode_id=state.episode_id,
            decision_index=state.decision_index,
            candidate_label=candidate.label,
            action_id=action.action_id,
            executed_at=action.execute_at,
            recovered=recovered,
            oracle_probability=probability,
            recovered_amount_minor=template.observation.amount_minor if recovered else 0,
        )

    def hidden_failure_family(self, template: SequentialEpisodeTemplate) -> str:
        cause = self.scenario.ground_truth.payments[
            template.observation.payment_id
        ].true_failure_cause
        if cause is None:
            raise ValueError("failed payment has no hidden failure family")
        return cause.value

    def _active_incident(
        self,
        template: SequentialEpisodeTemplate,
        at: datetime,
    ) -> DegradationIncidentGroundTruth | None:
        matching = [
            incident
            for incident in self.scenario.ground_truth.incidents
            if incident.issuer == template.subscription.issuer
            and incident.payment_method is template.observation.payment_method
            and incident.start_at <= at < incident.end_at
            and keyed_uniform(
                self.config.seed,
                "incident-exposure",
                incident.incident_id,
                template.observation.payment_id,
            )
            < incident.traffic_exposure_fraction
        ]
        return max(matching, key=lambda item: item.severity, default=None)
