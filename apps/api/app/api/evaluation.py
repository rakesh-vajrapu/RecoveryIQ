import json
import uuid
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException

from app.api.razorpay import DecisionResponse, RecoveryCaseResponse

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])

ARTIFACTS_DIR = (
    Path(__file__).parent.parent.parent.parent.parent
    / "artifacts"
    / "policy"
    / "recoveriq-sequential-v2"
)
ARTIFACT_PATH = ARTIFACTS_DIR / "validation-evaluation-v2.json"


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
            "id": "recoveriq_sequential_erv_v2",
            "name": "RecoveryIQ V2",
            "recovered_count": riq.get("recovered_episodes", 0),
            "recovery_rate": riq.get("recovery_rate", 0.0),
            "simulated_net_value_minor": riq.get("simulated_net_recovery_value_minor", 0),
            "contacts": riq.get("customer_contacts", 0),
            "retries": riq.get("retry_count", 0),
            "human_reviews": riq.get("human_reviews", 0),
            "policy_violations": riq.get("policy_violations", 0),
        },
        "primary_baseline": {
            "id": "reminder_retry_workflow",
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
        "best_global_sequential": "Best Global Sequential",
        "fixed_retry_workflow": "Fixed Retry",
        "greedy_hidden_oracle": "Hidden Oracle",
        "random_sequential": "Random Search",
        "recoveriq_sequential_erv_v2": "RecoveryIQ V2",
        "reminder_retry_workflow": "Reminder + Retry",
        "sequential_probability_policy": "Probability Policy",
        "simple_sequential_observable_rule": "Simple Observable Rule",
    }
    return mapping.get(name, name.replace("_", " ").title())


@router.get("/replay/presets")
async def get_replay_presets() -> list[dict[str, str]]:
    return [
        {"id": "successful-adaptive-trace-v2", "name": "Successful Adaptive Recovery"},
        {"id": "bounded-failure-trace-v2", "name": "Bounded Safe Failure"},
    ]


@router.get("/replay/{preset_id}")
async def get_replay_trace(preset_id: str) -> dict[str, Any]:
    allowed_presets = {
        "successful-adaptive-trace-v2",
        "bounded-failure-trace-v2",
    }
    if preset_id not in allowed_presets:
        raise HTTPException(status_code=404, detail="Preset not found")

    trace_path = ARTIFACTS_DIR / f"{preset_id}.json"
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail="Trace artifact unavailable")

    try:
        with open(trace_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Invalid trace artifact") from e


@router.get("/simulated-decision-example", response_model=RecoveryCaseResponse)
async def get_simulated_decision_example() -> Any:
    trace_path = ARTIFACT_PATH.parent / "successful-adaptive-trace-v2.json"
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail="Simulated trace unavailable")
    try:
        with open(trace_path, encoding="utf-8") as f:
            trace_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Invalid simulated trace") from e

    initial = trace_data.get("initial_failure", {})
    decisions = trace_data.get("decisions", [])
    first_decision = decisions[0] if decisions else {}
    candidates = first_decision.get("candidates", [])

    amount = initial.get("amount_minor", 0)

    # pyrefly: ignore [bad-assignment]
    selected_action: str = first_decision.get("selected_action") or "UNKNOWN"
    # pyrefly: ignore [bad-assignment]
    policy_checks: dict[str, Any] = first_decision.get("policy_checks") or {}
    reason: str = policy_checks.get("reason") or "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV"

    decision_res = DecisionResponse(
        id=uuid.uuid4(),
        kind="ACTION",
        selected_action=selected_action,
        reason=reason,
        model_version="2.0.0",
        policy_version="2.0.0",
        feature_schema_version="2.0",
        context_metadata={
            "candidates": candidates,
            "policy_checks": first_decision.get("policy_checks", {}),
            "observable_context": first_decision.get("observable_context", {}),
        },
    )

    return {
        "id": uuid.uuid4(),
        "status": "RECOVERED",
        "correlation_id": uuid.uuid4(),
        "amount_minor": amount,
        "currency": "INR",
        "subscription_status": "active",
        "source": "SIMULATED",
        "synthetic": True,
        "failure_type": initial.get("failure_reason", "CUSTOMER_ACTION_REQUIRED"),
        "payment_method": initial.get("payment_method", "CARD"),
        "failure_description": "Simulated evaluation trajectory",
        "decisions": [decision_res.model_dump()],
        "plans": [],
        "executions": [],
        "outcomes": [],
        "attribution": None,
    }


DIAGNOSTIC_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "artifacts"
    / "evaluation"
    / "multi-action-counterfactual-v3"
    / "multi-action-counterfactual-summary-v3.json"
)


@router.get("/action-advantage")
async def get_action_advantage_diagnostic() -> dict[str, Any]:
    if not DIAGNOSTIC_PATH.exists():
        raise HTTPException(status_code=404, detail="Diagnostic artifact unavailable")
    try:
        with open(DIAGNOSTIC_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Invalid diagnostic artifact") from e

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Invalid diagnostic artifact format")
    return cast(dict[str, Any], data)
