from __future__ import annotations

import hashlib
import math
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from numpy.random import Generator

from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import (
    EventType,
    FailureReason,
    FailureSource,
    InstrumentState,
    PaymentMethod,
    TrueFailureCause,
)
from recoveriq_simulator.events import EventQueue
from recoveriq_simulator.ground_truth import (
    CustomerGroundTruth,
    DegradationIncidentGroundTruth,
    EnvironmentGroundTruth,
    GeneratedScenario,
    MerchantGroundTruth,
    PaymentGroundTruth,
    SubscriptionGroundTruth,
)
from recoveriq_simulator.observation import (
    CustomerRecord,
    MerchantRecord,
    ObservedPaymentEvent,
    PaymentObservation,
    PaymentRecord,
    PublicScenario,
    SubscriptionRecord,
)

ISSUERS = ("ISSUER_A", "ISSUER_B", "ISSUER_C", "ISSUER_D")
METHODS = tuple(PaymentMethod)

type History = dict[str, list[ObservedPaymentEvent]]
type ScopeKey = tuple[PaymentMethod, str]


@dataclass(frozen=True, slots=True)
class _PaymentDue:
    payment_id: str
    subscription: SubscriptionRecord


@dataclass(frozen=True, slots=True)
class _PendingDelivery:
    event: ObservedPaymentEvent


def _synthetic_id(kind: str, index: int, width: int = 6) -> str:
    return f"SIM_{kind}_{index:0{width}d}"


def _choice[T](
    rng: Generator, values: tuple[T, ...], probabilities: list[float] | None = None
) -> T:
    index = int(rng.choice(len(values), p=probabilities))
    return values[index]


class ScenarioGenerator:
    """Build a reproducible event stream and privately retained environment truth."""

    def __init__(self, config: SimulatorConfig) -> None:
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        self._payment_due_offsets: dict[str, float] = {}

    def generate(self) -> GeneratedScenario:
        merchants, merchant_truth = self._generate_merchants()
        customers, customer_truth = self._generate_customers(merchants)
        subscriptions, subscription_truth = self._generate_subscriptions(
            customers, merchant_truth, customer_truth
        )
        incidents = self._generate_incidents()
        due_events = self._generate_payment_dues(subscriptions)

        queue = EventQueue()
        for incident in incidents:
            queue.push(incident.start_at, EventType.INCIDENT_STARTED, incident)
            queue.push(incident.end_at, EventType.INCIDENT_ENDED, incident)
        for payment_due in due_events:
            due_at = self._due_at(payment_due.subscription, payment_due.payment_id)
            queue.push(due_at, EventType.PAYMENT_DUE, payment_due)

        active_incidents: dict[str, DegradationIncidentGroundTruth] = {}
        payments: list[PaymentRecord] = []
        payment_truth: dict[str, PaymentGroundTruth] = {}
        observable_events: list[ObservedPaymentEvent] = []
        observations: list[PaymentObservation] = []
        customer_history: History = defaultdict(list)
        subscription_history: History = defaultdict(list)
        scope_history: dict[ScopeKey, deque[ObservedPaymentEvent]] = defaultdict(deque)

        while queue:
            scheduled = queue.pop()
            if scheduled.event_type is EventType.INCIDENT_STARTED:
                incident = self._expect_incident(scheduled.payload)
                active_incidents[incident.incident_id] = incident
            elif scheduled.event_type is EventType.INCIDENT_ENDED:
                incident = self._expect_incident(scheduled.payload)
                active_incidents.pop(incident.incident_id, None)
            elif scheduled.event_type is EventType.PAYMENT_DUE:
                due = self._expect_payment_due(scheduled.payload)
                record, truth, event = self._attempt_initial_payment(
                    due=due,
                    due_at=scheduled.execute_at,
                    merchant_truth=merchant_truth[due.subscription.merchant_id],
                    customer_truth=customer_truth[due.subscription.customer_id],
                    subscription_truth=subscription_truth[due.subscription.subscription_id],
                    active_incidents=active_incidents,
                )
                payments.append(record)
                payment_truth[record.payment_id] = truth
                queue.push(
                    event.observed_at, EventType.STATUS_EVENT_DELIVERED, _PendingDelivery(event)
                )
            elif scheduled.event_type is EventType.STATUS_EVENT_DELIVERED:
                pending = self._expect_pending_delivery(scheduled.payload)
                event = pending.event
                if not event.success:
                    observations.append(
                        self._build_observation(
                            event,
                            customer_history,
                            subscription_history,
                            scope_history,
                        )
                    )
                self._record_observable_event(
                    event,
                    observable_events,
                    customer_history,
                    subscription_history,
                    scope_history,
                )

        public = PublicScenario(
            experiment_id=self.config.experiment_id,
            merchants=tuple(merchants),
            customers=tuple(customers),
            subscriptions=tuple(subscriptions),
            payments=tuple(payments),
            observable_events=tuple(observable_events),
            failure_observations=tuple(observations),
        )
        hidden = EnvironmentGroundTruth(
            seed=self.config.seed,
            merchants=merchant_truth,
            customers=customer_truth,
            subscriptions=subscription_truth,
            payments=payment_truth,
            incidents=tuple(incidents),
        )
        return GeneratedScenario(public=public, ground_truth=hidden)

    def _generate_merchants(
        self,
    ) -> tuple[list[MerchantRecord], dict[str, MerchantGroundTruth]]:
        median_palette = np.array(
            [29_900, 49_900, 79_900, 119_900, 179_900, 249_900, 349_900, 499_900]
        )
        self.rng.shuffle(median_palette)
        records: list[MerchantRecord] = []
        truth: dict[str, MerchantGroundTruth] = {}
        for index in range(self.config.merchant_count):
            merchant_id = _synthetic_id("MERCHANT", index + 1, 3)
            method_weights = self.rng.dirichlet(np.array([3.0, 3.5, 1.5, 2.0]))
            records.append(
                MerchantRecord(
                    merchant_id=merchant_id,
                    display_name=f"Synthetic Merchant {index + 1:02d}",
                )
            )
            truth[merchant_id] = MerchantGroundTruth(
                merchant_id=merchant_id,
                median_amount_minor=int(median_palette[index]),
                amount_sigma=float(self.rng.uniform(0.45, 0.82)),
                baseline_success_rate=float(self.rng.uniform(0.87, 0.95)),
                payment_method_mix={
                    method: float(weight)
                    for method, weight in zip(METHODS, method_weights, strict=True)
                },
            )
        return records, truth

    def _generate_customers(
        self, merchants: list[MerchantRecord]
    ) -> tuple[list[CustomerRecord], dict[str, CustomerGroundTruth]]:
        merchant_assignments = np.arange(self.config.customer_count) % len(merchants)
        self.rng.shuffle(merchant_assignments)
        records: list[CustomerRecord] = []
        truth: dict[str, CustomerGroundTruth] = {}
        for index, merchant_index in enumerate(merchant_assignments):
            customer_id = _synthetic_id("CUSTOMER", index + 1, 7)
            merchant_id = merchants[int(merchant_index)].merchant_id
            records.append(CustomerRecord(customer_id=customer_id, merchant_id=merchant_id))
            truth[customer_id] = CustomerGroundTruth(
                customer_id=customer_id,
                liquidity_propensity=float(self.rng.beta(5.0, 2.2)),
                historical_reliability=float(self.rng.beta(7.0, 2.0)),
                nudge_responsiveness=float(self.rng.beta(3.0, 3.0)),
                payment_method_stability=float(self.rng.beta(8.0, 2.0)),
                instrument_update_propensity=float(self.rng.beta(3.2, 2.2)),
                retry_sensitivity=float(self.rng.beta(4.0, 3.0)),
            )
        return records, truth

    def _generate_subscriptions(
        self,
        customers: list[CustomerRecord],
        merchant_truth: dict[str, MerchantGroundTruth],
        customer_truth: dict[str, CustomerGroundTruth],
    ) -> tuple[list[SubscriptionRecord], dict[str, SubscriptionGroundTruth]]:
        records: list[SubscriptionRecord] = []
        truth: dict[str, SubscriptionGroundTruth] = {}
        for index in range(self.config.subscription_count):
            customer = (
                customers[index]
                if index < len(customers)
                else customers[int(self.rng.integers(0, len(customers)))]
            )
            profile = merchant_truth[customer.merchant_id]
            methods = tuple(profile.payment_method_mix)
            probabilities = [profile.payment_method_mix[method] for method in methods]
            method = _choice(self.rng, methods, probabilities)
            issuer = _choice(self.rng, ISSUERS)
            amount = int(
                np.clip(
                    self.rng.lognormal(
                        mean=math.log(profile.median_amount_minor), sigma=profile.amount_sigma
                    ),
                    self.config.min_payment_amount_minor,
                    self.config.max_payment_amount_minor,
                )
            )
            amount = max(self.config.min_payment_amount_minor, int(round(amount / 100) * 100))
            subscription_id = _synthetic_id("SUBSCRIPTION", index + 1, 7)
            created_at = self.config.start_time - timedelta(days=int(self.rng.integers(60, 730)))
            records.append(
                SubscriptionRecord(
                    subscription_id=subscription_id,
                    customer_id=customer.customer_id,
                    merchant_id=customer.merchant_id,
                    amount_minor=amount,
                    cadence_days=30,
                    created_at=created_at,
                    payment_method=method,
                    issuer=issuer,
                )
            )
            stability = customer_truth[customer.customer_id].payment_method_stability
            state_draw = float(self.rng.random())
            if method is PaymentMethod.MANDATE and state_draw < 0.035 + 0.04 * (1 - stability):
                instrument_state = InstrumentState.INACTIVE
            elif state_draw < 0.025 + 0.04 * (1 - stability):
                instrument_state = InstrumentState.EXPIRED
            elif state_draw < 0.09 + 0.08 * (1 - stability):
                instrument_state = InstrumentState.UNSTABLE
            else:
                instrument_state = InstrumentState.VALID
            truth[subscription_id] = SubscriptionGroundTruth(
                subscription_id=subscription_id,
                instrument_state=instrument_state,
            )
        return records, truth

    def _generate_incidents(self) -> list[DegradationIncidentGroundTruth]:
        incidents: list[DegradationIncidentGroundTruth] = []
        for index in range(self.config.incident_count):
            start_offset_hours = float(
                self.rng.uniform(24, max(25, self.config.horizon_days * 24 - 48))
            )
            duration_hours = float(self.rng.uniform(12, 36))
            start_at = self.config.start_time + timedelta(hours=start_offset_hours)
            end_at = min(
                start_at + timedelta(hours=duration_hours),
                self.config.start_time + timedelta(days=self.config.horizon_days),
            )
            severity = float(self.rng.uniform(0.38, 0.72))
            baseline = float(self.rng.uniform(0.9, 0.97))
            dominant = _choice(
                self.rng,
                (
                    TrueFailureCause.ISSUER_DEGRADATION,
                    TrueFailureCause.NETWORK_INSTABILITY,
                ),
            )
            incidents.append(
                DegradationIncidentGroundTruth(
                    incident_id=_synthetic_id("INCIDENT", index + 1, 4),
                    start_at=start_at,
                    end_at=end_at,
                    payment_method=_choice(self.rng, METHODS),
                    issuer=_choice(self.rng, ISSUERS),
                    severity=severity,
                    baseline_health=baseline,
                    degraded_health=baseline * (1 - severity),
                    dominant_failure_cause=dominant,
                )
            )
        return sorted(incidents, key=lambda incident: (incident.start_at, incident.incident_id))

    def _generate_payment_dues(self, subscriptions: list[SubscriptionRecord]) -> list[_PaymentDue]:
        cycles = max(
            math.ceil(self.config.num_payment_attempts / len(subscriptions)),
            math.ceil(self.config.horizon_days / 30),
        )
        candidates: list[tuple[float, _PaymentDue]] = []
        payment_index = 0
        for subscription in subscriptions:
            stagger = float(self.rng.uniform(0, 30))
            time_of_day = float(self.rng.uniform(0, 24))
            for cycle in range(cycles):
                payment_index += 1
                payment_id = _synthetic_id("PAYMENT", payment_index, 8)
                due_offset = stagger + cycle * subscription.cadence_days + time_of_day / 24
                candidates.append((due_offset, _PaymentDue(payment_id, subscription)))
        candidates.sort(key=lambda item: (item[0], item[1].payment_id))
        # Preserve the configured time horizon at every scale. Taking the first N
        # candidates would make small test runs cover only the first few days.
        selected_indexes = np.linspace(
            0,
            len(candidates) - 1,
            num=self.config.num_payment_attempts,
            dtype=int,
        )
        selected = [candidates[int(index)] for index in selected_indexes]
        self._payment_due_offsets = {due.payment_id: offset for offset, due in selected}
        return [due for _, due in selected]

    def _due_at(self, _: SubscriptionRecord, payment_id: str) -> datetime:
        return self.config.start_time + timedelta(days=self._payment_due_offsets[payment_id])

    def _attempt_initial_payment(
        self,
        *,
        due: _PaymentDue,
        due_at: datetime,
        merchant_truth: MerchantGroundTruth,
        customer_truth: CustomerGroundTruth,
        subscription_truth: SubscriptionGroundTruth,
        active_incidents: dict[str, DegradationIncidentGroundTruth],
    ) -> tuple[PaymentRecord, PaymentGroundTruth, ObservedPaymentEvent]:
        incident = self._matching_incident(due.subscription, active_incidents)
        probability = self._initial_success_probability(
            due.subscription,
            merchant_truth,
            customer_truth,
            subscription_truth,
            incident,
        )
        success = bool(self.rng.random() < probability)
        true_cause = None
        reason = None
        source = None
        if not success:
            true_cause = self._select_failure_cause(
                due.subscription,
                customer_truth,
                subscription_truth,
                incident,
            )
            reason, source = self._observable_failure(true_cause)

        event_delay = 0
        if self.rng.random() < self.config.delayed_event_rate:
            event_delay = int(self.rng.integers(1, self.config.max_event_delay_minutes + 1))
        issuer = (
            None if self.rng.random() < self.config.missing_issuer_rate else due.subscription.issuer
        )
        occurred_at = due_at
        observed_at = occurred_at + timedelta(minutes=event_delay)
        event = ObservedPaymentEvent(
            event_id=f"{due.payment_id}:INITIAL",
            payment_id=due.payment_id,
            subscription_id=due.subscription.subscription_id,
            customer_id=due.subscription.customer_id,
            merchant_id=due.subscription.merchant_id,
            occurred_at=occurred_at,
            observed_at=observed_at,
            success=success,
            payment_method=due.subscription.payment_method,
            issuer=issuer,
            failure_reason=reason,
            failure_source=source,
            attempt_number=1,
            amount_minor=due.subscription.amount_minor,
        )
        payment = PaymentRecord(
            payment_id=due.payment_id,
            subscription_id=due.subscription.subscription_id,
            customer_id=due.subscription.customer_id,
            merchant_id=due.subscription.merchant_id,
            amount_minor=due.subscription.amount_minor,
            due_at=occurred_at,
            initial_status="SUCCEEDED" if success else "FAILED",
            observable_failure_reason=reason,
        )
        truth = PaymentGroundTruth(
            payment_id=due.payment_id,
            initial_success=success,
            initial_success_probability=probability,
            true_failure_cause=true_cause,
            instrument_state=subscription_truth.instrument_state,
            incident_id=incident.incident_id if incident is not None else None,
        )
        return payment, truth, event

    def _initial_success_probability(
        self,
        subscription: SubscriptionRecord,
        merchant: MerchantGroundTruth,
        customer: CustomerGroundTruth,
        subscription_truth: SubscriptionGroundTruth,
        incident: DegradationIncidentGroundTruth | None,
    ) -> float:
        probability = merchant.baseline_success_rate
        probability += 0.05 * (customer.historical_reliability - 0.7)
        probability += 0.03 * (customer.liquidity_propensity - 0.65)
        method_adjustment = {
            PaymentMethod.CARD: 0.0,
            PaymentMethod.UPI: 0.01,
            PaymentMethod.NETBANKING: -0.025,
            PaymentMethod.MANDATE: -0.01,
        }
        probability += method_adjustment[subscription.payment_method]
        state = subscription_truth.instrument_state
        if state is InstrumentState.EXPIRED:
            probability *= 0.07
        elif state is InstrumentState.INACTIVE:
            probability *= 0.1
        elif state is InstrumentState.UNSTABLE:
            probability *= 0.72
        if incident is not None:
            probability *= 1 - 0.9 * incident.severity
        return float(np.clip(probability, 0.015, 0.985))

    def _select_failure_cause(
        self,
        subscription: SubscriptionRecord,
        customer: CustomerGroundTruth,
        subscription_truth: SubscriptionGroundTruth,
        incident: DegradationIncidentGroundTruth | None,
    ) -> TrueFailureCause:
        weights = {
            TrueFailureCause.LIQUIDITY_SHORTFALL: 0.18 + 0.45 * (1 - customer.liquidity_propensity),
            TrueFailureCause.ISSUER_DEGRADATION: 0.1,
            TrueFailureCause.AUTHENTICATION_FRICTION: 0.15,
            TrueFailureCause.INVALID_INSTRUMENT: 0.04,
            TrueFailureCause.INACTIVE_MANDATE: 0.03,
            TrueFailureCause.NETWORK_INSTABILITY: 0.14,
            TrueFailureCause.CUSTOMER_CONFIRMATION: 0.1
            + 0.12 * (1 - customer.nudge_responsiveness),
            TrueFailureCause.UNKNOWN_TEMPORARY: 0.08,
        }
        if subscription.payment_method in {PaymentMethod.CARD, PaymentMethod.UPI}:
            weights[TrueFailureCause.AUTHENTICATION_FRICTION] += 0.08
        if subscription_truth.instrument_state is InstrumentState.EXPIRED:
            weights[TrueFailureCause.INVALID_INSTRUMENT] += 2.2
        elif subscription_truth.instrument_state is InstrumentState.INACTIVE:
            weights[TrueFailureCause.INACTIVE_MANDATE] += 2.2
        elif subscription_truth.instrument_state is InstrumentState.UNSTABLE:
            weights[TrueFailureCause.NETWORK_INSTABILITY] += 0.35
        if incident is not None:
            weights[incident.dominant_failure_cause] += 1.8 * incident.severity
            weights[TrueFailureCause.NETWORK_INSTABILITY] += 0.6 * incident.severity

        causes = tuple(weights)
        raw = np.array([weights[cause] for cause in causes])
        probabilities = list(raw / raw.sum())
        return _choice(self.rng, causes, probabilities)

    def _observable_failure(self, cause: TrueFailureCause) -> tuple[FailureReason, FailureSource]:
        primary = {
            TrueFailureCause.LIQUIDITY_SHORTFALL: (
                FailureReason.INSUFFICIENT_FUNDS,
                FailureSource.CUSTOMER,
            ),
            TrueFailureCause.ISSUER_DEGRADATION: (
                FailureReason.ISSUER_UNAVAILABLE,
                FailureSource.ISSUER,
            ),
            TrueFailureCause.AUTHENTICATION_FRICTION: (
                FailureReason.AUTHENTICATION_FAILURE,
                FailureSource.CUSTOMER,
            ),
            TrueFailureCause.INVALID_INSTRUMENT: (
                FailureReason.INSTRUMENT_EXPIRED,
                FailureSource.INSTRUMENT,
            ),
            TrueFailureCause.INACTIVE_MANDATE: (
                FailureReason.MANDATE_INACTIVE,
                FailureSource.MANDATE,
            ),
            TrueFailureCause.NETWORK_INSTABILITY: (
                FailureReason.TEMPORARY_NETWORK_ERROR,
                FailureSource.NETWORK,
            ),
            TrueFailureCause.CUSTOMER_CONFIRMATION: (
                FailureReason.CUSTOMER_ACTION_REQUIRED,
                FailureSource.CUSTOMER,
            ),
            TrueFailureCause.UNKNOWN_TEMPORARY: (
                FailureReason.UNKNOWN_TRANSIENT_ERROR,
                FailureSource.UNKNOWN,
            ),
        }
        if self.rng.random() < self.config.unknown_failure_rate:
            return FailureReason.UNKNOWN_TRANSIENT_ERROR, FailureSource.UNKNOWN
        if self.rng.random() < 0.18:
            overlaps = {
                TrueFailureCause.LIQUIDITY_SHORTFALL: (
                    FailureReason.CUSTOMER_ACTION_REQUIRED,
                    FailureSource.CUSTOMER,
                ),
                TrueFailureCause.ISSUER_DEGRADATION: (
                    FailureReason.TEMPORARY_NETWORK_ERROR,
                    FailureSource.NETWORK,
                ),
                TrueFailureCause.AUTHENTICATION_FRICTION: (
                    FailureReason.CUSTOMER_ACTION_REQUIRED,
                    FailureSource.CUSTOMER,
                ),
                TrueFailureCause.INVALID_INSTRUMENT: (
                    FailureReason.AUTHENTICATION_FAILURE,
                    FailureSource.INSTRUMENT,
                ),
                TrueFailureCause.INACTIVE_MANDATE: (
                    FailureReason.CUSTOMER_ACTION_REQUIRED,
                    FailureSource.MANDATE,
                ),
                TrueFailureCause.NETWORK_INSTABILITY: (
                    FailureReason.ISSUER_UNAVAILABLE,
                    FailureSource.ISSUER,
                ),
                TrueFailureCause.CUSTOMER_CONFIRMATION: (
                    FailureReason.AUTHENTICATION_FAILURE,
                    FailureSource.CUSTOMER,
                ),
                TrueFailureCause.UNKNOWN_TEMPORARY: (
                    FailureReason.TEMPORARY_NETWORK_ERROR,
                    FailureSource.UNKNOWN,
                ),
            }
            return overlaps[cause]
        return primary[cause]

    @staticmethod
    def _matching_incident(
        subscription: SubscriptionRecord,
        active: dict[str, DegradationIncidentGroundTruth],
    ) -> DegradationIncidentGroundTruth | None:
        matching = [
            incident
            for incident in active.values()
            if incident.payment_method is subscription.payment_method
            and incident.issuer == subscription.issuer
        ]
        return max(matching, key=lambda item: item.severity, default=None)

    @staticmethod
    def _build_observation(
        event: ObservedPaymentEvent,
        customer_history: History,
        subscription_history: History,
        scope_history: dict[ScopeKey, deque[ObservedPaymentEvent]],
    ) -> PaymentObservation:
        customer_events = customer_history[event.customer_id]
        subscription_events = subscription_history[event.subscription_id]
        scope_key = (event.payment_method, event.issuer or "UNKNOWN")
        scope_events = scope_history[scope_key]
        cutoff = event.observed_at - timedelta(hours=6)
        while scope_events and scope_events[0].observed_at < cutoff:
            scope_events.popleft()
        customer_successes = sum(item.success for item in customer_events)
        scope_successes = sum(item.success for item in scope_events)
        if event.failure_reason is None or event.failure_source is None:
            raise ValueError("failed event must have observable failure fields")
        return PaymentObservation(
            payment_id=event.payment_id,
            subscription_id=event.subscription_id,
            customer_id=event.customer_id,
            merchant_id=event.merchant_id,
            observed_at=event.observed_at,
            failure_occurred_at=event.occurred_at,
            amount_minor=event.amount_minor,
            payment_method=event.payment_method,
            issuer=event.issuer,
            failure_reason=event.failure_reason,
            failure_source=event.failure_source,
            attempt_number=event.attempt_number,
            subscription_prior_attempts=len(subscription_events),
            subscription_prior_successes=sum(item.success for item in subscription_events),
            customer_prior_attempts=len(customer_events),
            customer_prior_success_rate=(
                customer_successes / len(customer_events) if customer_events else None
            ),
            recent_scope_attempts=len(scope_events),
            recent_scope_success_rate=(
                scope_successes / len(scope_events) if scope_events else None
            ),
            prior_events=tuple(customer_events[-5:]),
        )

    @staticmethod
    def _record_observable_event(
        event: ObservedPaymentEvent,
        observable_events: list[ObservedPaymentEvent],
        customer_history: History,
        subscription_history: History,
        scope_history: dict[ScopeKey, deque[ObservedPaymentEvent]],
    ) -> None:
        observable_events.append(event)
        customer_history[event.customer_id].append(event)
        subscription_history[event.subscription_id].append(event)
        scope_history[(event.payment_method, event.issuer or "UNKNOWN")].append(event)

    @staticmethod
    def _expect_incident(payload: object) -> DegradationIncidentGroundTruth:
        if not isinstance(payload, DegradationIncidentGroundTruth):
            raise TypeError("incident event payload is invalid")
        return payload

    @staticmethod
    def _expect_payment_due(payload: object) -> _PaymentDue:
        if not isinstance(payload, _PaymentDue):
            raise TypeError("payment due payload is invalid")
        return payload

    @staticmethod
    def _expect_pending_delivery(payload: object) -> _PendingDelivery:
        if not isinstance(payload, _PendingDelivery):
            raise TypeError("delivery event payload is invalid")
        return payload


def scenario_digest(scenario: GeneratedScenario) -> str:
    payload = scenario.model_dump_json(exclude_none=False)
    return hashlib.sha256(payload.encode()).hexdigest()
