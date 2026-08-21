"""Distribution reporting and defensive sanity checks."""

from __future__ import annotations

from collections import Counter
from statistics import fmean
from typing import Any

import numpy as np

from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.results import BenchmarkResult
from recoveriq_simulator.scenario import GeneratedScenario


def build_analysis(
    scenario: GeneratedScenario,
    config: SimulatorConfig,
    benchmark: BenchmarkResult | None = None,
) -> dict[str, Any]:
    payments = scenario.public.payments
    observations = scenario.public.failure_observations
    truth = scenario.ground_truth
    amounts = np.array([payment.amount_minor for payment in payments], dtype=np.int64)
    failures = len(observations)
    failure_rate = failures / len(payments) if payments else 0.0
    method_counts = Counter(
        event.payment_method.value for event in scenario.public.observable_events
    )
    issuer_counts = Counter(
        event.issuer or "MISSING" for event in scenario.public.observable_events
    )
    reason_counts = Counter(observation.failure_reason.value for observation in observations)
    during = [payment for payment in truth.payments.values() if payment.incident_id is not None]
    outside = [payment for payment in truth.payments.values() if payment.incident_id is None]
    during_rate = fmean(float(payment.initial_success) for payment in during) if during else None
    outside_rate = fmean(float(payment.initial_success) for payment in outside) if outside else None
    durations = [
        (incident.end_at - incident.start_at).total_seconds() / 3600.0
        for incident in truth.incidents
    ]
    dominant_reason_share = max(reason_counts.values(), default=0) / failures if failures else 0.0

    policy_summary: dict[str, Any] = {}
    if benchmark is not None:
        for evaluation in benchmark.policies:
            metrics = evaluation.metrics
            policy_summary[evaluation.policy_name] = metrics.model_dump(mode="json")

    checks = {
        "payment_values_positive": bool(len(amounts) and np.all(amounts > 0)),
        "has_successes": failures < len(payments),
        "has_failures": failures > 0,
        "failure_rate_plausible": (
            config.plausible_failure_rate_min <= failure_rate <= config.plausible_failure_rate_max
        ),
        "incidents_have_valid_windows": all(
            incident.start_at < incident.end_at for incident in truth.incidents
        ),
        "incident_deterioration_measurable": (
            during_rate is not None and outside_rate is not None and during_rate < outside_rate
        ),
        "failure_reason_not_dominant": dominant_reason_share < 0.75,
        "not_every_failure_recovers": all(
            evaluation.metrics.recovered_payment_count < failures
            for evaluation in benchmark.policies
        )
        if benchmark is not None
        else True,
    }
    return {
        "payment_amount_minor": {
            "minimum": int(amounts.min()) if len(amounts) else None,
            "p25": int(np.quantile(amounts, 0.25)) if len(amounts) else None,
            "median": int(np.median(amounts)) if len(amounts) else None,
            "p75": int(np.quantile(amounts, 0.75)) if len(amounts) else None,
            "p95": int(np.quantile(amounts, 0.95)) if len(amounts) else None,
            "maximum": int(amounts.max()) if len(amounts) else None,
        },
        "payment_method_counts": dict(sorted(method_counts.items())),
        "failure_reason_counts": dict(sorted(reason_counts.items())),
        "issuer_counts": dict(sorted(issuer_counts.items())),
        "payment_attempt_count": len(payments),
        "failure_count": failures,
        "failure_rate": failure_rate,
        "incident_count": len(truth.incidents),
        "incident_duration_hours": {
            "minimum": min(durations) if durations else None,
            "mean": fmean(durations) if durations else None,
            "maximum": max(durations) if durations else None,
        },
        "success_rate_during_incidents": during_rate,
        "success_rate_outside_incidents": outside_rate,
        "payments_during_incidents": len(during),
        "baseline_results": policy_summary,
        "sanity_checks": checks,
    }


def assert_sane(analysis: dict[str, Any]) -> None:
    failed = [name for name, passed in analysis["sanity_checks"].items() if not bool(passed)]
    if failed:
        raise ValueError(f"simulator sanity checks failed: {', '.join(failed)}")
