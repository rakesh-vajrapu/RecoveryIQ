import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/evaluation", tags=["Batch Explorer"])

ARTIFACT_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "artifacts"
    / "policy"
    / "recoveriq-sequential-v2"
    / "validation-evaluation-v2.json"
)


@router.get("/batch-explorer")
async def get_batch_explorer() -> dict[str, Any]:
    """
    Read-only API that serves the portfolio-level intelligence from sealed simulation data.
    """
    if not ARTIFACT_PATH.exists():
        raise HTTPException(status_code=404, detail="Evaluation artifact unavailable")
    try:
        content = ARTIFACT_PATH.read_text(encoding="utf-8")
        import typing

        data = typing.cast(dict[str, Any], json.loads(content))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Invalid evaluation artifact") from e

    fh_eval = data.get("full_horizon_evaluation")
    if not fh_eval or "strategies" not in fh_eval:
        raise HTTPException(status_code=500, detail="Invalid evaluation artifact schema")

    strategies = fh_eval["strategies"]
    riq = strategies.get("recoveriq_sequential_erv_v2")
    if not riq:
        raise HTTPException(status_code=500, detail="Missing RecoveryIQ evaluation")

    baseline = strategies.get("reminder_retry_workflow")
    if not baseline:
        raise HTTPException(status_code=500, detail="Missing baseline evaluation")

    pa = fh_eval.get("personalization_analysis", {})

    return {
        "evidence_type": "SEALED_SIMULATED",
        "artifact_version": data.get("artifact_type", "sequential_policy_v2_one_time_validation"),
        "episodes": riq.get("episodes", 0),
        "portfolio": {
            "recovered_episodes": riq.get("recovered_episodes", 0),
            "recovery_rate": riq.get("recovery_rate", 0.0),
            "simulated_gross_recovered_minor": riq.get("simulated_gross_recovered_amount_minor", 0),
            "simulated_net_recovery_value_minor": riq.get("simulated_net_recovery_value_minor", 0),
            "friction_cost_minor": riq.get("friction_cost_minor", 0),
            "intervention_cost_minor": riq.get("intervention_cost_minor", 0),
            "customer_contacts": riq.get("customer_contacts", 0),
            "retries": riq.get("retry_count", 0),
            "human_reviews": riq.get("human_reviews", 0),
            "stop_outcomes": riq.get("stop_outcomes", 0),
            "policy_violations": riq.get("policy_violations", 0),
            "payment_links": riq.get("payment_links", 0),
            "alternate_methods": riq.get("alternate_methods", 0),
            "method_updates": riq.get("method_updates", 0),
            "mean_actions_per_episode": riq.get("mean_actions_per_episode", 0.0),
            "mean_recovery_time_hours": riq.get("mean_recovery_time_hours", 0.0),
        },
        "cohorts": {
            "failure_reason": pa.get("failure_reason", []),
            "payment_method": pa.get("payment_method", []),
            "amount_bucket": pa.get("amount_bucket", []),
            "prior_success_bucket": pa.get("prior_success_bucket", []),
            "subscription_tenure_bucket": pa.get("subscription_tenure_bucket", []),
        },
        "action_mix": {
            "retries": riq.get("retry_count", 0),
            "payment_links": riq.get("payment_links", 0),
            "alternate_methods": riq.get("alternate_methods", 0),
            "method_updates": riq.get("method_updates", 0),
            "human_reviews": riq.get("human_reviews", 0),
            "stop_outcomes": riq.get("stop_outcomes", 0),
        },
        "intervention_burden": riq.get("friction_efficiency", {}),
        "baseline_comparison": {
            "baseline_name": "Reminder + Retry",
            "baseline_recovery_rate": baseline.get("recovery_rate", 0.0),
            "baseline_net_value_minor": baseline.get("simulated_net_recovery_value_minor", 0),
            "incremental_recovery_rate_pp": (
                riq.get("recovery_rate", 0.0) - baseline.get("recovery_rate", 0.0)
            )
            * 100,
            "incremental_net_value_minor": riq.get("simulated_net_recovery_value_minor", 0)
            - baseline.get("simulated_net_recovery_value_minor", 0),
        },
    }
