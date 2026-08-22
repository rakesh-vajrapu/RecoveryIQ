from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import fmean, median
from typing import Any

from recoveriq_detector_v2.audit import v2_incident_opportunity_rows
from recoveriq_detector_v2.config import DetectorV2Config
from recoveriq_detector_v2.models import DegradationEpisodeV2, ScopeLevel
from recoveriq_simulator.enums import TrueFailureCause
from recoveriq_simulator.ground_truth import GeneratedScenario

_EXPECTED_REASON = {
    TrueFailureCause.LIQUIDITY_SHORTFALL: "INSUFFICIENT_FUNDS",
    TrueFailureCause.ISSUER_DEGRADATION: "ISSUER_UNAVAILABLE",
    TrueFailureCause.AUTHENTICATION_FRICTION: "AUTHENTICATION_FAILURE",
    TrueFailureCause.INVALID_INSTRUMENT: "INSTRUMENT_EXPIRED",
    TrueFailureCause.INACTIVE_MANDATE: "MANDATE_INACTIVE",
    TrueFailureCause.NETWORK_INSTABILITY: "TEMPORARY_NETWORK_ERROR",
    TrueFailureCause.CUSTOMER_CONFIRMATION: "CUSTOMER_ACTION_REQUIRED",
    TrueFailureCause.UNKNOWN_TEMPORARY: "UNKNOWN_TRANSIENT_ERROR",
}


def evaluate_v2_scenario(
    scenario: GeneratedScenario,
    episodes: tuple[DegradationEpisodeV2, ...],
    config: DetectorV2Config,
) -> dict[str, Any]:
    issuer_episodes = [episode for episode in episodes if episode.scope.level is ScopeLevel.ISSUER]
    opportunities = {str(row["incident_id"]): row for row in v2_incident_opportunity_rows(scenario)}
    watch_matches, unused_watch = _match_tier(
        scenario,
        issuer_episodes,
        lambda episode: episode.watch_at,
    )
    confirmed_indexes = [
        index for index, episode in enumerate(issuer_episodes) if episode.confirmed_at is not None
    ]
    confirmed_subset = [issuer_episodes[index] for index in confirmed_indexes]
    confirmed_matches_subset, unused_confirmed_subset = _match_tier(
        scenario,
        confirmed_subset,
        lambda episode: episode.confirmed_at,
    )
    confirmed_matches = {
        incident_id: confirmed_indexes[index]
        for incident_id, index in confirmed_matches_subset.items()
    }
    unused_confirmed = {confirmed_indexes[index] for index in unused_confirmed_subset}

    hidden_rows: list[dict[str, Any]] = []
    for hidden in sorted(scenario.ground_truth.incidents, key=lambda item: item.start_at):
        opportunity = opportunities[hidden.incident_id]
        attempt_times = sorted(
            event.observed_at
            for event in scenario.public.observable_events
            if event.payment_method == hidden.payment_method
            and event.issuer == hidden.issuer
            and hidden.start_at <= event.observed_at <= hidden.end_at
        )
        first_time = attempt_times[0] if attempt_times else None
        watch_nth = _nth(attempt_times, config.watch_min_events)
        confirm_nth = _nth(attempt_times, config.confirmed_min_events)
        watch = (
            issuer_episodes[watch_matches[hidden.incident_id]]
            if hidden.incident_id in watch_matches
            else None
        )
        confirmed = (
            issuer_episodes[confirmed_matches[hidden.incident_id]]
            if hidden.incident_id in confirmed_matches
            else None
        )
        top_reason = (
            confirmed.failure_distribution.dominant_shifts[0]
            if confirmed is not None and confirmed.failure_distribution.dominant_shifts
            else None
        )
        hidden_rows.append(
            {
                "seed": scenario.ground_truth.seed,
                "incident_id": hidden.incident_id,
                "hidden_severity": hidden.severity_class.value,
                "traffic_volume_bucket": _volume_bucket(int(opportunity["observable_attempts"])),
                "observable_attempts": opportunity["observable_attempts"],
                "eligible": opportunity["eligible"],
                "high_evidence": opportunity["high_evidence"],
                "watch_detected": watch is not None,
                "confirmed_detected": confirmed is not None,
                "watch_delay_minutes": _delay(watch.watch_at if watch else None, hidden.start_at),
                "confirmed_delay_minutes": _delay(
                    confirmed.confirmed_at if confirmed else None,
                    hidden.start_at,
                ),
                "watch_delay_after_first_minutes": _between(
                    watch.watch_at if watch else None,
                    first_time,
                ),
                "confirmed_delay_after_first_minutes": _between(
                    confirmed.confirmed_at if confirmed else None,
                    first_time,
                ),
                "watch_delay_after_minimum_minutes": _between(
                    watch.watch_at if watch else None,
                    watch_nth,
                ),
                "confirmed_delay_after_minimum_minutes": _between(
                    confirmed.confirmed_at if confirmed else None,
                    confirm_nth,
                ),
                "watch_to_confirmed_minutes": (
                    (confirmed.confirmed_at - confirmed.watch_at).total_seconds() / 60
                    if confirmed is not None and confirmed.confirmed_at is not None
                    else None
                ),
                "resolution_delay_minutes": (
                    (confirmed.resolved_at - hidden.end_at).total_seconds() / 60
                    if confirmed is not None and confirmed.resolved_at is not None
                    else None
                ),
                "predicted_severity": confirmed.current_severity.value if confirmed else None,
                "expected_reason": _EXPECTED_REASON[hidden.dominant_failure_cause],
                "top_reason": top_reason.reason if top_reason else None,
                "top_reason_support": top_reason.support_count if top_reason else None,
                "top_reason_match": (
                    top_reason.reason == _EXPECTED_REASON[hidden.dominant_failure_cause]
                    if top_reason
                    else None
                ),
            }
        )

    horizon_end = max(event.observed_at for event in scenario.public.observable_events)
    false_confirmed = [
        _false_confirmed_row(scenario, issuer_episodes[index], horizon_end)
        for index in sorted(unused_confirmed)
    ]
    observed_scope_count = len(
        {
            (event.payment_method.value, event.issuer)
            for event in scenario.public.observable_events
            if event.issuer is not None
        }
    )
    horizon_days = (
        horizon_end - min(event.observed_at for event in scenario.public.observable_events)
    ).total_seconds() / 86_400
    return {
        "seed": scenario.ground_truth.seed,
        "scope_days": observed_scope_count * horizon_days,
        "hidden_incidents": hidden_rows,
        "issuer_watch_episode_count": len(issuer_episodes),
        "issuer_confirmed_episode_count": len(confirmed_subset),
        "matched_watch_count": len(watch_matches),
        "matched_confirmed_count": len(confirmed_matches),
        "false_watch_indexes": sorted(unused_watch),
        "false_confirmed": false_confirmed,
        "broad_watch_episode_count": sum(
            episode.scope.level is not ScopeLevel.ISSUER for episode in episodes
        ),
    }


def aggregate_v2_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    hidden = [row for evaluation in evaluations for row in evaluation["hidden_incidents"]]
    scope_days = sum(float(evaluation["scope_days"]) for evaluation in evaluations)
    watch_count = sum(int(evaluation["issuer_watch_episode_count"]) for evaluation in evaluations)
    confirmed_count = sum(
        int(evaluation["issuer_confirmed_episode_count"]) for evaluation in evaluations
    )
    matched_watch = sum(int(evaluation["matched_watch_count"]) for evaluation in evaluations)
    matched_confirmed = sum(
        int(evaluation["matched_confirmed_count"]) for evaluation in evaluations
    )
    false_confirmed = [row for evaluation in evaluations for row in evaluation["false_confirmed"]]
    watch = _tier_metrics(hidden, "watch", watch_count, matched_watch, scope_days)
    confirmed = _tier_metrics(
        hidden,
        "confirmed",
        confirmed_count,
        matched_confirmed,
        scope_days,
    )
    confirmed["watch_to_confirmed_delay_minutes"] = _summary(
        [
            float(row["watch_to_confirmed_minutes"])
            for row in hidden
            if row["confirmed_detected"] and row["watch_to_confirmed_minutes"] is not None
        ]
    )
    confirmed["resolution_delay_minutes"] = _summary(
        [
            float(row["resolution_delay_minutes"])
            for row in hidden
            if row["confirmed_detected"] and row["resolution_delay_minutes"] is not None
        ]
    )
    confirmed["false_confirmed_failed_payment_exposure"] = sum(
        int(row["failed_payments_during_episode"]) for row in false_confirmed
    )
    reason_rows = [row for row in hidden if row["top_reason_match"] is not None]
    support = [float(row["top_reason_support"]) for row in reason_rows]
    return {
        "seed_count": len(evaluations),
        "all_incident_count": len(hidden),
        "eligible_incident_count": sum(bool(row["eligible"]) for row in hidden),
        "high_evidence_incident_count": sum(bool(row["high_evidence"]) for row in hidden),
        "watch": watch,
        "confirmed": confirmed,
        "root_cause_evidence": {
            "confirmed_matches": matched_confirmed,
            "supported_top_reason_count": len(reason_rows),
            "coverage": _ratio(len(reason_rows), matched_confirmed),
            "top_1_agreement": _ratio(
                sum(bool(row["top_reason_match"]) for row in reason_rows),
                len(reason_rows),
            ),
            "support_distribution": _summary(support),
        },
        "false_confirmed": false_confirmed,
        "broad_watch_episode_count": sum(
            int(evaluation["broad_watch_episode_count"]) for evaluation in evaluations
        ),
        "per_seed": evaluations,
    }


def _tier_metrics(
    hidden: list[dict[str, Any]],
    tier: str,
    episode_count: int,
    matched_count: int,
    scope_days: float,
) -> dict[str, Any]:
    detected_key = f"{tier}_detected"
    delay_key = f"{tier}_delay_minutes"
    eligible = [row for row in hidden if row["eligible"]]
    high = [row for row in hidden if row["high_evidence"]]
    detected = [row for row in hidden if row[detected_key]]
    return {
        "episode_count": episode_count,
        "matched_count": matched_count,
        "all_incident_recall": _ratio(len(detected), len(hidden)),
        "eligible_incident_recall": _ratio(
            sum(bool(row[detected_key]) for row in eligible),
            len(eligible),
        ),
        "high_evidence_incident_recall": _ratio(
            sum(bool(row[detected_key]) for row in high),
            len(high),
        ),
        "episode_precision": _ratio(matched_count, episode_count),
        "false_episode_count": episode_count - matched_count,
        "false_episodes_per_scope_day": _ratio(episode_count - matched_count, scope_days),
        "detection_delay_minutes": _summary(
            [float(row[delay_key]) for row in detected if row[delay_key] is not None]
        ),
        "delay_after_first_event_minutes": _summary(
            [
                float(row[f"{tier}_delay_after_first_minutes"])
                for row in detected
                if row[f"{tier}_delay_after_first_minutes"] is not None
            ]
        ),
        "delay_after_minimum_evidence_minutes": _summary(
            [
                float(row[f"{tier}_delay_after_minimum_minutes"])
                for row in detected
                if row[f"{tier}_delay_after_minimum_minutes"] is not None
            ]
        ),
        "recall_by_hidden_severity": _grouped_recall(hidden, detected_key, "hidden_severity"),
        "recall_by_traffic_volume": _grouped_recall(
            hidden,
            detected_key,
            "traffic_volume_bucket",
        ),
    }


def _match_tier(
    scenario: GeneratedScenario,
    episodes: list[DegradationEpisodeV2],
    timestamp_getter: Any,
) -> tuple[dict[str, int], set[int]]:
    unused = set(range(len(episodes)))
    matches: dict[str, int] = {}
    for hidden in sorted(scenario.ground_truth.incidents, key=lambda item: item.start_at):
        grace = hidden.end_at + timedelta(minutes=30)
        candidates: list[int] = []
        for index in unused:
            episode = episodes[index]
            timestamp = timestamp_getter(episode)
            if timestamp is None:
                continue
            if (
                episode.scope.payment_method == hidden.payment_method.value
                and episode.scope.issuer == hidden.issuer
                and hidden.start_at <= timestamp <= grace
            ):
                candidates.append(index)
        if candidates:
            chosen = min(candidates, key=lambda index: timestamp_getter(episodes[index]))
            matches[hidden.incident_id] = chosen
            unused.remove(chosen)
    return matches, unused


def _false_confirmed_row(
    scenario: GeneratedScenario,
    episode: DegradationEpisodeV2,
    horizon_end: datetime,
) -> dict[str, Any]:
    assert episode.confirmed_at is not None
    end = episode.resolved_at or horizon_end
    failures = sum(
        1
        for event in scenario.public.observable_events
        if event.payment_method.value == episode.scope.payment_method
        and event.issuer == episode.scope.issuer
        and episode.confirmed_at <= event.observed_at <= end
        and not event.success
    )
    return {
        "seed": scenario.ground_truth.seed,
        "incident_id": episode.incident_id,
        "scope": episode.scope.model_dump(mode="json"),
        "confirmed_at": episode.confirmed_at.isoformat(),
        "resolved_at": episode.resolved_at.isoformat() if episode.resolved_at else None,
        "failed_payments_during_episode": failures,
        "confirmation_rule": episode.confirmation_rule,
    }


def _grouped_recall(
    rows: list[dict[str, Any]],
    detected_key: str,
    group_key: str,
) -> dict[str, dict[str, int | float | None]]:
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[group_key])].append(row)
    return {
        group: {
            "incidents": len(items),
            "detected": sum(bool(item[detected_key]) for item in items),
            "recall": _ratio(sum(bool(item[detected_key]) for item in items), len(items)),
        }
        for group, items in sorted(groups.items())
    }


def _nth(values: list[datetime], number: int) -> datetime | None:
    return values[number - 1] if len(values) >= number else None


def _delay(timestamp: datetime | None, onset: datetime) -> float | None:
    return (timestamp - onset).total_seconds() / 60 if timestamp is not None else None


def _between(later: datetime | None, earlier: datetime | None) -> float | None:
    return (later - earlier).total_seconds() / 60 if later and earlier else None


def _volume_bucket(attempts: int) -> str:
    if attempts <= 2:
        return "0-2"
    if attempts <= 4:
        return "3-4"
    if attempts <= 9:
        return "5-9"
    return "10+"


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def _summary(values: list[float]) -> dict[str, int | float | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "p90": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "mean": fmean(values),
        "median": median(values),
        "p90": ordered[round((len(ordered) - 1) * 0.90)],
    }
