from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import fmean, median
from typing import Any

from recoveriq_detector.audit import incident_observability_rows
from recoveriq_detector.config import ELIGIBILITY_RULE, EligibilityRule
from recoveriq_detector.models import PredictedIncident, ScopeLevel
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


def evaluate_scenario(
    scenario: GeneratedScenario,
    predicted: tuple[PredictedIncident, ...],
    rule: EligibilityRule = ELIGIBILITY_RULE,
) -> dict[str, Any]:
    audit_by_id = {
        str(row["incident_id"]): row for row in incident_observability_rows(scenario, rule)
    }
    issuer_predictions = [
        incident for incident in predicted if incident.scope.level is ScopeLevel.ISSUER
    ]
    broad_predictions = len(predicted) - len(issuer_predictions)
    unused = set(range(len(issuer_predictions)))
    hidden_rows: list[dict[str, Any]] = []
    matched_prediction_indexes: set[int] = set()

    for hidden in sorted(scenario.ground_truth.incidents, key=lambda item: item.start_at):
        grace_end = hidden.end_at + timedelta(minutes=30)
        candidates = [
            index
            for index in unused
            if issuer_predictions[index].scope.payment_method == hidden.payment_method.value
            and issuer_predictions[index].scope.issuer == hidden.issuer
            and hidden.start_at <= issuer_predictions[index].detected_at <= grace_end
            and (issuer_predictions[index].resolved_at or grace_end) >= hidden.start_at
        ]
        match_index = (
            min(candidates, key=lambda index: issuer_predictions[index].detected_at)
            if candidates
            else None
        )
        match = issuer_predictions[match_index] if match_index is not None else None
        if match_index is not None:
            unused.remove(match_index)
            matched_prediction_indexes.add(match_index)

        audit = audit_by_id[hidden.incident_id]
        attempt_times = sorted(
            event.observed_at
            for event in scenario.public.observable_events
            if event.payment_method == hidden.payment_method
            and event.issuer == hidden.issuer
            and hidden.start_at <= event.observed_at <= hidden.end_at
        )
        nth_time = (
            attempt_times[rule.min_incident_attempts - 1]
            if len(attempt_times) >= rule.min_incident_attempts
            else None
        )
        dominant_reason = (
            match.dominant_failure_shifts[0].reason
            if match is not None and match.dominant_failure_shifts
            else None
        )
        hidden_rows.append(
            {
                "seed": scenario.ground_truth.seed,
                "incident_id": hidden.incident_id,
                "payment_method": hidden.payment_method.value,
                "issuer": hidden.issuer,
                "hidden_severity": hidden.severity_class.value,
                "traffic_volume_bucket": _volume_bucket(int(audit["observable_attempts"])),
                "observable_attempts": audit["observable_attempts"],
                "prior_baseline_attempts": audit["prior_baseline_attempts"],
                "eligible": audit["eligible"],
                "detected": match is not None,
                "predicted_incident_id": match.incident_id if match else None,
                "detection_delay_minutes": (
                    (match.detected_at - hidden.start_at).total_seconds() / 60 if match else None
                ),
                "time_to_nth_attempt_minutes": (
                    (nth_time - hidden.start_at).total_seconds() / 60 if nth_time else None
                ),
                "delay_after_nth_attempt_minutes": (
                    (match.detected_at - nth_time).total_seconds() / 60
                    if match is not None and nth_time is not None
                    else None
                ),
                "resolution_delay_minutes": (
                    (match.resolved_at - hidden.end_at).total_seconds() / 60
                    if match is not None and match.resolved_at is not None
                    else None
                ),
                "predicted_severity": match.current_severity.value if match else None,
                "dominant_failure_reason": dominant_reason,
                "expected_dominant_reason": _EXPECTED_REASON[hidden.dominant_failure_cause],
                "dominant_reason_match": (
                    dominant_reason == _EXPECTED_REASON[hidden.dominant_failure_cause]
                    if dominant_reason is not None
                    else None
                ),
            }
        )

    false_rows = [
        _false_positive_row(scenario, issuer_predictions[index]) for index in sorted(unused)
    ]
    events = scenario.public.observable_events
    observed_scope_count = len(
        {(event.payment_method.value, event.issuer) for event in events if event.issuer is not None}
    )
    horizon_days = (
        (
            max(event.observed_at for event in events) - min(event.observed_at for event in events)
        ).total_seconds()
        / 86_400
        if events
        else 0.0
    )
    return {
        "seed": scenario.ground_truth.seed,
        "scope_days": observed_scope_count * horizon_days,
        "broad_scope_prediction_count": broad_predictions,
        "hidden_incidents": hidden_rows,
        "predicted_issuer_incident_count": len(issuer_predictions),
        "matched_prediction_count": len(matched_prediction_indexes),
        "false_positive_incidents": false_rows,
    }


def aggregate_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    hidden = [row for evaluation in evaluations for row in evaluation["hidden_incidents"]]
    false_rows = [
        row for evaluation in evaluations for row in evaluation["false_positive_incidents"]
    ]
    predicted_count = sum(
        int(evaluation["predicted_issuer_incident_count"]) for evaluation in evaluations
    )
    matched_count = sum(int(evaluation["matched_prediction_count"]) for evaluation in evaluations)
    scope_days = sum(float(evaluation["scope_days"]) for evaluation in evaluations)
    eligible = [row for row in hidden if row["eligible"]]
    detected = [row for row in hidden if row["detected"]]
    eligible_detected = [row for row in eligible if row["detected"]]
    raw_delays = [float(row["detection_delay_minutes"]) for row in detected]
    evidence_delays = [
        float(row["delay_after_nth_attempt_minutes"])
        for row in eligible_detected
        if row["delay_after_nth_attempt_minutes"] is not None
    ]
    resolution_delays = [
        float(row["resolution_delay_minutes"])
        for row in detected
        if row["resolution_delay_minutes"] is not None
    ]
    reason_rows = [row for row in detected if row["dominant_reason_match"] is not None]
    return {
        "seed_count": len(evaluations),
        "all_incident_count": len(hidden),
        "eligible_incident_count": len(eligible),
        "predicted_issuer_incident_count": predicted_count,
        "broad_scope_prediction_count": sum(
            int(evaluation["broad_scope_prediction_count"]) for evaluation in evaluations
        ),
        "matched_prediction_count": matched_count,
        "all_incident_recall": _ratio(len(detected), len(hidden)),
        "eligible_incident_recall": _ratio(len(eligible_detected), len(eligible)),
        "predicted_incident_precision": _ratio(matched_count, predicted_count),
        "false_positive_incident_count": len(false_rows),
        "false_incidents_per_scope_day": _ratio(len(false_rows), scope_days),
        "detection_delay_minutes": _summary(raw_delays),
        "delay_after_sufficient_evidence_minutes": _summary(evidence_delays),
        "resolution_delay_minutes": _summary(resolution_delays),
        "recall_by_hidden_severity": _grouped_recall(hidden, "hidden_severity"),
        "recall_by_traffic_volume": _grouped_recall(hidden, "traffic_volume_bucket"),
        "severity_confusion_matrix": _severity_confusion(detected),
        "dominant_failure_shift": {
            "detected_incidents": len(detected),
            "incidents_with_supported_shift": len(reason_rows),
            "support_coverage": _ratio(len(reason_rows), len(detected)),
            "top_reason_accuracy_when_supported": _ratio(
                sum(bool(row["dominant_reason_match"]) for row in reason_rows),
                len(reason_rows),
            ),
        },
        "false_positive_causes": dict(Counter(str(row["classification"]) for row in false_rows)),
        "false_positive_incidents": false_rows,
        "per_seed": evaluations,
    }


def _false_positive_row(
    scenario: GeneratedScenario,
    incident: PredictedIncident,
) -> dict[str, Any]:
    start = incident.detected_at - timedelta(minutes=incident.evidence_window_minutes)
    events = [
        event
        for event in scenario.public.observable_events
        if event.payment_method.value == incident.scope.payment_method
        and event.issuer == incident.scope.issuer
        and start <= event.observed_at <= incident.detected_at
    ]
    duration_minutes = (
        (incident.resolved_at - incident.detected_at).total_seconds() / 60
        if incident.resolved_at is not None
        else None
    )
    if incident.current_attempts < 12:
        classification = "sparse_sample"
    elif incident.baseline_attempts < 100:
        classification = "baseline_instability"
    elif incident.baseline_success_rate < 0.80:
        classification = "naturally_lower_performing_scope"
    elif duration_minutes is not None and duration_minutes <= 60:
        classification = "one_off_burst"
    else:
        classification = "random_fluctuation"
    return {
        "seed": scenario.ground_truth.seed,
        "predicted_incident_id": incident.incident_id,
        "scope": incident.scope.model_dump(mode="json"),
        "detected_at": incident.detected_at.isoformat(),
        "attempts_in_evidence_window": len(events),
        "baseline_success_rate": incident.baseline_success_rate,
        "current_success_rate": incident.current_success_rate,
        "classification": classification,
    }


def _grouped_recall(
    rows: list[dict[str, Any]], key: str
) -> dict[str, dict[str, float | int | None]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return {
        group: {
            "incidents": len(group_rows),
            "detected": sum(bool(row["detected"]) for row in group_rows),
            "recall": _ratio(sum(bool(row["detected"]) for row in group_rows), len(group_rows)),
        }
        for group, group_rows in sorted(grouped.items())
    }


def _severity_confusion(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    matrix: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        matrix[str(row["hidden_severity"])][str(row["predicted_severity"])] += 1
    return {hidden: dict(predicted) for hidden, predicted in sorted(matrix.items())}


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


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "p90": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "mean": fmean(ordered),
        "median": median(ordered),
        "p90": ordered[round((len(ordered) - 1) * 0.90)],
    }
