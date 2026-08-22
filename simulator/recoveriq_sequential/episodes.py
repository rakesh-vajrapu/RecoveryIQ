from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from recoveriq_sequential.config import (
    ALTERNATE_METHOD_AVAILABLE_RATE,
    CONTACT_ACTIONS,
    CONTACT_ALLOWED_RATE,
    CONTACT_OBSERVATION_WINDOW_HOURS,
    EPISODE_HORIZON_HOURS,
    INITIAL_ACTIVE_LINK_RATE,
    MAX_AUTONOMOUS_INTERVENTIONS,
    MAX_CONTACTS,
    MAX_RETRIES,
    METHOD_CHANGE_ACTIONS,
    MIN_RETRY_INTERVAL_HOURS,
    QUIET_HOURS_END_UTC,
    QUIET_HOURS_START_UTC,
    RETRY_ACTIONS,
    RETRY_OBSERVATION_WINDOW_HOURS,
    SEQUENTIAL_CANDIDATE_SPECS,
)
from recoveriq_sequential.models import (
    EpisodeTermination,
    PreviousInterventionResult,
    SequentialActionOutcome,
    SequentialCandidate,
    SequentialEpisodeState,
    SequentialEpisodeTemplate,
    SequentialOperationalProfile,
)
from recoveriq_simulator.config import SimulationCosts
from recoveriq_simulator.enums import ActionType
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.observation import RecoveryAction
from recoveriq_simulator.randomness import keyed_uniform


def build_episode_templates(
    scenario: GeneratedScenario,
    seed: int,
) -> tuple[SequentialEpisodeTemplate, ...]:
    observations = {
        observation.payment_id: observation for observation in scenario.public.failure_observations
    }
    subscriptions = {
        subscription.subscription_id: subscription for subscription in scenario.public.subscriptions
    }
    last_success: dict[str, datetime] = {}
    templates: list[SequentialEpisodeTemplate] = []
    for event in sorted(
        scenario.public.observable_events,
        key=lambda item: (item.observed_at, item.event_id),
    ):
        if event.success:
            last_success[event.customer_id] = event.observed_at
            continue
        observation = observations[event.payment_id]
        episode_id = _opaque_episode_id(seed, observation.payment_id)
        templates.append(
            SequentialEpisodeTemplate(
                episode_id=episode_id,
                observation=observation,
                subscription=subscriptions[observation.subscription_id],
                last_success_at=last_success.get(observation.customer_id),
                operational=SequentialOperationalProfile(
                    customer_contact_allowed=(
                        keyed_uniform(
                            seed,
                            "sequential-contact-permission-v2",
                            observation.customer_id,
                        )
                        < CONTACT_ALLOWED_RATE
                    ),
                    alternate_method_available=(
                        keyed_uniform(
                            seed,
                            "sequential-alternate-available-v2",
                            observation.payment_id,
                        )
                        < ALTERNATE_METHOD_AVAILABLE_RATE
                    ),
                ),
                initial_active_payment_link=(
                    keyed_uniform(
                        seed,
                        "sequential-existing-link-v2",
                        observation.payment_id,
                    )
                    < INITIAL_ACTIVE_LINK_RATE
                ),
            )
        )
    return tuple(templates)


def initial_episode_state(template: SequentialEpisodeTemplate) -> SequentialEpisodeState:
    return SequentialEpisodeState(
        episode_id=template.episode_id,
        decision_index=1,
        decision_at=template.observation.observed_at,
        horizon_at=template.observation.observed_at + timedelta(hours=EPISODE_HORIZON_HOURS),
        intervention_count=0,
        retry_count=0,
        contact_count=0,
        payment_link_count=int(template.initial_active_payment_link),
        method_update_count=0,
        alternate_method_count=0,
        active_payment_link=template.initial_active_payment_link,
        method_update_requested=False,
        alternate_method_used=False,
    )


def generate_sequential_candidates(
    template: SequentialEpisodeTemplate,
    state: SequentialEpisodeState,
    costs: SimulationCosts,
) -> tuple[SequentialCandidate, ...]:
    if state.termination is not EpisodeTermination.ACTIVE:
        return ()
    if state.intervention_count >= MAX_AUTONOMOUS_INTERVENTIONS:
        return ()
    candidates: list[SequentialCandidate] = []
    for spec in SEQUENTIAL_CANDIDATE_SPECS:
        action_type = spec.action_type
        contact = action_type in CONTACT_ACTIONS
        retry = action_type in RETRY_ACTIONS
        if retry and state.retry_count >= MAX_RETRIES:
            continue
        if contact and (
            state.contact_count >= MAX_CONTACTS or not template.operational.customer_contact_allowed
        ):
            continue
        if action_type is ActionType.CREATE_PAYMENT_LINK and state.active_payment_link:
            continue
        if (
            action_type is ActionType.REQUEST_PAYMENT_METHOD_UPDATE
            and state.method_update_requested
        ):
            continue
        if action_type is ActionType.OFFER_ALTERNATE_METHOD and (
            state.alternate_method_used or not template.operational.alternate_method_available
        ):
            continue
        delay = spec.delay_hours
        quiet_delay = False
        if contact and _is_quiet(state.decision_at):
            delay = _hours_until_contact_window(state.decision_at)
            quiet_delay = True
        if (
            action_type is ActionType.RETRY_NOW
            and state.last_action_type in {ActionType.RETRY_NOW.value, ActionType.RETRY_LATER.value}
            and state.last_action_executed_at is not None
            and _hours_between(state.decision_at, state.last_action_executed_at)
            < MIN_RETRY_INTERVAL_HOURS
        ):
            continue
        execute_at = state.decision_at + timedelta(hours=delay)
        if execute_at > state.horizon_at:
            continue
        observation_window = (
            RETRY_OBSERVATION_WINDOW_HOURS if retry else CONTACT_OBSERVATION_WINDOW_HOURS
        )
        action = RecoveryAction(
            action_id=_action_id(state, spec.label),
            action_type=action_type,
            execute_at=execute_at,
            scheduled_delay_hours=delay,
            attempt_number=state.retry_count + 1 if retry else 0,
            intervention_cost_minor=_intervention_cost(action_type, costs),
            friction_cost_minor=(
                costs.retry_friction_minor * (state.retry_count + 1)
                if retry
                else _contact_friction(costs, state.contact_count + 1)
                if contact
                else 0
            ),
        )
        candidates.append(
            SequentialCandidate(
                label=spec.label,
                recovery_action=action,
                is_customer_contact=contact,
                requests_method_change=action_type in METHOD_CHANGE_ACTIONS,
                observation_window_hours=observation_window,
                quiet_hours_delay_applied=quiet_delay,
            )
        )
    return tuple(candidates)


def advance_episode_state(
    template: SequentialEpisodeTemplate,
    state: SequentialEpisodeState,
    candidate: SequentialCandidate,
    outcome: SequentialActionOutcome,
) -> SequentialEpisodeState:
    if state.termination is not EpisodeTermination.ACTIVE:
        raise ValueError("cannot advance a terminated episode")
    if outcome.episode_id != state.episode_id or outcome.decision_index != state.decision_index:
        raise ValueError("action outcome does not belong to current decision")
    action_type = candidate.recovery_action.action_type
    retry = action_type in RETRY_ACTIONS
    contact = action_type in CONTACT_ACTIONS
    intervention_count = state.intervention_count + 1
    if outcome.recovered:
        return state.model_copy(
            update={
                "intervention_count": intervention_count,
                "retry_count": state.retry_count + int(retry),
                "contact_count": state.contact_count + int(contact),
                "payment_link_count": state.payment_link_count
                + int(action_type is ActionType.CREATE_PAYMENT_LINK),
                "method_update_count": state.method_update_count
                + int(action_type is ActionType.REQUEST_PAYMENT_METHOD_UPDATE),
                "alternate_method_count": state.alternate_method_count
                + int(action_type is ActionType.OFFER_ALTERNATE_METHOD),
                "active_payment_link": state.active_payment_link
                or action_type is ActionType.CREATE_PAYMENT_LINK,
                "method_update_requested": state.method_update_requested
                or action_type is ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
                "alternate_method_used": state.alternate_method_used
                or action_type is ActionType.OFFER_ALTERNATE_METHOD,
                "last_action_label": candidate.label,
                "last_action_type": action_type.value,
                "last_action_executed_at": candidate.recovery_action.execute_at,
                "recovered": True,
                "recovered_at": outcome.executed_at,
                "recovery_action_id": outcome.action_id,
                "recovery_action_label": candidate.label,
                "recovery_decision_index": state.decision_index,
                "termination": EpisodeTermination.RECOVERED,
            }
        )
    next_at = min(
        state.horizon_at,
        candidate.recovery_action.execute_at + timedelta(hours=candidate.observation_window_hours),
    )
    termination = (
        EpisodeTermination.MAX_INTERVENTIONS
        if intervention_count >= MAX_AUTONOMOUS_INTERVENTIONS
        else EpisodeTermination.HORIZON_EXHAUSTED
        if next_at >= state.horizon_at
        else EpisodeTermination.ACTIVE
    )
    return state.model_copy(
        update={
            "decision_index": min(4, state.decision_index + 1),
            "decision_at": next_at,
            "intervention_count": intervention_count,
            "retry_count": state.retry_count + int(retry),
            "contact_count": state.contact_count + int(contact),
            "payment_link_count": state.payment_link_count
            + int(action_type is ActionType.CREATE_PAYMENT_LINK),
            "method_update_count": state.method_update_count
            + int(action_type is ActionType.REQUEST_PAYMENT_METHOD_UPDATE),
            "alternate_method_count": state.alternate_method_count
            + int(action_type is ActionType.OFFER_ALTERNATE_METHOD),
            "active_payment_link": state.active_payment_link
            or action_type is ActionType.CREATE_PAYMENT_LINK,
            "method_update_requested": state.method_update_requested
            or action_type is ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
            "alternate_method_used": state.alternate_method_used
            or action_type is ActionType.OFFER_ALTERNATE_METHOD,
            "last_action_label": candidate.label,
            "last_action_type": action_type.value,
            "last_action_executed_at": candidate.recovery_action.execute_at,
            "previous_intervention_result": PreviousInterventionResult.FAILED,
            "termination": termination,
        }
    )


def _opaque_episode_id(seed: int, payment_id: str) -> str:
    digest = hashlib.sha256(f"sequential-v2|{seed}|{payment_id}".encode()).hexdigest()
    return f"seq_{digest[:32]}"


def _action_id(state: SequentialEpisodeState, label: str) -> str:
    payload = f"{state.episode_id}|{state.decision_index}|{state.decision_at.isoformat()}|{label}"
    return f"sact_{hashlib.sha256(payload.encode()).hexdigest()[:28]}"


def _is_quiet(timestamp: datetime) -> bool:
    return timestamp.hour >= QUIET_HOURS_START_UTC or timestamp.hour < QUIET_HOURS_END_UTC


def _hours_until_contact_window(timestamp: datetime) -> float:
    target = timestamp.replace(hour=QUIET_HOURS_END_UTC, minute=0, second=0, microsecond=0)
    if timestamp.hour >= QUIET_HOURS_START_UTC:
        target += timedelta(days=1)
    return max(0.0, (target - timestamp).total_seconds() / 3600.0)


def _hours_between(later: datetime, earlier: datetime) -> float:
    return max(0.0, (later - earlier).total_seconds() / 3600.0)


def _contact_friction(costs: SimulationCosts, contact_number: int) -> int:
    growth = Decimal(str(costs.friction_growth)) ** max(0, contact_number - 1)
    value = (Decimal(costs.base_contact_friction_minor) * growth).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return min(costs.max_contact_friction_minor, int(value))


def _intervention_cost(action_type: ActionType, costs: SimulationCosts) -> int:
    return {
        ActionType.RETRY_NOW: costs.retry_operational_minor,
        ActionType.RETRY_LATER: costs.retry_operational_minor,
        ActionType.SEND_NUDGE: costs.message_minor,
        ActionType.CREATE_PAYMENT_LINK: costs.payment_link_minor,
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE: costs.method_update_minor,
        ActionType.OFFER_ALTERNATE_METHOD: costs.alternate_method_minor,
    }[action_type]
