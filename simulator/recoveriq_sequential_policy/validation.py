from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from recoveriq_ml.artifacts import sha256_file, write_json, write_markdown
from recoveriq_sequential.config import (
    OVERALL_FINAL_SEEDS,
    SEQUENTIAL_POLICY_VALIDATION_SEEDS,
)
from recoveriq_sequential_policy.development import load_frozen_baselines
from recoveriq_sequential_policy.evaluation import (
    RECOVERIQ,
    REMINDER_RETRY,
    SIMPLE_RULE,
    evaluate_policy_seed_group,
)
from recoveriq_sequential_policy.models import FrozenSequentialPolicy


def run_policy_validation_once(
    *,
    artifact_root: Path,
    model_root: Path,
    calibration_root: Path,
) -> dict[str, Any]:
    output = artifact_root / "validation-evaluation-v2.json"
    attempt_path = artifact_root / "validation-attempt-v2.json"
    if output.exists() or attempt_path.exists():
        raise FileExistsError("Sequential Policy V2 validation was already attempted")
    policy = FrozenSequentialPolicy.model_validate_json(
        (artifact_root / "recoveriq-sequential-policy-v2.json").read_text(encoding="utf-8")
    )
    _assert_frozen_policy(policy, artifact_root, model_root, calibration_root)
    baselines = load_frozen_baselines(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    write_json(
        attempt_path,
        {
            "artifact_type": "sequential_policy_v2_registered_validation_attempt",
            "policy_config_hash": policy.config_hash,
            "validation_seeds": SEQUENTIAL_POLICY_VALIDATION_SEEDS,
            "status": "STARTED",
        },
    )
    started = perf_counter()
    evaluation, records, traces = evaluate_policy_seed_group(
        seeds=SEQUENTIAL_POLICY_VALIDATION_SEEDS,
        baselines=baselines,
        normalized_margin_threshold=policy.normalized_erv_margin_threshold,
        model_root=model_root,
        calibration_root=calibration_root,
    )
    records.to_parquet(artifact_root / "validation-episode-records-v2.parquet", index=False)
    write_json(
        artifact_root / "successful-adaptive-trace-v2.json",
        traces["successful_adaptive_trace"],
    )
    write_json(
        artifact_root / "bounded-failure-trace-v2.json",
        traces["bounded_failure_trace"],
    )
    claims = _validation_claims(evaluation)
    report = {
        "artifact_type": "sequential_policy_v2_one_time_validation",
        "policy_version": policy.policy_version,
        "policy_config_hash": policy.config_hash,
        "validation_seeds": SEQUENTIAL_POLICY_VALIDATION_SEEDS,
        "validation_run_count": 1,
        "overall_final_seeds": OVERALL_FINAL_SEEDS,
        "final_seeds_untouched": True,
        "full_horizon_evaluation": evaluation,
        "preregistered_validation_claims": claims,
        "runtime_seconds": perf_counter() - started,
    }
    write_json(output, report)
    write_markdown(artifact_root / "validation-report-v2.md", render_validation_report(report))
    write_json(
        attempt_path,
        {
            "artifact_type": "sequential_policy_v2_registered_validation_attempt",
            "policy_config_hash": policy.config_hash,
            "validation_seeds": SEQUENTIAL_POLICY_VALIDATION_SEEDS,
            "status": "COMPLETED",
            "result_sha256": sha256_file(output),
            "safety_claim": claims["safety"]["status"],
        },
    )
    validated = policy.model_dump(mode="json")
    validated["validation_status"] = (
        "EXECUTED_ONCE_PASS" if claims["safety"]["status"] == "PASS" else "EXECUTED_ONCE_FAIL"
    )
    write_json(artifact_root / "recoveriq-sequential-policy-v2.json", validated)
    return report


def _assert_frozen_policy(
    policy: FrozenSequentialPolicy,
    artifact_root: Path,
    model_root: Path,
    calibration_root: Path,
) -> None:
    baseline_path = artifact_root / policy.baseline_artifact
    if sha256_file(baseline_path) != policy.baseline_sha256:
        raise RuntimeError("sequential baseline artifact changed after freeze")
    model: dict[str, Any] = json.loads(
        (model_root / "model-manifest-v2.json").read_text(encoding="utf-8")
    )
    calibration: dict[str, Any] = json.loads(
        (calibration_root / "calibration-manifest-v2.json").read_text(encoding="utf-8")
    )
    if model["model_sha256"]["lightgbm"] != policy.model_sha256:
        raise RuntimeError("frozen Model V2 hash does not match policy")
    if calibration["calibration_mappings"]["lightgbm"]["sha256"] != policy.calibration_sha256:
        raise RuntimeError("frozen calibration hash does not match policy")
    if policy.validation_seeds != SEQUENTIAL_POLICY_VALIDATION_SEEDS:
        raise RuntimeError("policy validation seed protocol changed after freeze")


def _validation_claims(evaluation: dict[str, Any]) -> dict[str, Any]:
    metrics = evaluation["strategies"]
    lifts = evaluation["recoveriq_paired_lifts"]
    primary = metrics[RECOVERIQ]
    reminder = lifts[REMINDER_RETRY]["aggregate"]
    simple = lifts[SIMPLE_RULE]["aggregate"]
    recovery_mean = reminder["recovery_rate_difference"]["mean"]
    net_mean = reminder["net_value_difference_minor"]["mean"]
    net_low = reminder["net_value_difference_minor"]["ci95_low"]
    safety_pass = primary["policy_violations"] == 0
    recovery_pass = recovery_mean > 0 and net_mean > 0
    strong_pass = net_low is not None and net_low > 0
    personalization_pass = safety_pass and (
        simple["recovery_rate_difference"]["mean"] > 0
        or simple["net_value_difference_minor"]["mean"] > 0
    )
    primary_efficiency = primary["friction_efficiency"]
    reminder_efficiency = metrics[REMINDER_RETRY]["friction_efficiency"]
    friction_pass = primary["simulated_net_recovery_value_minor"] >= metrics[REMINDER_RETRY][
        "simulated_net_recovery_value_minor"
    ] and (
        primary["retry_count"] < metrics[REMINDER_RETRY]["retry_count"]
        or primary["customer_contacts"] < metrics[REMINDER_RETRY]["customer_contacts"]
    )
    return {
        "safety": {
            "status": "PASS" if safety_pass else "FAIL",
            "evidence": primary["policy_violations"],
        },
        "recovery": {
            "status": "PASS" if recovery_pass else "FAIL",
            "paired_mean_recovery_rate_difference": recovery_mean,
            "paired_mean_net_value_difference_minor": net_mean,
        },
        "strong_recovery": {
            "status": "PASS" if strong_pass else "FAIL",
            "paired_net_value_ci95_low_minor": net_low,
        },
        "ml_personalization": {
            "status": "PASS" if personalization_pass else "FAIL",
            "versus_simple_rule": simple,
        },
        "friction_efficiency": {
            "status": "PASS" if friction_pass else "FAIL",
            "recoveriq": primary_efficiency,
            "reminder_retry": reminder_efficiency,
        },
    }


def render_validation_report(report: dict[str, Any]) -> str:
    evaluation = report["full_horizon_evaluation"]
    metrics = evaluation["strategies"]
    lines = [
        "# RecoverIQ Sequential Policy V2 One-Time Validation",
        "",
        "All values are deterministic synthetic simulator evidence, not production revenue.",
        "",
        "| Strategy | Recovery rate | Gross minor | Net minor | Retries | Contacts | Violations |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in metrics.items():
        lines.append(
            f"| {name} | {row['recovery_rate']:.4f} | "
            f"{row['simulated_gross_recovered_amount_minor']} | "
            f"{row['simulated_net_recovery_value_minor']} | {row['retry_count']} | "
            f"{row['customer_contacts']} | {row['policy_violations']} |"
        )
    lines.extend(("", "## Preregistered claims", ""))
    for name, claim in report["preregistered_validation_claims"].items():
        lines.append(f"- {name}: **{claim['status']}**")
    lines.extend(
        (
            "",
            "The overall-final Buildathon seeds were not executed.",
            "Detector V2 remained advisory and absent from primary Model V2.",
        )
    )
    return "\n".join(lines)
