from __future__ import annotations

import math
from datetime import datetime

from recoveriq_ml_v2.models import RecoveryFeatureSnapshotV2
from recoveriq_sequential.models import (
    SequentialCandidate,
    SequentialEpisodeState,
    SequentialEpisodeTemplate,
)


def build_feature_snapshot_v2(
    template: SequentialEpisodeTemplate,
    state: SequentialEpisodeState,
    candidate: SequentialCandidate,
) -> RecoveryFeatureSnapshotV2:
    observation = template.observation
    decision_at = state.decision_at
    hour = decision_at.hour + decision_at.minute / 60 + decision_at.second / 3600
    weekday = decision_at.weekday()
    customer_successes = round(
        (observation.customer_prior_success_rate or 0.0) * observation.customer_prior_attempts
    )
    previous_attempt_at = max(
        (event.observed_at for event in observation.prior_events),
        default=None,
    )
    return RecoveryFeatureSnapshotV2(
        payment_method=observation.payment_method.value,
        issuer=observation.issuer or "UNKNOWN",
        failure_reason=observation.failure_reason.value,
        failure_source=observation.failure_source.value,
        action_type=candidate.recovery_action.action_type.value,
        action_label=candidate.label,
        last_action_type=state.last_action_type,
        last_action_label=state.last_action_label,
        previous_intervention_result=state.previous_intervention_result.value,
        amount_minor=observation.amount_minor,
        attempt_number=observation.attempt_number,
        decision_hour_sin=math.sin(2 * math.pi * hour / 24),
        decision_hour_cos=math.cos(2 * math.pi * hour / 24),
        decision_day_sin=math.sin(2 * math.pi * weekday / 7),
        decision_day_cos=math.cos(2 * math.pi * weekday / 7),
        elapsed_episode_hours=_hours_between(decision_at, observation.observed_at),
        time_since_previous_payment_attempt_hours=_optional_hours(decision_at, previous_attempt_at),
        time_since_last_successful_payment_hours=_optional_hours(
            decision_at, template.last_success_at
        ),
        subscription_tenure_days=max(
            0.0,
            (decision_at - template.subscription.created_at).total_seconds() / 86_400,
        ),
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
            0, observation.customer_prior_attempts - customer_successes
        ),
        customer_prior_success_rate=observation.customer_prior_success_rate,
        decision_index=state.decision_index,
        prior_autonomous_interventions=state.intervention_count,
        retries_executed=state.retry_count,
        contacts_sent=state.contact_count,
        payment_links_created=state.payment_link_count,
        method_updates_requested=state.method_update_count,
        alternate_methods_used=state.alternate_method_count,
        existing_payment_link=state.active_payment_link,
        method_update_requested=state.method_update_requested,
        alternate_method_used=state.alternate_method_used,
        hours_since_last_action=_optional_hours(decision_at, state.last_action_executed_at),
        action_delay_hours=candidate.recovery_action.scheduled_delay_hours,
        action_observation_window_hours=candidate.observation_window_hours,
        customer_contact_action=candidate.is_customer_contact,
        payment_method_change_action=candidate.requests_method_change,
        quiet_hours_delay_applied=candidate.quiet_hours_delay_applied,
    )


def _hours_between(later: datetime, earlier: datetime) -> float:
    return max(0.0, (later - earlier).total_seconds() / 3600)


def _optional_hours(later: datetime, earlier: datetime | None) -> float | None:
    return _hours_between(later, earlier) if earlier is not None else None
