from __future__ import annotations

import heapq
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from recoveriq_detector_v2.artifacts import load_frozen_v2_config
from recoveriq_detector_v2.detector import OperationalDegradationDetectorV2
from recoveriq_detector_v2.replay import observable_v2_event
from recoveriq_ml.config import TARGET_HORIZON_HOURS
from recoveriq_ml.exploration import (
    decision_key,
    feasible_actions,
    select_exploration_action,
)
from recoveriq_ml.features import (
    ObservableRecoveryHistory,
    build_feature_snapshot,
    snapshot_for_action,
)
from recoveriq_ml.models import LoggedRecoveryExample, RecoveryFeatureSnapshot
from recoveriq_ml.outcomes import oracle_action_probability, selected_action_outcome
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.observation import PaymentObservation, RecoveryAction


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    action: RecoveryAction
    features: RecoveryFeatureSnapshot
    oracle_probability: float


@dataclass(frozen=True, slots=True)
class HeldoutDecision:
    decision_key: str
    candidates: tuple[CandidateEvaluation, ...]
    hidden_cause: str
    during_hidden_incident: bool
    near_incident_boundary: bool
    high_observable_health_evidence: bool


@dataclass(frozen=True, slots=True)
class LoggedGenerationResult:
    examples: tuple[LoggedRecoveryExample, ...]
    heldout_decisions: tuple[HeldoutDecision, ...]


class LoggedDatasetGenerator:
    def __init__(self, config: SimulatorConfig, frozen_detector_path: Any) -> None:
        self.config = config
        self.detector_config = load_frozen_v2_config(frozen_detector_path)

    def generate(
        self,
        scenario: GeneratedScenario,
        *,
        include_evaluation_truth: bool = False,
    ) -> LoggedGenerationResult:
        detector = OperationalDegradationDetectorV2(self.detector_config)
        observations = {
            observation.payment_id: observation
            for observation in scenario.public.failure_observations
        }
        subscriptions = {
            subscription.subscription_id: subscription
            for subscription in scenario.public.subscriptions
        }
        histories: defaultdict[str, ObservableRecoveryHistory] = defaultdict(
            ObservableRecoveryHistory
        )
        pending: list[tuple[datetime, int, str, ActionType, bool]] = []
        last_success: dict[str, datetime] = {}
        examples: list[LoggedRecoveryExample] = []
        evaluations: list[HeldoutDecision] = []
        events = sorted(
            scenario.public.observable_events,
            key=lambda event: (event.observed_at, event.event_id),
        )
        pending_ordinal = 0
        for event in events:
            self._settle_history(pending, histories, event.observed_at)
            detector.update(observable_v2_event(event))
            if not event.success:
                observation = observations[event.payment_id]
                selection = select_exploration_action(
                    observation,
                    self.config.resolved_costs,
                    self.config.seed,
                )
                health = detector.get_health_context(
                    observation.observed_at,
                    observation.payment_method.value,
                    observation.issuer,
                )
                if health.confirmed_hard_policy_gate_passed:
                    raise RuntimeError("frozen detector v2 must remain advisory-only")
                features = build_feature_snapshot(
                    observation=observation,
                    subscription=subscriptions[observation.subscription_id],
                    action=selection.action,
                    health=health,
                    recovery_history=histories[observation.customer_id],
                    last_success_at=last_success.get(observation.customer_id),
                )
                recovered = selected_action_outcome(
                    scenario=scenario,
                    config=self.config,
                    observation=observation,
                    action=selection.action,
                )
                within_horizon = bool(
                    recovered
                    and selection.action.execute_at
                    <= observation.observed_at + timedelta(hours=TARGET_HORIZON_HOURS)
                )
                key = decision_key(self.config.seed, observation)
                examples.append(
                    LoggedRecoveryExample(
                        decision_key=key,
                        decision_at=observation.observed_at,
                        selected_action=selection.action.action_type,
                        delay_hours=selection.action.scheduled_delay_hours,
                        selection_propensity=selection.propensity,
                        candidate_count=selection.candidate_count,
                        recovered_within_48h=within_horizon,
                        features=features,
                    )
                )
                pending_ordinal += 1
                heapq.heappush(
                    pending,
                    (
                        selection.action.execute_at,
                        pending_ordinal,
                        observation.customer_id,
                        selection.action.action_type,
                        within_horizon,
                    ),
                )
                if include_evaluation_truth:
                    evaluations.append(
                        self._evaluation_decision(
                            scenario,
                            observation,
                            features,
                            key,
                        )
                    )
            elif event.success:
                last_success[event.customer_id] = event.observed_at
        return LoggedGenerationResult(
            examples=tuple(examples),
            heldout_decisions=tuple(evaluations),
        )

    def _evaluation_decision(
        self,
        scenario: GeneratedScenario,
        observation: PaymentObservation,
        selected_features: RecoveryFeatureSnapshot,
        key: str,
    ) -> HeldoutDecision:
        candidates = tuple(
            CandidateEvaluation(
                action=action,
                features=snapshot_for_action(selected_features, action),
                oracle_probability=oracle_action_probability(
                    scenario=scenario,
                    config=self.config,
                    observation=observation,
                    action=action,
                ),
            )
            for action in feasible_actions(observation, self.config.resolved_costs)
        )
        truth = scenario.ground_truth.payments[observation.payment_id]
        subscription = next(
            item
            for item in scenario.public.subscriptions
            if item.subscription_id == observation.subscription_id
        )
        near_boundary = any(
            incident.payment_method is observation.payment_method
            and incident.issuer == subscription.issuer
            and min(
                abs((observation.observed_at - incident.start_at).total_seconds()),
                abs((observation.observed_at - incident.end_at).total_seconds()),
            )
            <= 6 * 3600
            for incident in scenario.ground_truth.incidents
        )
        high_health = bool(
            selected_features.health_issuer_watch
            or selected_features.health_method_watch
            or selected_features.health_global_watch
            or max(
                selected_features.health_issuer_maximum_llr,
                selected_features.health_method_maximum_llr,
                selected_features.health_global_maximum_llr,
            )
            >= self.detector_config.watch_llr_threshold
        )
        if truth.true_failure_cause is None:
            raise ValueError("failed observation is missing hidden cause in evaluation layer")
        return HeldoutDecision(
            decision_key=key,
            candidates=candidates,
            hidden_cause=truth.true_failure_cause.value,
            during_hidden_incident=truth.incident_id is not None,
            near_incident_boundary=near_boundary,
            high_observable_health_evidence=high_health,
        )

    @staticmethod
    def _settle_history(
        pending: list[tuple[datetime, int, str, ActionType, bool]],
        histories: defaultdict[str, ObservableRecoveryHistory],
        timestamp: datetime,
    ) -> None:
        while pending and pending[0][0] <= timestamp:
            _, _, customer_id, action_type, recovered = heapq.heappop(pending)
            history = histories[customer_id]
            history.recovery_attempts += 1
            history.successful_recoveries += int(recovered)
            history.nudges += int(action_type is ActionType.SEND_NUDGE)
            history.retries += int(action_type in {ActionType.RETRY_NOW, ActionType.RETRY_LATER})
            history.payment_links += int(action_type is ActionType.CREATE_PAYMENT_LINK)


def audit_examples(examples: tuple[LoggedRecoveryExample, ...]) -> dict[str, Any]:
    actions = Counter(example.selected_action.value for example in examples)
    positives = sum(example.recovered_within_48h for example in examples)
    return {
        "example_count": len(examples),
        "action_counts": dict(sorted(actions.items())),
        "positive_count": positives,
        "positive_rate": positives / len(examples) if examples else None,
        "propensity_distribution": dict(
            sorted(Counter(example.selection_propensity for example in examples).items())
        ),
        "candidate_count_distribution": dict(
            sorted(Counter(example.candidate_count for example in examples).items())
        ),
    }
