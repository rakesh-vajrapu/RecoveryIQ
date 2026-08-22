from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from recoveriq_detector_v2.models import (
    EvidenceLevel,
    HealthSnapshotV2,
    PaymentHealthContextV2,
)
from recoveriq_ml.models import RecoveryFeatureSnapshot
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.observation import (
    PaymentObservation,
    RecoveryAction,
    SubscriptionRecord,
)

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


@dataclass(slots=True)
class ObservableRecoveryHistory:
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    nudges: int = 0
    retries: int = 0
    payment_links: int = 0


def build_feature_snapshot(
    *,
    observation: PaymentObservation,
    subscription: SubscriptionRecord,
    action: RecoveryAction,
    health: PaymentHealthContextV2,
    recovery_history: ObservableRecoveryHistory,
    last_success_at: datetime | None,
) -> RecoveryFeatureSnapshot:
    decision_at = observation.observed_at
    hour = decision_at.hour + decision_at.minute / 60 + decision_at.second / 3600
    weekday = decision_at.weekday()
    customer_successes = round(
        (observation.customer_prior_success_rate or 0.0) * observation.customer_prior_attempts
    )
    previous_attempt_at = max(
        (event.observed_at for event in observation.prior_events),
        default=None,
    )
    issuer = _health_fields("issuer", health.issuer_health)
    method = _health_fields("method", health.method_health)
    global_health = _health_fields("global", health.global_health)
    issuer_snapshot = health.issuer_health
    parent_levels = {
        EvidenceLevel.WATCH,
        EvidenceLevel.CONFIRMED,
        EvidenceLevel.RECOVERING,
    }
    return RecoveryFeatureSnapshot(
        payment_method=observation.payment_method.value,
        issuer=observation.issuer or "UNKNOWN",
        failure_reason=observation.failure_reason.value,
        failure_source=observation.failure_source.value,
        action_type=action.action_type.value,
        amount_minor=observation.amount_minor,
        attempt_number=observation.attempt_number,
        decision_hour_sin=math.sin(2 * math.pi * hour / 24),
        decision_hour_cos=math.cos(2 * math.pi * hour / 24),
        decision_day_sin=math.sin(2 * math.pi * weekday / 7),
        decision_day_cos=math.cos(2 * math.pi * weekday / 7),
        failure_to_decision_hours=(decision_at - observation.failure_occurred_at).total_seconds()
        / 3600,
        time_since_previous_payment_attempt_hours=_hours_since(
            decision_at,
            previous_attempt_at,
        ),
        delay_hours=action.scheduled_delay_hours,
        customer_contact_action=action.action_type in CONTACT_ACTIONS,
        payment_method_change_action=action.action_type in METHOD_CHANGE_ACTIONS,
        current_contact_count=0,
        current_retry_count=0,
        subscription_prior_attempts=observation.subscription_prior_attempts,
        subscription_prior_successes=observation.subscription_prior_successes,
        subscription_success_rate=(
            observation.subscription_prior_successes / observation.subscription_prior_attempts
            if observation.subscription_prior_attempts
            else None
        ),
        customer_prior_attempts=observation.customer_prior_attempts,
        customer_prior_successes=customer_successes,
        customer_prior_failed_renewals=max(
            0,
            observation.customer_prior_attempts - customer_successes,
        ),
        customer_prior_success_rate=observation.customer_prior_success_rate,
        previous_recovery_attempts=recovery_history.recovery_attempts,
        previous_successful_recovery_count=recovery_history.successful_recoveries,
        previous_nudge_count=recovery_history.nudges,
        previous_retry_count=recovery_history.retries,
        previous_payment_link_count=recovery_history.payment_links,
        subscription_tenure_days=max(
            0.0,
            (decision_at - subscription.created_at).total_seconds() / 86_400,
        ),
        time_since_last_successful_payment_hours=_hours_since(decision_at, last_success_at),
        **issuer,
        health_issuer_dominant_current_share=_dominant(
            issuer_snapshot,
            "current_share",
        ),
        health_issuer_dominant_baseline_share=_dominant(
            issuer_snapshot,
            "baseline_share",
        ),
        health_issuer_dominant_absolute_increase=_dominant(
            issuer_snapshot,
            "absolute_increase",
        ),
        health_issuer_dominant_relative_lift=_dominant(
            issuer_snapshot,
            "relative_lift",
        ),
        health_issuer_dominant_support=int(_dominant(issuer_snapshot, "support_count") or 0),
        health_issuer_time_since_watch_hours=(
            issuer_snapshot.time_since_watch_seconds / 3600
            if issuer_snapshot and issuer_snapshot.time_since_watch_seconds is not None
            else None
        ),
        health_issuer_time_since_confirmed_hours=(
            issuer_snapshot.time_since_confirmed_seconds / 3600
            if issuer_snapshot and issuer_snapshot.time_since_confirmed_seconds is not None
            else None
        ),
        health_issuer_parent_method_watch=bool(
            issuer_snapshot and issuer_snapshot.parent_corroboration.method_level in parent_levels
        ),
        health_issuer_parent_global_watch=bool(
            issuer_snapshot and issuer_snapshot.parent_corroboration.global_level in parent_levels
        ),
        **method,
        **global_health,
    )


def snapshot_for_action(
    snapshot: RecoveryFeatureSnapshot,
    action: RecoveryAction,
) -> RecoveryFeatureSnapshot:
    return snapshot.model_copy(
        update={
            "action_type": action.action_type.value,
            "delay_hours": action.scheduled_delay_hours,
            "customer_contact_action": action.action_type in CONTACT_ACTIONS,
            "payment_method_change_action": action.action_type in METHOD_CHANGE_ACTIONS,
        }
    )


def _health_fields(
    prefix: str,
    snapshot: HealthSnapshotV2 | None,
) -> dict[str, object]:
    windows = {window.minutes: window for window in snapshot.recent_windows} if snapshot else {}
    baseline = snapshot.baseline_success_probability if snapshot else None

    def rate(minutes: int) -> float | None:
        window = windows.get(minutes)
        return window.success_rate if window else None

    def attempts(minutes: int) -> int:
        window = windows.get(minutes)
        return window.attempts if window else 0

    def delta(minutes: int) -> float | None:
        current = rate(minutes)
        return current - baseline if current is not None and baseline is not None else None

    active_levels = {
        EvidenceLevel.WATCH,
        EvidenceLevel.CONFIRMED,
        EvidenceLevel.RECOVERING,
    }
    confirmed_levels = {EvidenceLevel.CONFIRMED, EvidenceLevel.RECOVERING}
    return {
        f"health_{prefix}_available": snapshot is not None,
        f"health_{prefix}_baseline_success": baseline,
        f"health_{prefix}_baseline_attempts": snapshot.baseline_attempts if snapshot else 0,
        f"health_{prefix}_rate_5m": rate(5),
        f"health_{prefix}_attempts_5m": attempts(5),
        f"health_{prefix}_delta_5m": delta(5),
        f"health_{prefix}_rate_15m": rate(15),
        f"health_{prefix}_attempts_15m": attempts(15),
        f"health_{prefix}_delta_15m": delta(15),
        f"health_{prefix}_rate_60m": rate(60),
        f"health_{prefix}_attempts_60m": attempts(60),
        f"health_{prefix}_delta_60m": delta(60),
        f"health_{prefix}_maximum_llr": (
            snapshot.sequential_evidence.maximum_log_likelihood_ratio if snapshot else 0.0
        ),
        f"health_{prefix}_recovery_llr": (
            snapshot.sequential_evidence.recovery_log_likelihood_ratio if snapshot else 0.0
        ),
        f"health_{prefix}_failure_js": (
            snapshot.failure_distribution.jensen_shannon_divergence if snapshot else None
        ),
        f"health_{prefix}_watch": bool(snapshot and snapshot.evidence_level in active_levels),
        f"health_{prefix}_confirmed": bool(
            snapshot and snapshot.evidence_level in confirmed_levels
        ),
    }


def _dominant(snapshot: HealthSnapshotV2 | None, name: str) -> float | int | None:
    if snapshot is None or not snapshot.failure_distribution.dominant_shifts:
        return None
    shift = snapshot.failure_distribution.dominant_shifts[0]
    values: dict[str, float | int | None] = {
        "current_share": shift.current_share,
        "baseline_share": shift.baseline_share,
        "absolute_increase": shift.absolute_increase,
        "relative_lift": shift.relative_lift,
        "support_count": shift.support_count,
    }
    return values[name]


def _hours_since(later: datetime, earlier: datetime | None) -> float | None:
    if earlier is None:
        return None
    return max(0.0, (later - earlier).total_seconds() / 3600)
