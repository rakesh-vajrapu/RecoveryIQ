"""Distribution, causal-integrity, and leakage-oriented simulator analysis."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from statistics import fmean, median
from typing import Any

import numpy as np

from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import ActionType, TrueFailureCause
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.observation import ObservedPaymentEvent
from recoveriq_simulator.results import BenchmarkResult, PaymentPolicyOutcome


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _numeric_distribution(values: Iterable[float]) -> dict[str, float | None]:
    array = np.asarray(tuple(values), dtype=float)
    if not len(array):
        return {key: None for key in ("minimum", "p25", "median", "mean", "p75", "p95", "maximum")}
    return {
        "minimum": float(array.min()),
        "p25": float(np.quantile(array, 0.25)),
        "median": float(np.median(array)),
        "mean": float(array.mean()),
        "p75": float(np.quantile(array, 0.75)),
        "p95": float(np.quantile(array, 0.95)),
        "maximum": float(array.max()),
    }


def _event_failure_rates(
    events: tuple[ObservedPaymentEvent, ...], key: Callable[[ObservedPaymentEvent], str]
) -> dict[str, dict[str, float | int]]:
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for event in events:
        group = key(event)
        counts[group][0] += 1
        counts[group][1] += int(event.success)
    return {
        group: {
            "attempts": values[0],
            "failures": values[0] - values[1],
            "failure_rate": (values[0] - values[1]) / values[0],
        }
        for group, values in sorted(counts.items())
    }


def _failure_reason_audit(
    scenario: GeneratedScenario, benchmark: BenchmarkResult | None
) -> dict[str, Any]:
    truth = scenario.ground_truth.payments
    observations = scenario.public.failure_observations
    contingency: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    cause_counts: Counter[str] = Counter()
    joint: Counter[tuple[str, str]] = Counter()
    for observation in observations:
        cause = truth[observation.payment_id].true_failure_cause
        if cause is None:
            continue
        reason = observation.failure_reason.value
        contingency[reason][cause.value] += 1
        reason_counts[reason] += 1
        cause_counts[cause.value] += 1
        joint[(reason, cause.value)] += 1

    conditional: dict[str, Any] = {}
    maximum_posterior = 0.0
    for reason, cause_counter in sorted(contingency.items()):
        total = sum(cause_counter.values())
        probabilities = {cause: count / total for cause, count in sorted(cause_counter.items())}
        entropy = -sum(
            probability * math.log(probability) for probability in probabilities.values()
        )
        normalized_entropy = (
            entropy / math.log(len(probabilities)) if len(probabilities) > 1 else 0.0
        )
        posterior = max(probabilities.values(), default=0.0)
        maximum_posterior = max(maximum_posterior, posterior)
        conditional[reason] = {
            "count": total,
            "hidden_cause_counts": dict(sorted(cause_counter.items())),
            "hidden_cause_probabilities": probabilities,
            "normalized_entropy": normalized_entropy,
            "maximum_posterior": posterior,
        }

    total = sum(joint.values())
    mutual_information = 0.0
    for (reason, hidden_cause_name), count in joint.items():
        p_joint = count / total
        mutual_information += p_joint * math.log(
            p_joint / ((reason_counts[reason] / total) * (cause_counts[hidden_cause_name] / total))
        )
    reason_entropy = (
        -sum((count / total) * math.log(count / total) for count in reason_counts.values())
        if total
        else 0.0
    )
    cause_entropy = (
        -sum((count / total) * math.log(count / total) for count in cause_counts.values())
        if total
        else 0.0
    )
    denominator = min(reason_entropy, cause_entropy)

    action_success_by_reason: dict[str, Any] = {}
    if benchmark is not None:
        reason_by_payment = {
            observation.payment_id: observation.failure_reason.value for observation in observations
        }
        for evaluation in benchmark.policies:
            groups: dict[str, list[PaymentPolicyOutcome]] = defaultdict(list)
            for outcome in evaluation.outcomes:
                groups[reason_by_payment[outcome.payment_id]].append(outcome)
            action_success_by_reason[evaluation.policy_name] = {
                reason: {
                    "payments": len(outcomes),
                    "recovered": sum(outcome.recovered for outcome in outcomes),
                    "recovery_rate": sum(outcome.recovered for outcome in outcomes) / len(outcomes),
                    "recovery_action_counts": dict(
                        sorted(
                            Counter(
                                outcome.recovery_action.value
                                for outcome in outcomes
                                if outcome.recovery_action is not None
                            ).items()
                        )
                    ),
                }
                for reason, outcomes in sorted(groups.items())
            }

    return {
        "conditional_hidden_cause_by_observable_reason": conditional,
        "maximum_hidden_cause_posterior": maximum_posterior,
        "mutual_information_nats": mutual_information,
        "normalized_mutual_information": mutual_information / denominator if denominator else 0.0,
        "action_success_by_observable_reason": action_success_by_reason,
    }


def _nudge_effect_analysis(
    scenario: GeneratedScenario, benchmark: BenchmarkResult | None
) -> dict[str, Any]:
    if benchmark is None:
        return {}
    evaluations = {evaluation.policy_name: evaluation for evaluation in benchmark.policies}
    fixed = {outcome.payment_id: outcome for outcome in evaluations["fixed_retry"].outcomes}
    reminder = {
        outcome.payment_id: outcome for outcome in evaluations["reminder_then_fixed_retry"].outcomes
    }
    observations = {
        observation.payment_id: observation for observation in scenario.public.failure_observations
    }

    def summarize(payment_ids: list[str]) -> dict[str, float | int | None]:
        exposed = [payment_id for payment_id in payment_ids if reminder[payment_id].nudge_count]
        direct = [
            payment_id
            for payment_id in exposed
            if reminder[payment_id].recovery_action is ActionType.SEND_NUDGE
        ]
        fixed_recovered = sum(fixed[payment_id].recovered for payment_id in exposed)
        reminder_recovered = sum(reminder[payment_id].recovered for payment_id in exposed)
        direct_times = [
            value
            for payment_id in direct
            if (value := reminder[payment_id].time_to_recovery_hours) is not None
        ]
        return {
            "exposed": len(exposed),
            "direct_nudge_recoveries": len(direct),
            "direct_nudge_recovery_rate": _rate(len(direct), len(exposed)),
            "fixed_final_recovered": fixed_recovered,
            "reminder_final_recovered": reminder_recovered,
            "fixed_final_recovery_rate": _rate(fixed_recovered, len(exposed)),
            "reminder_final_recovery_rate": _rate(reminder_recovered, len(exposed)),
            "final_recovery_lift": _rate(reminder_recovered - fixed_recovered, len(exposed)),
            "mean_direct_recovery_time_hours": fmean(direct_times) if direct_times else None,
        }

    by_cause: dict[str, Any] = {}
    for cause in TrueFailureCause:
        ids = [
            payment_id
            for payment_id in reminder
            if scenario.ground_truth.payments[payment_id].true_failure_cause is cause
        ]
        by_cause[cause.value] = summarize(ids)

    during_ids = [
        payment_id
        for payment_id in reminder
        if scenario.ground_truth.payments[payment_id].incident_id is not None
    ]
    during_id_set = set(during_ids)
    outside_ids = [payment_id for payment_id in reminder if payment_id not in during_id_set]
    segments: dict[str, list[str]] = {"LOW": [], "MEDIUM": [], "HIGH": []}
    for payment_id, observation in observations.items():
        responsiveness = scenario.ground_truth.customers[
            observation.customer_id
        ].nudge_responsiveness
        segment = (
            "LOW" if responsiveness < 1 / 3 else "HIGH" if responsiveness >= 2 / 3 else "MEDIUM"
        )
        segments[segment].append(payment_id)

    return {
        "overall": summarize(list(reminder)),
        "by_hidden_failure_family": by_cause,
        "during_incident": summarize(during_ids),
        "outside_incident": summarize(outside_ids),
        "by_responsiveness_segment": {segment: summarize(ids) for segment, ids in segments.items()},
    }


def build_analysis(
    scenario: GeneratedScenario,
    config: SimulatorConfig,
    benchmark: BenchmarkResult | None = None,
) -> dict[str, Any]:
    payments = scenario.public.payments
    events = scenario.public.observable_events
    observations = scenario.public.failure_observations
    truth = scenario.ground_truth
    failures = len(observations)
    failure_rate = failures / len(payments) if payments else 0.0
    amounts = [payment.amount_minor for payment in payments]
    reason_counts = Counter(observation.failure_reason.value for observation in observations)
    hidden_cause_counts = Counter(
        payment.true_failure_cause.value
        for payment in truth.payments.values()
        if payment.true_failure_cause is not None
    )
    incident_by_id = {incident.incident_id: incident for incident in truth.incidents}
    during = [payment for payment in truth.payments.values() if payment.incident_id is not None]
    outside = [payment for payment in truth.payments.values() if payment.incident_id is None]
    during_failures = sum(not payment.initial_success for payment in during)
    durations = [
        (incident.end_at - incident.start_at).total_seconds() / 3600.0
        for incident in truth.incidents
    ]
    severity_counts = Counter(incident.severity_class.value for incident in truth.incidents)
    severity_payment_groups: dict[str, list[bool]] = defaultdict(list)
    for payment in during:
        if payment.incident_id is not None:
            severity = incident_by_id[payment.incident_id].severity_class.value
            severity_payment_groups[severity].append(payment.initial_success)

    policy_summary: dict[str, Any] = {}
    recovery_by_cause: dict[str, Any] = {}
    action_effectiveness: dict[str, Any] = {}
    if benchmark is not None:
        for evaluation in benchmark.policies:
            policy_summary[evaluation.policy_name] = evaluation.metrics.model_dump(mode="json")
            outcome_by_id = {outcome.payment_id: outcome for outcome in evaluation.outcomes}
            cause_summary: dict[str, Any] = {}
            for cause in TrueFailureCause:
                ids = [
                    payment_id
                    for payment_id, payment_truth in truth.payments.items()
                    if payment_truth.true_failure_cause is cause
                ]
                recovered = sum(outcome_by_id[payment_id].recovered for payment_id in ids)
                cause_summary[cause.value] = {
                    "failed": len(ids),
                    "recovered": recovered,
                    "recovery_rate": _rate(recovered, len(ids)),
                }
            recovery_by_cause[evaluation.policy_name] = cause_summary
            action_effectiveness[evaluation.policy_name] = {
                action: {
                    "executed": count,
                    "recoveries": evaluation.metrics.action_success_counts.get(action, 0),
                    "success_rate": _rate(
                        evaluation.metrics.action_success_counts.get(action, 0), count
                    ),
                }
                for action, count in evaluation.metrics.action_counts.items()
                if action != ActionType.STOP.value
            }

    missing_issuer = sum(event.issuer is None for event in events)
    delayed = sum(event.observed_at > event.occurred_at for event in events)
    unknown = sum(
        observation.failure_reason.value == "UNKNOWN_TRANSIENT_ERROR"
        for observation in observations
    )
    incident_success_by_severity = {
        severity: {
            "attempts": len(successes),
            "success_rate": fmean(float(success) for success in successes),
        }
        for severity, successes in sorted(severity_payment_groups.items())
    }
    dominant_reason_share = max(reason_counts.values(), default=0) / failures if failures else 0.0
    during_rate = fmean(float(payment.initial_success) for payment in during) if during else None
    outside_rate = fmean(float(payment.initial_success) for payment in outside) if outside else None
    expected_during_rate = (
        fmean(payment.initial_success_probability for payment in during) if during else None
    )
    expected_outside_rate = (
        fmean(payment.initial_success_probability for payment in outside) if outside else None
    )
    reason_audit = _failure_reason_audit(scenario, benchmark)

    checks = {
        "payment_values_positive": bool(amounts and min(amounts) > 0),
        "has_successes": failures < len(payments),
        "has_failures": failures > 0,
        "failure_rate_plausible": config.plausible_failure_rate_min
        <= failure_rate
        <= config.plausible_failure_rate_max,
        "incidents_have_valid_windows": all(
            incident.start_at < incident.end_at for incident in truth.incidents
        ),
        "incident_deterioration_measurable": expected_during_rate is not None
        and expected_outside_rate is not None
        and expected_during_rate < expected_outside_rate,
        "failure_reason_not_dominant": dominant_reason_share < 0.75,
        "failure_reason_information_not_total": reason_audit["normalized_mutual_information"]
        < 0.80,
        "not_every_failure_recovers": all(
            evaluation.metrics.recovered_payment_count < failures
            for evaluation in benchmark.policies
        )
        if benchmark is not None
        else True,
    }
    return {
        "configuration": {
            "simulator_version": config.simulator_version,
            "seed": config.seed,
            "cost_regime": config.cost_regime.value,
            "incident_severity_profile": config.incident_severity_profile.value,
            "nudge_effect_strength": config.nudge_effect_strength,
        },
        "payment_attempt_count": len(payments),
        "failure_count": failures,
        "failure_rate": failure_rate,
        "payments_per_merchant": dict(
            sorted(Counter(payment.merchant_id for payment in payments).items())
        ),
        "subscription_value_minor": _numeric_distribution(
            subscription.amount_minor for subscription in scenario.public.subscriptions
        ),
        "payment_amount_minor": _numeric_distribution(amounts),
        "payment_method_counts": dict(
            sorted(Counter(event.payment_method.value for event in events).items())
        ),
        "issuer_counts": dict(
            sorted(Counter(event.issuer or "MISSING" for event in events).items())
        ),
        "failure_rates_by_method": _event_failure_rates(
            events, lambda event: event.payment_method.value
        ),
        "failure_rates_by_issuer": _event_failure_rates(
            events, lambda event: event.issuer or "MISSING"
        ),
        "observable_failure_reason_counts": dict(sorted(reason_counts.items())),
        "hidden_failure_family_counts": dict(sorted(hidden_cause_counts.items())),
        "customer_prior_attempt_distribution": _numeric_distribution(
            observation.customer_prior_attempts for observation in observations
        ),
        "missing_data_rates": {
            "issuer": _rate(missing_issuer, len(events)),
            "unknown_failure_reason": _rate(unknown, failures),
            "delayed_status_event": _rate(delayed, len(events)),
        },
        "incident_coverage": {
            "incident_count": len(truth.incidents),
            "count_by_severity": dict(sorted(severity_counts.items())),
            "duration_hours": {
                "minimum": min(durations) if durations else None,
                "mean": fmean(durations) if durations else None,
                "median": median(durations) if durations else None,
                "maximum": max(durations) if durations else None,
            },
            "attempts_during_incidents": len(during),
            "attempt_proportion": _rate(len(during), len(payments)),
            "failures_during_incidents": during_failures,
            "failure_proportion": _rate(during_failures, failures),
            "success_rate_inside": during_rate,
            "success_rate_outside": outside_rate,
            "expected_success_rate_inside": expected_during_rate,
            "expected_success_rate_outside": expected_outside_rate,
            "success_rate_by_severity": incident_success_by_severity,
            "incidents_by_method_issuer": dict(
                sorted(
                    Counter(
                        f"{incident.payment_method.value}/{incident.issuer}"
                        for incident in truth.incidents
                    ).items()
                )
            ),
        },
        "recovery_by_hidden_failure_family": recovery_by_cause,
        "action_effectiveness": action_effectiveness,
        "nudge_effect_analysis": _nudge_effect_analysis(scenario, benchmark),
        "failure_reason_predictive_triviality": reason_audit,
        "baseline_results": policy_summary,
        "sanity_checks": checks,
    }


def assert_sane(analysis: dict[str, Any]) -> None:
    failed = [name for name, passed in analysis["sanity_checks"].items() if not bool(passed)]
    if failed:
        raise ValueError(f"simulator sanity checks failed: {', '.join(failed)}")


def render_quality_markdown(analysis: dict[str, Any]) -> str:
    incident = analysis["incident_coverage"]
    triviality = analysis["failure_reason_predictive_triviality"]
    lines = [
        "# RecoverIQ Simulator Quality Report",
        "",
        f"Simulator version: `{analysis['configuration']['simulator_version']}`  ",
        f"Seed: `{analysis['configuration']['seed']}`  ",
        f"Attempts: {analysis['payment_attempt_count']:,}  ",
        f"Failures: {analysis['failure_count']:,} ({analysis['failure_rate']:.2%})",
        "",
        "## Incident coverage",
        "",
        f"Count by severity: `{incident['count_by_severity']}`  ",
        f"Attempt coverage: {incident['attempt_proportion']:.2%}  ",
        f"Failure coverage: {incident['failure_proportion']:.2%}  ",
        f"Success inside incidents: {incident['success_rate_inside']:.2%}  ",
        f"Success outside incidents: {incident['success_rate_outside']:.2%}",
        "",
        "## Baselines",
        "",
        "| Policy | Recovery rate | Gross (minor) | Net (minor) | Retries | Contacts |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for policy, metrics in analysis["baseline_results"].items():
        lines.append(
            f"| {policy} | {metrics['recovery_rate']:.2%} | "
            f"{metrics['gross_recovered_amount_minor']:,} | "
            f"{metrics['net_recovered_value_minor']:,} | {metrics['retry_count']:,} | "
            f"{metrics['customer_contact_count']:,} |"
        )
    lines.extend(
        [
            "",
            "## Leakage and triviality",
            "",
            f"Maximum P(hidden cause | observable reason): "
            f"{triviality['maximum_hidden_cause_posterior']:.2%}  ",
            f"Normalized mutual information: {triviality['normalized_mutual_information']:.3f}",
            "",
            "## Sanity checks",
            "",
            *(
                f"- {name}: {'PASS' if passed else 'FAIL'}"
                for name, passed in analysis["sanity_checks"].items()
            ),
            "",
            "All values and costs are synthetic evaluation assumptions.",
        ]
    )
    return "\n".join(lines) + "\n"
