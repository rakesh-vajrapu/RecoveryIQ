from __future__ import annotations

from collections import Counter
from datetime import timedelta
from statistics import fmean, median
from typing import Any

from recoveriq_detector.config import ELIGIBILITY_RULE, EligibilityRule
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.scenario import ScenarioGenerator


def incident_observability_rows(
    scenario: GeneratedScenario,
    rule: EligibilityRule = ELIGIBILITY_RULE,
) -> list[dict[str, Any]]:
    events = sorted(
        scenario.public.observable_events,
        key=lambda event: (event.observed_at, event.event_id),
    )
    rows: list[dict[str, Any]] = []
    for incident in scenario.ground_truth.incidents:
        scope_events = [
            event
            for event in events
            if event.payment_method == incident.payment_method and event.issuer == incident.issuer
        ]
        during = [
            event
            for event in scope_events
            if incident.start_at <= event.observed_at <= incident.end_at
        ]
        prior = [
            event
            for event in scope_events
            if incident.start_at - timedelta(days=rule.baseline_lookback_days)
            <= event.observed_at
            < incident.start_at
        ]
        realized_rate = sum(event.success for event in during) / len(during) if during else None
        baseline_rate = sum(event.success for event in prior) / len(prior) if prior else None
        attempts_by_horizon = {
            f"attempts_first_{minutes}m": sum(
                event.observed_at <= incident.start_at + timedelta(minutes=minutes)
                for event in during
            )
            for minutes in (15, 30, 60)
        }
        rows.append(
            {
                "seed": scenario.ground_truth.seed,
                "incident_id": incident.incident_id,
                "payment_method": incident.payment_method.value,
                "issuer": incident.issuer,
                "severity": incident.severity_class.value,
                "duration_hours": (incident.end_at - incident.start_at).total_seconds() / 3600,
                "observable_attempts": len(during),
                **attempts_by_horizon,
                "prior_baseline_attempts": len(prior),
                "baseline_success_rate": baseline_rate,
                "incident_success_rate": realized_rate,
                "realized_rate_drop": (
                    baseline_rate - realized_rate
                    if baseline_rate is not None and realized_rate is not None
                    else None
                ),
                "eligible": (
                    len(during) >= rule.min_incident_attempts
                    and len(prior) >= rule.min_prior_baseline_attempts
                ),
            }
        )
    return rows


def build_development_observability_audit(
    seeds: tuple[int, ...],
    base_config: SimulatorConfig | None = None,
) -> dict[str, Any]:
    config = base_config or SimulatorConfig()
    rows: list[dict[str, Any]] = []
    for seed in seeds:
        scenario = ScenarioGenerator(config.model_copy(update={"seed": seed})).generate()
        rows.extend(incident_observability_rows(scenario))
    fields = (
        "duration_hours",
        "observable_attempts",
        "attempts_first_15m",
        "attempts_first_30m",
        "attempts_first_60m",
        "prior_baseline_attempts",
        "realized_rate_drop",
    )
    return {
        "seed_group": "development",
        "seeds": list(seeds),
        "incident_count": len(rows),
        "eligible_incident_count": sum(bool(row["eligible"]) for row in rows),
        "eligibility_rule": ELIGIBILITY_RULE.model_dump(mode="json"),
        "severity_distribution": dict(Counter(str(row["severity"]) for row in rows)),
        "distributions": {field: _distribution(rows, field) for field in fields},
        "incidents": rows,
    }


def _distribution(rows: list[dict[str, Any]], field: str) -> dict[str, float | int | None]:
    values = sorted(float(row[field]) for row in rows if row[field] is not None)
    if not values:
        return {
            "count": 0,
            "minimum": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "maximum": None,
            "mean": None,
        }

    def percentile(fraction: float) -> float:
        return values[round((len(values) - 1) * fraction)]

    return {
        "count": len(values),
        "minimum": values[0],
        "p25": percentile(0.25),
        "median": median(values),
        "p75": percentile(0.75),
        "p90": percentile(0.90),
        "maximum": values[-1],
        "mean": fmean(values),
        "zero_count": sum(value == 0 for value in values),
    }
