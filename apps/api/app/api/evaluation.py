import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])

ARTIFACT_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "artifacts"
    / "policy"
    / "recoveriq-sequential-v2"
    / "validation-evaluation-v2.json"
)


@router.get("/summary")
async def get_evaluation_summary() -> dict[str, Any]:
    if not ARTIFACT_PATH.exists():
        raise HTTPException(status_code=404, detail="Evaluation artifact unavailable")
    try:
        with open(ARTIFACT_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Invalid evaluation artifact") from e

    fh_eval = data.get("full_horizon_evaluation")
    if not fh_eval or "strategies" not in fh_eval:
        raise HTTPException(status_code=500, detail="Invalid evaluation artifact schema")

    strategies = fh_eval["strategies"]

    # 1. RecoveryIQ
    riq = strategies.get("recoveriq_sequential_erv_v2")
    if not riq:
        raise HTTPException(status_code=500, detail="Missing RecoveryIQ evaluation")

    # 2. Primary Baseline
    baseline = strategies.get("reminder_retry_workflow")
    if not baseline:
        raise HTTPException(status_code=500, detail="Missing baseline evaluation")

    return {
        "evidence_type": "SIMULATED",
        "evaluation_name": "Sequential ERV V2",
        "episodes": riq.get("episodes", 0),
        "recoveryiq": {
            "recovered_count": riq.get("recovered_episodes", 0),
            "recovery_rate": riq.get("recovery_rate", 0.0),
            "simulated_net_value_minor": riq.get("simulated_net_recovery_value_minor", 0),
            "contacts": riq.get("customer_contacts", 0),
            "retries": riq.get("retry_count", 0),
            "human_reviews": riq.get("human_reviews", 0),
            "policy_violations": riq.get("policy_violations", 0),
        },
        "primary_baseline": {
            "name": "Reminder + Retry",
            "recovered_count": baseline.get("recovered_episodes", 0),
            "recovery_rate": baseline.get("recovery_rate", 0.0),
            "simulated_net_value_minor": baseline.get("simulated_net_recovery_value_minor", 0),
            "contacts": baseline.get("customer_contacts", 0),
            "retries": baseline.get("retry_count", 0),
            "human_reviews": baseline.get("human_reviews", 0),
            "policy_violations": baseline.get("policy_violations", 0),
        },
        "incremental": {
            "recovery_rate_pp": (riq.get("recovery_rate", 0.0) - baseline.get("recovery_rate", 0.0))
            * 100,
            "simulated_net_value_minor": riq.get("simulated_net_recovery_value_minor", 0)
            - baseline.get("simulated_net_recovery_value_minor", 0),
        },
        "strategies": [
            {
                "id": k,
                "name": format_strategy_name(k),
                "recovered_count": v.get("recovered_episodes"),
                "recovery_rate": v.get("recovery_rate"),
                "simulated_net_value_minor": v.get("simulated_net_recovery_value_minor"),
                "contacts": v.get("customer_contacts"),
                "retries": v.get("retry_count"),
                "human_reviews": v.get("human_reviews"),
                "policy_violations": v.get("policy_violations"),
            }
            for k, v in strategies.items()
        ],
    }


def format_strategy_name(name: str) -> str:
    mapping = {
        "best_global_sequential": "Best Global Action",
        "fixed_retry_workflow": "Fixed Retry",
        "greedy_hidden_oracle": "Hidden Oracle",
        "recoveriq_sequential_erv_v2": "RecoveryIQ V2",
        "reminder_retry_workflow": "Reminder + Retry",
        "sequential_probability_policy": "Probability Policy",
        "simple_sequential_observable_rule": "Simple Observable Rule",
    }
    return mapping.get(name, name.replace("_", " ").title())
