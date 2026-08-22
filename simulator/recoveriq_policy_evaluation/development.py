from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from recoveriq_ml.artifacts import sha256_file, write_json, write_markdown
from recoveriq_policy import POLICY_SCHEMA_VERSION, POLICY_VERSION
from recoveriq_policy.config import (
    CANDIDATE_LABELS,
    MARGIN_THRESHOLD_CANDIDATES,
    MAX_CONTACT_COUNT,
    MAX_RETRY_COUNT,
    MIN_ACTION_TRAINING_SUPPORT,
    MIN_AUTONOMOUS_COVERAGE,
    MIN_CALIBRATION_BIN_SUPPORT,
    MIN_RETRY_INTERVAL_HOURS,
    OVERALL_FINAL_SEEDS,
    POLICY_DEVELOPMENT_SEEDS,
    POLICY_VALIDATION_SEEDS,
    PRIMARY_COST_REGIME,
    QUIET_HOURS_END_UTC,
    QUIET_HOURS_START_UTC,
)
from recoveriq_policy.models import FrozenBaselineArtifact, FrozenPolicyArtifact
from recoveriq_policy_evaluation.metrics import strategy_metrics
from recoveriq_policy_evaluation.strategy import STRATEGIES, execute_strategies


def freeze_development_policy(
    *,
    artifact_root: Path,
    model_root: Path,
    calibration_root: Path,
) -> dict[str, Any]:
    output = artifact_root / "development-policy-v1.json"
    policy_path = artifact_root / "recoveriq-policy-v1.json"
    if output.exists() or policy_path.exists():
        raise FileExistsError("Policy V1 is already frozen; refusing redevelopment")
    candidates_path = artifact_root / "development-candidates-v1.parquet"
    baselines_path = artifact_root / "development-baselines-v1.json"
    if not candidates_path.exists() or not baselines_path.exists():
        raise FileNotFoundError("run the development personalization audit first")
    started = perf_counter()
    frame = pd.read_parquet(candidates_path)
    baselines = FrozenBaselineArtifact.model_validate_json(
        baselines_path.read_text(encoding="utf-8")
    )
    base_records, _, _ = execute_strategies(
        frame,
        baselines=baselines,
        policy_config_hash="DEVELOPMENT_THRESHOLD_CANDIDATE",
        normalized_margin_threshold=Decimal("0"),
        strategy_names=("recoveriq_erv_policy_v1",),
    )
    sweep: list[dict[str, Any]] = []
    for threshold in MARGIN_THRESHOLD_CANDIDATES:
        records = _apply_margin_threshold(base_records, float(threshold))
        metrics = strategy_metrics(records)
        coverage = float(metrics["autonomous_decisions"]) / len(records)
        sweep.append(
            {
                "normalized_margin_threshold": threshold,
                "autonomous_coverage": coverage,
                "mean_net_recovery_value_minor_per_decision": float(
                    metrics["simulated_net_recovery_value_minor"]
                )
                / len(records),
                "metrics": metrics,
                "constraints_pass": (
                    metrics["deterministic_policy_violations"] == 0
                    and coverage >= MIN_AUTONOMOUS_COVERAGE
                ),
            }
        )
    eligible = [row for row in sweep if row["constraints_pass"]]
    if not eligible:
        raise RuntimeError("no registered margin threshold satisfies development constraints")
    best_value = max(float(row["mean_net_recovery_value_minor_per_decision"]) for row in eligible)
    tied = [
        row
        for row in eligible
        if best_value - float(row["mean_net_recovery_value_minor_per_decision"]) <= 1.0
    ]
    selected = min(
        tied,
        key=lambda row: (
            -float(row["autonomous_coverage"]),
            float(row["normalized_margin_threshold"]),
        ),
    )
    selected_threshold = Decimal(str(selected["normalized_margin_threshold"]))
    model_manifest = json.loads((model_root / "model-manifest-v1.json").read_text(encoding="utf-8"))
    calibration_manifest = json.loads(
        (calibration_root / "calibration-manifest-v1.json").read_text(encoding="utf-8")
    )
    config_payload = {
        "policy_version": POLICY_VERSION,
        "policy_schema_version": POLICY_SCHEMA_VERSION,
        "recovery_model_version": model_manifest["model_version"],
        "recovery_model_sha256": model_manifest["model_sha256"]["lightgbm"],
        "feature_schema_hash": model_manifest["feature_schema_hash"],
        "calibration_method": calibration_manifest["selected_method"],
        "calibration_sha256": calibration_manifest["calibration_mappings"]["lightgbm"]["sha256"],
        "development_seeds": POLICY_DEVELOPMENT_SEEDS,
        "validation_seeds": POLICY_VALIDATION_SEEDS,
        "final_seeds": OVERALL_FINAL_SEEDS,
        "cost_regime": PRIMARY_COST_REGIME.value,
        "candidate_labels": CANDIDATE_LABELS,
        "max_retry_count": MAX_RETRY_COUNT,
        "max_contact_count": MAX_CONTACT_COUNT,
        "min_retry_interval_hours": MIN_RETRY_INTERVAL_HOURS,
        "quiet_hours_start_utc": QUIET_HOURS_START_UTC,
        "quiet_hours_end_utc": QUIET_HOURS_END_UTC,
        "min_action_training_support": MIN_ACTION_TRAINING_SUPPORT,
        "min_calibration_bin_support": MIN_CALIBRATION_BIN_SUPPORT,
        "normalized_erv_margin_threshold": str(selected_threshold),
        "baseline_artifact_sha256": sha256_file(baselines_path),
    }
    config_hash = hashlib.sha256(
        json.dumps(config_payload, sort_keys=True, separators=(",", ":"), default=list).encode()
    ).hexdigest()
    policy_payload = {
        **config_payload,
        "normalized_erv_margin_threshold": selected_threshold,
    }
    policy = FrozenPolicyArtifact(
        **policy_payload,
        config_hash=config_hash,
        validation_status="PENDING_AT_FREEZE",
    )
    all_records, trace, block_rows = execute_strategies(
        frame,
        baselines=baselines,
        policy_config_hash=config_hash,
        normalized_margin_threshold=selected_threshold,
        strategy_names=STRATEGIES,
        capture_trace=True,
    )
    all_records.to_parquet(artifact_root / "development-policy-records-v1.parquet", index=False)
    strategy_results = {
        name: strategy_metrics(all_records[all_records["strategy"] == name]) for name in STRATEGIES
    }
    report = {
        "phase": "policy_development_and_freeze",
        "selection_rule": (
            "maximum mean net value subject to zero violations and >=70% autonomous "
            "coverage; within one minor choose greater coverage then smaller threshold"
        ),
        "threshold_sweep": sweep,
        "selected_normalized_margin_threshold": float(selected_threshold),
        "frozen_policy_config_hash": config_hash,
        "strategy_results": strategy_results,
        "blocked_rule_evidence_count": len(block_rows),
        "example_trace_available": trace is not None,
        "runtime_seconds": perf_counter() - started,
    }
    write_json(policy_path, policy.model_dump(mode="json"))
    write_json(output, report)
    if trace is not None:
        write_json(artifact_root / "development-decision-trace-v1.json", trace)
    write_markdown(
        artifact_root / "development-policy-v1.md",
        render_development_policy(report),
    )
    return report


def _apply_margin_threshold(records: pd.DataFrame, threshold: float) -> pd.DataFrame:
    adjusted = records.copy()
    review = (
        (adjusted["decision_kind"] == "ACTION")
        & adjusted["normalized_erv_margin"].notna()
        & (adjusted["normalized_erv_margin"] < threshold)
    )
    adjusted.loc[review, "decision_kind"] = "HUMAN_REVIEW"
    adjusted.loc[review, "selected_action"] = "HUMAN_REVIEW"
    adjusted.loc[review, "reason"] = "normalized ERV decision margin is below the frozen threshold"
    adjusted.loc[review, "review_reasons"] = '["LOW_DECISION_MARGIN"]'
    adjusted.loc[review, "recovered"] = False
    adjusted.loc[review, "gross_recovered_minor"] = 0
    adjusted.loc[review, "intervention_cost_minor"] = 4_000
    adjusted.loc[review, "friction_cost_minor"] = 0
    adjusted.loc[review, "net_recovery_value_minor"] = -4_000
    for column in (
        "retry_count",
        "customer_contacts",
        "payment_links",
        "method_updates",
        "alternate_methods",
        "autonomous_decisions",
        "action_count",
        "top_1_oracle_agreement",
        "top_2_oracle_coverage",
    ):
        adjusted.loc[review, column] = 0
    adjusted.loc[review, "human_reviews"] = 1
    adjusted.loc[review, "stop_count"] = 0
    adjusted.loc[review, "recovery_time_hours"] = None
    adjusted.loc[review, "selected_oracle_erv_minor"] = 0
    adjusted.loc[review, "oracle_erv_regret_minor"] = adjusted.loc[review, "oracle_best_erv_minor"]
    return adjusted


def render_development_policy(report: dict[str, Any]) -> str:
    selected = report["selected_normalized_margin_threshold"]
    primary = report["strategy_results"]["recoveriq_erv_policy_v1"]
    return "\n".join(
        (
            "# RecoverIQ Policy V1 Development Freeze",
            "",
            f"Selected normalized ERV margin: `{selected}`",
            f"Config hash: `{report['frozen_policy_config_hash']}`",
            f"Autonomous decisions: {primary['autonomous_decisions']}",
            f"Human review decisions: {primary['human_review_decisions']}",
            f"STOP decisions: {primary['stop_decisions']}",
            f"Simulated net recovery value minor: {primary['simulated_net_recovery_value_minor']}",
            f"Policy violations: {primary['deterministic_policy_violations']}",
            "",
            "Policy configuration is frozen before validation.",
        )
    )
