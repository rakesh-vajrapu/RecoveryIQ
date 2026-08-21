"""Hidden recovery environment used to evaluate observable-only policies."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from statistics import fmean

from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import (
    ActionType,
    EventType,
    InstrumentState,
    TrueFailureCause,
)
from recoveriq_simulator.events import EventQueue
from recoveriq_simulator.ground_truth import (
    CustomerGroundTruth,
    DegradationIncidentGroundTruth,
    PaymentGroundTruth,
)
from recoveriq_simulator.observation import PaymentObservation, RecoveryAction
from recoveriq_simulator.policies.base import RecoveryPolicy
from recoveriq_simulator.results import (
    BaselineMetrics,
    PaymentPolicyOutcome,
    PolicyEvaluation,
    RecoveryAttribution,
)
from recoveriq_simulator.scenario import GeneratedScenario

RETRY_ACTIONS = frozenset({ActionType.RETRY_NOW, ActionType.RETRY_LATER})
CONTACT_ACTIONS = frozenset(
    {
        ActionType.SEND_NUDGE,
        ActionType.CREATE_PAYMENT_LINK,
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        ActionType.OFFER_ALTERNATE_METHOD,
        ActionType.ESCALATE_TO_HUMAN,
    }
)


class AttributionLedger:
    """Guarantee that a payment can be recovered and credited only once."""

    def __init__(self) -> None:
        self._entries: dict[str, RecoveryAttribution] = {}

    def attribute(self, attribution: RecoveryAttribution) -> None:
        if attribution.payment_id in self._entries:
            raise ValueError(f"payment already attributed: {attribution.payment_id}")
        self._entries[attribution.payment_id] = attribution

    def values(self) -> tuple[RecoveryAttribution, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))


class RecoveryProbabilityModel:
    """Deterministic hidden-state response surface for recovery actions."""

    def probability(
        self,
        *,
        truth: PaymentGroundTruth,
        customer: CustomerGroundTruth,
        action: RecoveryAction,
        incident: DegradationIncidentGroundTruth | None,
        hours_since_failure: float,
        retry_number: int,
        prior_contacts: int,
    ) -> float:
        cause = truth.true_failure_cause
        if cause is None:
            raise ValueError("recovery probability requires a failed payment")
        responsiveness = customer.nudge_responsiveness
        update = customer.instrument_update_propensity

        if action.action_type in {ActionType.WAIT, ActionType.STOP}:
            return 0.0

        if action.action_type in RETRY_ACTIONS:
            probability = self._retry_probability(cause, hours_since_failure, incident)
            probability += 0.10 * (customer.retry_sensitivity - 0.5)
            probability -= 0.045 * max(0, retry_number - 1)
            if prior_contacts:
                probability += 0.06 * responsiveness
            if truth.instrument_state in {InstrumentState.EXPIRED, InstrumentState.INACTIVE}:
                probability *= 0.14
        elif action.action_type is ActionType.SEND_NUDGE:
            probability = {
                TrueFailureCause.LIQUIDITY_SHORTFALL: 0.08 + 0.30 * responsiveness,
                TrueFailureCause.ISSUER_DEGRADATION: 0.03,
                TrueFailureCause.AUTHENTICATION_FRICTION: 0.14 + 0.24 * responsiveness,
                TrueFailureCause.INVALID_INSTRUMENT: 0.07 + 0.13 * responsiveness,
                TrueFailureCause.INACTIVE_MANDATE: 0.12 + 0.24 * responsiveness,
                TrueFailureCause.NETWORK_INSTABILITY: 0.04,
                TrueFailureCause.CUSTOMER_CONFIRMATION: 0.20 + 0.52 * responsiveness,
                TrueFailureCause.UNKNOWN_TEMPORARY: 0.10 + 0.18 * responsiveness,
            }[cause]
        elif action.action_type is ActionType.CREATE_PAYMENT_LINK:
            probability = 0.23 + 0.32 * responsiveness + 0.12 * update
        elif action.action_type is ActionType.REQUEST_PAYMENT_METHOD_UPDATE:
            probability = 0.12 + 0.58 * update
            if cause in {
                TrueFailureCause.INVALID_INSTRUMENT,
                TrueFailureCause.INACTIVE_MANDATE,
            }:
                probability += 0.18
        elif action.action_type is ActionType.OFFER_ALTERNATE_METHOD:
            probability = 0.30 + 0.32 * update
            if cause in {
                TrueFailureCause.ISSUER_DEGRADATION,
                TrueFailureCause.INVALID_INSTRUMENT,
                TrueFailureCause.INACTIVE_MANDATE,
                TrueFailureCause.NETWORK_INSTABILITY,
            }:
                probability += 0.12
        else:
            probability = 0.26 + 0.30 * responsiveness + 0.16 * update

        probability -= 0.025 * max(0, prior_contacts - 1)
        return max(0.005, min(0.95, probability))

    @staticmethod
    def _retry_probability(
        cause: TrueFailureCause,
        hours_since_failure: float,
        incident: DegradationIncidentGroundTruth | None,
    ) -> float:
        if cause is TrueFailureCause.LIQUIDITY_SHORTFALL:
            return min(0.66, 0.07 + 0.021 * hours_since_failure)
        if cause is TrueFailureCause.ISSUER_DEGRADATION:
            return 0.04 + 0.08 * (1.0 - incident.severity) if incident else 0.67
        if cause is TrueFailureCause.AUTHENTICATION_FRICTION:
            return 0.14 + min(0.18, hours_since_failure / 48.0)
        if cause is TrueFailureCause.INVALID_INSTRUMENT:
            return 0.012
        if cause is TrueFailureCause.INACTIVE_MANDATE:
            return 0.018
        if cause is TrueFailureCause.NETWORK_INSTABILITY:
            return 0.09 if incident else min(0.72, 0.36 + hours_since_failure / 36.0)
        if cause is TrueFailureCause.CUSTOMER_CONFIRMATION:
            return 0.08
        return min(0.46, 0.18 + hours_since_failure / 60.0)


class RecoveryEnvironment:
    def __init__(self, scenario: GeneratedScenario, config: SimulatorConfig) -> None:
        self.scenario = scenario
        self.config = config
        self.probability_model = RecoveryProbabilityModel()
        self._subscriptions = {
            subscription.subscription_id: subscription
            for subscription in scenario.public.subscriptions
        }

    def evaluate(self, policy: RecoveryPolicy) -> PolicyEvaluation:
        ledger = AttributionLedger()
        outcomes = tuple(
            self._evaluate_payment(policy, observation, ledger)
            for observation in self.scenario.public.failure_observations
        )
        return PolicyEvaluation(
            policy_name=policy.name,
            outcomes=outcomes,
            attributions=ledger.values(),
            metrics=self._metrics(policy.name, outcomes),
        )

    def _evaluate_payment(
        self,
        policy: RecoveryPolicy,
        observation: PaymentObservation,
        ledger: AttributionLedger,
    ) -> PaymentPolicyOutcome:
        queue = EventQueue()
        for action in policy.plan(observation, self.config.costs):
            queue.push(action.execute_at, EventType.RECOVERY_ACTION_EXECUTED, action)

        truth = self.scenario.ground_truth.payments[observation.payment_id]
        customer = self.scenario.ground_truth.customers[observation.customer_id]
        retry_count = 0
        nudge_count = 0
        contact_count = 0
        link_count = 0
        human_count = 0
        action_count = 0
        intervention_cost = 0
        friction_cost = 0
        stopped = False
        recovery_action: ActionType | None = None
        recovered_at: datetime | None = None
        executed: Counter[str] = Counter()

        while queue:
            action = queue.pop().payload
            if not isinstance(action, RecoveryAction):
                raise TypeError("action queue payload must be RecoveryAction")
            action_count += 1
            executed[action.action_type.value] += 1
            intervention_cost += action.intervention_cost_minor
            friction_cost += action.friction_cost_minor
            if action.action_type in RETRY_ACTIONS:
                retry_count += 1
            if action.action_type is ActionType.SEND_NUDGE:
                nudge_count += 1
            if action.action_type in CONTACT_ACTIONS:
                contact_count += 1
            if action.action_type is ActionType.CREATE_PAYMENT_LINK:
                link_count += 1
            if action.action_type is ActionType.ESCALATE_TO_HUMAN:
                human_count += 1
            if action.action_type is ActionType.STOP:
                stopped = True
                break

            prior_contacts = contact_count - int(action.action_type in CONTACT_ACTIONS)
            hours = max(
                0.0,
                (action.execute_at - observation.failure_occurred_at).total_seconds() / 3600.0,
            )
            probability = self.probability_model.probability(
                truth=truth,
                customer=customer,
                action=action,
                incident=self._active_incident(observation, action.execute_at),
                hours_since_failure=hours,
                retry_number=retry_count,
                prior_contacts=prior_contacts,
            )
            if self._paired_uniform(observation.payment_id, action, retry_count) < probability:
                attribution = RecoveryAttribution(
                    payment_id=observation.payment_id,
                    action_id=action.action_id,
                    action_type=action.action_type,
                    recovered_at=action.execute_at,
                    recovered_amount_minor=observation.amount_minor,
                )
                ledger.attribute(attribution)
                recovery_action = action.action_type
                recovered_at = action.execute_at
                break

        recovered = recovered_at is not None
        return PaymentPolicyOutcome(
            policy_name=policy.name,
            payment_id=observation.payment_id,
            failed_amount_minor=observation.amount_minor,
            recovered=recovered,
            recovery_action=recovery_action,
            recovered_at=recovered_at,
            time_to_recovery_hours=(
                (recovered_at - observation.failure_occurred_at).total_seconds() / 3600.0
                if recovered_at
                else None
            ),
            retry_count=retry_count,
            nudge_count=nudge_count,
            customer_contacts=contact_count,
            payment_link_count=link_count,
            human_review_count=human_count,
            action_count=action_count,
            intervention_cost_minor=intervention_cost,
            friction_cost_minor=friction_cost,
            stopped=stopped,
            executed_action_counts=dict(sorted(executed.items())),
        )

    def _active_incident(
        self, observation: PaymentObservation, at: datetime
    ) -> DegradationIncidentGroundTruth | None:
        subscription = self._subscriptions[observation.subscription_id]
        matching = [
            incident
            for incident in self.scenario.ground_truth.incidents
            if incident.issuer == subscription.issuer
            and incident.payment_method is observation.payment_method
            and incident.start_at <= at < incident.end_at
        ]
        return max(matching, key=lambda incident: incident.severity, default=None)

    def _paired_uniform(self, payment_id: str, action: RecoveryAction, retry_count: int) -> float:
        # Policy name/action ID are intentionally absent. Identical retry actions
        # share the same counterfactual draw across paired baseline evaluations.
        key = "|".join(
            (
                str(self.config.seed),
                payment_id,
                action.action_type.value,
                action.execute_at.isoformat(),
                str(retry_count),
            )
        )
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / 2**64

    @staticmethod
    def _metrics(policy_name: str, outcomes: tuple[PaymentPolicyOutcome, ...]) -> BaselineMetrics:
        recovered = [outcome for outcome in outcomes if outcome.recovered]
        failed_amount = sum(outcome.failed_amount_minor for outcome in outcomes)
        gross = sum(outcome.failed_amount_minor for outcome in recovered)
        intervention = sum(outcome.intervention_cost_minor for outcome in outcomes)
        friction = sum(outcome.friction_cost_minor for outcome in outcomes)
        total_actions = sum(outcome.action_count for outcome in outcomes)
        action_counts: Counter[str] = Counter()
        success_counts: Counter[str] = Counter()
        for outcome in outcomes:
            action_counts.update(outcome.executed_action_counts)
            if outcome.recovery_action:
                success_counts[outcome.recovery_action.value] += 1
        times = [
            outcome.time_to_recovery_hours
            for outcome in recovered
            if outcome.time_to_recovery_hours is not None
        ]
        return BaselineMetrics(
            policy_name=policy_name,
            failed_payment_count=len(outcomes),
            recovered_payment_count=len(recovered),
            failed_amount_minor=failed_amount,
            gross_recovered_amount_minor=gross,
            net_recovered_value_minor=gross - intervention - friction,
            recovery_rate=len(recovered) / len(outcomes) if outcomes else 0.0,
            value_recovery_rate=gross / failed_amount if failed_amount else 0.0,
            retry_count=sum(outcome.retry_count for outcome in outcomes),
            nudge_count=sum(outcome.nudge_count for outcome in outcomes),
            customer_contact_count=sum(outcome.customer_contacts for outcome in outcomes),
            payment_link_count=sum(outcome.payment_link_count for outcome in outcomes),
            human_review_count=sum(outcome.human_review_count for outcome in outcomes),
            intervention_cost_minor=intervention,
            friction_cost_minor=friction,
            average_actions_per_failed_payment=total_actions / len(outcomes) if outcomes else 0.0,
            average_actions_per_recovered_payment=(
                sum(outcome.action_count for outcome in recovered) / len(recovered)
                if recovered
                else 0.0
            ),
            average_time_to_recovery_hours=fmean(times) if times else None,
            action_counts=dict(sorted(action_counts.items())),
            action_success_counts=dict(sorted(success_counts.items())),
        )
