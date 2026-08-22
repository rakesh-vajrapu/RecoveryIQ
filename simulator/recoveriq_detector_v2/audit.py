from __future__ import annotations

from datetime import timedelta
from typing import Any

from recoveriq_detector.audit import incident_observability_rows
from recoveriq_detector_v2.config import HIGH_EVIDENCE_RULE, HighEvidenceRule
from recoveriq_simulator.ground_truth import GeneratedScenario


def v2_incident_opportunity_rows(
    scenario: GeneratedScenario,
    high_rule: HighEvidenceRule = HIGH_EVIDENCE_RULE,
) -> list[dict[str, Any]]:
    original = {str(row["incident_id"]): row for row in incident_observability_rows(scenario)}
    rows: list[dict[str, Any]] = []
    for incident in scenario.ground_truth.incidents:
        base = original[incident.incident_id]
        horizon_end = min(
            incident.end_at,
            incident.start_at + timedelta(hours=high_rule.first_horizon_hours),
        )
        first_horizon_attempts = sum(
            1
            for event in scenario.public.observable_events
            if event.payment_method == incident.payment_method
            and event.issuer == incident.issuer
            and incident.start_at <= event.observed_at <= horizon_end
        )
        rows.append(
            {
                **base,
                "attempts_first_24h": first_horizon_attempts,
                "high_evidence": (
                    first_horizon_attempts >= high_rule.min_attempts_first_horizon
                    and int(base["prior_baseline_attempts"])
                    >= high_rule.min_prior_baseline_attempts
                ),
            }
        )
    return rows
