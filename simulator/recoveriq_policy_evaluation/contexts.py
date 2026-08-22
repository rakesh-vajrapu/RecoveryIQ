from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from recoveriq_detector_v2.artifacts import load_frozen_v2_config
from recoveriq_detector_v2.detector import OperationalDegradationDetectorV2
from recoveriq_detector_v2.replay import observable_v2_event
from recoveriq_ml.exploration import decision_key, feasible_actions
from recoveriq_ml.features import ObservableRecoveryHistory, build_feature_snapshot
from recoveriq_ml.models import RecoveryFeatureSnapshot
from recoveriq_policy.config import (
    ALTERNATE_METHOD_AVAILABLE_RATE,
    CONTACT_ALLOWED_RATE,
    EXISTING_PAYMENT_LINK_RATE,
    QUIET_HOURS_END_UTC,
    QUIET_HOURS_START_UTC,
)
from recoveriq_policy.models import (
    PolicyDecisionContext,
    PolicyOperationalProfile,
)
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.observation import PaymentObservation
from recoveriq_simulator.randomness import keyed_uniform


@dataclass(frozen=True, slots=True)
class ObservablePolicyCase:
    context: PolicyDecisionContext
    observation: PaymentObservation
    amount_bucket: str
    customer_history_bucket: str
    subscription_tenure_bucket: str
    prior_retry_bucket: str
    health_evidence_bucket: str
    time_since_failure_bucket: str


def generate_observable_policy_cases(
    *,
    scenario: GeneratedScenario,
    config: SimulatorConfig,
    frozen_detector_path: Path,
) -> tuple[ObservablePolicyCase, ...]:
    detector_config = load_frozen_v2_config(frozen_detector_path)
    detector = OperationalDegradationDetectorV2(detector_config)
    observations = {
        observation.payment_id: observation for observation in scenario.public.failure_observations
    }
    subscriptions = {
        subscription.subscription_id: subscription for subscription in scenario.public.subscriptions
    }
    last_success: dict[str, datetime] = {}
    cases: list[ObservablePolicyCase] = []
    events = sorted(
        scenario.public.observable_events,
        key=lambda event: (event.observed_at, event.event_id),
    )
    for event in events:
        detector.update(observable_v2_event(event))
        if event.success:
            last_success[event.customer_id] = event.observed_at
            continue
        observation = observations[event.payment_id]
        health = detector.get_health_context(
            observation.observed_at,
            observation.payment_method.value,
            observation.issuer,
        )
        if health.confirmed_hard_policy_gate_passed:
            raise RuntimeError("Detector V2 cannot acquire hard policy authority")
        placeholder = feasible_actions(observation, config.resolved_costs)[0]
        snapshot = build_feature_snapshot(
            observation=observation,
            subscription=subscriptions[observation.subscription_id],
            action=placeholder,
            health=health,
            recovery_history=ObservableRecoveryHistory(),
            last_success_at=last_success.get(observation.customer_id),
        )
        key = decision_key(config.seed, observation)
        profile = _operational_profile(config.seed, observation)
        context = PolicyDecisionContext(
            decision_key=key,
            decision_at=observation.observed_at,
            base_features=snapshot,
            operational=profile,
        )
        cases.append(
            ObservablePolicyCase(
                context=context,
                observation=observation,
                amount_bucket=_amount_bucket(observation.amount_minor),
                customer_history_bucket=_history_bucket(
                    observation.customer_prior_attempts,
                    observation.customer_prior_success_rate,
                ),
                subscription_tenure_bucket=_tenure_bucket(snapshot.subscription_tenure_days),
                prior_retry_bucket=_prior_retry_bucket(snapshot.current_retry_count),
                health_evidence_bucket=_health_bucket(
                    snapshot,
                    detector_config.watch_llr_threshold,
                ),
                time_since_failure_bucket=_failure_time_bucket(snapshot.failure_to_decision_hours),
            )
        )
    return tuple(cases)


def _operational_profile(seed: int, observation: PaymentObservation) -> PolicyOperationalProfile:
    contact_allowed = (
        keyed_uniform(
            seed,
            "policy-contact-permission-v1",
            observation.customer_id,
        )
        < CONTACT_ALLOWED_RATE
    )
    active_link = (
        keyed_uniform(
            seed,
            "policy-existing-payment-link-v1",
            observation.payment_id,
        )
        < EXISTING_PAYMENT_LINK_RATE
    )
    alternate_available = (
        keyed_uniform(
            seed,
            "policy-alternate-method-available-v1",
            observation.payment_id,
        )
        < ALTERNATE_METHOD_AVAILABLE_RATE
    )
    hour = observation.observed_at.hour
    quiet = hour >= QUIET_HOURS_START_UTC or hour < QUIET_HOURS_END_UTC
    return PolicyOperationalProfile(
        customer_contact_allowed=contact_allowed,
        existing_active_payment_link=active_link,
        alternate_method_available=alternate_available,
        quiet_hours=quiet,
    )


def _amount_bucket(amount_minor: int) -> str:
    if amount_minor < 50_000:
        return "LT_500_INR"
    if amount_minor < 200_000:
        return "500_TO_2000_INR"
    return "GE_2000_INR"


def _history_bucket(attempts: int, rate: float | None) -> str:
    if attempts == 0 or rate is None:
        return "NO_HISTORY"
    if rate < 0.7:
        return "LOW_LT_0_70"
    if rate < 0.9:
        return "MEDIUM_0_70_TO_0_90"
    return "HIGH_GE_0_90"


def _tenure_bucket(days: float) -> str:
    if days < 90:
        return "LT_90D"
    if days < 365:
        return "90_TO_365D"
    return "GE_365D"


def _prior_retry_bucket(count: int) -> str:
    return "0" if count == 0 else "1" if count == 1 else "2_PLUS"


def _health_bucket(snapshot: RecoveryFeatureSnapshot, watch_threshold: float) -> str:
    if snapshot.health_issuer_watch or snapshot.health_method_watch or snapshot.health_global_watch:
        return "WATCH_OR_CONFIRMED"
    maximum = max(
        snapshot.health_issuer_maximum_llr,
        snapshot.health_method_maximum_llr,
        snapshot.health_global_maximum_llr,
    )
    if maximum >= watch_threshold:
        return "HIGH_CONTINUOUS_EVIDENCE"
    if maximum > 0:
        return "LOW_CONTINUOUS_EVIDENCE"
    return "NO_SEQUENTIAL_EVIDENCE"


def _failure_time_bucket(hours: float) -> str:
    if hours <= 0.25:
        return "LE_15M"
    if hours <= 1:
        return "15M_TO_1H"
    return "GT_1H"
