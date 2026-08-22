from __future__ import annotations

import hashlib
import importlib.metadata
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from recoveriq_ml.models import (
    FEATURE_SCHEMA_HASH,
    MODEL_FEATURE_ALLOWLIST,
    LoggedDatasetManifest,
    LoggedRecoveryExample,
)


def ml_artifact_root() -> Path:
    return Path(__file__).resolve().parents[2] / "artifacts" / "ml"


def frozen_detector_v2_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "artifacts"
        / "detector_v2"
        / "degradation-detector-v2.json"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def software_versions() -> dict[str, str]:
    return {
        package: importlib.metadata.version(package)
        for package in (
            "recoveriq-simulator",
            "numpy",
            "pandas",
            "scikit-learn",
            "lightgbm",
            "shap",
            "joblib",
        )
    }


def examples_digest(examples: tuple[LoggedRecoveryExample, ...]) -> str:
    payload = "\n".join(example.model_dump_json(exclude_none=False) for example in examples)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_logged_group(
    root: Path,
    group: str,
    seeds: tuple[int, ...],
    examples: tuple[LoggedRecoveryExample, ...],
) -> LoggedDatasetManifest:
    logged_frame = pd.DataFrame(
        [
            {
                "decision_key": example.decision_key,
                "decision_at": example.decision_at,
                "feature_schema_hash": example.feature_schema_hash,
                "selected_action": example.selected_action.value,
                "delay_hours": example.delay_hours,
                "selection_propensity": example.selection_propensity,
                "candidate_count": example.candidate_count,
                "recovered_within_48h": example.recovered_within_48h,
                "feature_json": json.dumps(
                    example.features.model_features(),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
            for example in examples
        ]
    )
    feature_frame = examples_to_feature_frame(examples)
    logged_path = root / "logged" / f"{group}-logged-v1.parquet"
    features_path = root / "features" / f"{group}-features-v1.parquet"
    logged_path.parent.mkdir(parents=True, exist_ok=True)
    features_path.parent.mkdir(parents=True, exist_ok=True)
    logged_frame.to_parquet(logged_path, index=False)
    feature_frame.to_parquet(features_path, index=False)
    action_counts = (
        logged_frame["selected_action"].value_counts().sort_index().astype(int).to_dict()
        if not logged_frame.empty
        else {}
    )
    positives = int(feature_frame["recovered_within_48h"].sum())
    manifest = LoggedDatasetManifest(
        group=group,
        seeds=seeds,
        example_count=len(examples),
        action_counts=action_counts,
        positive_count=positives,
        positive_rate=positives / len(examples) if examples else None,
        logged_digest=examples_digest(examples),
        software_versions=software_versions(),
    )
    write_json(root / "logged" / f"{group}-manifest-v1.json", manifest.model_dump(mode="json"))
    return manifest


def examples_to_feature_frame(
    examples: tuple[LoggedRecoveryExample, ...],
) -> pd.DataFrame:
    rows = []
    for example in examples:
        features = example.features.model_features()
        if tuple(features) != MODEL_FEATURE_ALLOWLIST:
            raise ValueError("feature snapshot does not match the frozen allowlist")
        rows.append(
            {
                **features,
                "selection_propensity": example.selection_propensity,
                "candidate_count": example.candidate_count,
                "recovered_within_48h": int(example.recovered_within_48h),
            }
        )
    frame = pd.DataFrame(rows)
    if tuple(frame.columns[: len(MODEL_FEATURE_ALLOWLIST)]) != MODEL_FEATURE_ALLOWLIST:
        raise ValueError("flattened feature table column order changed")
    if LoggedRecoveryExample.model_fields["feature_schema_hash"].default != FEATURE_SCHEMA_HASH:
        raise RuntimeError("logged example schema hash default is stale")
    return frame


def read_feature_group(root: Path, group: str) -> pd.DataFrame:
    frame = pd.read_parquet(root / "features" / f"{group}-features-v1.parquet")
    expected = (
        *MODEL_FEATURE_ALLOWLIST,
        "selection_propensity",
        "candidate_count",
        "recovered_within_48h",
    )
    if tuple(frame.columns) != expected:
        raise ValueError("feature artifact schema does not match the frozen allowlist")
    return frame


def write_phase4_summary(root: Path) -> Path:
    """Build a compact, seed-free checkpoint from already frozen Phase 4 artifacts."""

    paths = {
        "training_manifest": root / "logged" / "training-manifest-v1.json",
        "development_manifest": root / "logged" / "development-manifest-v1.json",
        "calibration_manifest": root / "logged" / "calibration-manifest-v1.json",
        "heldout_manifest": root / "logged" / "heldout-manifest-v1.json",
        "model_manifest": root / "models" / "recovery-model-v1" / "model-manifest-v1.json",
        "calibration": root / "calibration" / "recovery-model-v1" / "calibration-manifest-v1.json",
        "development": root / "reports" / "development-selection-v1.json",
        "heldout": root / "reports" / "heldout-evaluation-v1.json",
        "shap": root / "reports" / "shap-report-v1.json",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Phase 4 evidence is incomplete: {missing}")
    evidence = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    development = evidence["development"]
    heldout = evidence["heldout"]
    calibration = evidence["calibration"]
    model_manifest = evidence["model_manifest"]
    tracked_artifacts = {
        **paths,
        "logistic_model": root / "models" / "recovery-model-v1" / "logistic-regression-v1.joblib",
        "lightgbm_model": root / "models" / "recovery-model-v1" / "lightgbm-v1.joblib",
        "lightgbm_without_health_model": root
        / "models"
        / "recovery-model-v1"
        / "lightgbm-without-health-v1.joblib",
        "logistic_calibrator": root
        / "calibration"
        / "recovery-model-v1"
        / "logistic-calibrator-v1.joblib",
        "lightgbm_calibrator": root
        / "calibration"
        / "recovery-model-v1"
        / "lightgbm-calibrator-v1.joblib",
        "lightgbm_without_health_calibrator": root
        / "calibration"
        / "recovery-model-v1"
        / "lightgbm-without-health-calibrator-v1.joblib",
    }
    summary = {
        "phase": 4,
        "status": "COMPLETE",
        "model_version": model_manifest["model_version"],
        "feature_schema_version": model_manifest["feature_schema_version"],
        "feature_schema_hash": model_manifest["feature_schema_hash"],
        "target": "recovered_within_48h",
        "detector_v2_role": "ADVISORY_FEATURE_SOURCE_ONLY",
        "seed_protocol": {
            "training": evidence["training_manifest"]["seeds"],
            "development": evidence["development_manifest"]["seeds"],
            "calibration": evidence["calibration_manifest"]["seeds"],
            "heldout_model_test": evidence["heldout_manifest"]["seeds"],
            "overall_final": list(range(20_261_101, 20_261_121)),
            "overall_final_status": "UNTOUCHED_AND_COMMAND_GUARDED",
        },
        "logged_datasets": {
            name: evidence[f"{name}_manifest"]
            for name in ("training", "development", "calibration", "heldout")
        },
        "exploration": {
            "method": "UNIFORM_BY_ACTION_TYPE_WITH_UNIFORM_RETRY_LATER_DELAY",
            "action_type_propensity": 1 / 6,
            "retry_later_candidate_propensity": 1 / 24,
            "candidate_count": 9,
            "one_selected_action_and_one_observed_outcome_per_decision": True,
            "unselected_counterfactuals_in_training": False,
            "inverse_propensity_weighting_used": False,
        },
        "development_selection": {
            "logistic_regression": _compact_probability_metrics(development["logistic_regression"]),
            "selected_lightgbm_candidate_index": development["selected_lightgbm_candidate_index"],
            "selected_lightgbm_hyperparameters": model_manifest[
                "selected_lightgbm_hyperparameters"
            ],
            "selected_lightgbm": _compact_probability_metrics(development["selected_lightgbm"]),
            "selected_lightgbm_without_health": _compact_probability_metrics(
                development["selected_lightgbm_without_health"]
            ),
        },
        "calibration": {
            "selected_method": calibration["selected_method"],
            "primary_method_candidates": [
                {
                    "method": candidate["method"],
                    "metrics": _compact_probability_metrics(candidate["metrics"]),
                }
                for candidate in calibration["primary_method_candidates"]
            ],
            "calibrated_metrics": {
                name: _compact_probability_metrics(metrics)
                for name, metrics in calibration["calibrated_metrics"].items()
            },
            "mappings": calibration["calibration_mappings"],
        },
        "heldout_evaluation": {
            "run_count": heldout["heldout_run_count"],
            "constant_prevalence_baseline": _compact_probability_metrics(
                heldout["constant_prevalence_baseline"]
            ),
            "models": {
                model: {
                    state: _compact_probability_metrics(metrics)
                    for state, metrics in states.items()
                }
                for model, states in heldout["models"].items()
            },
            "per_action": {
                action: _compact_probability_metrics(metrics)
                for action, metrics in heldout["primary_per_action_metrics"].items()
            },
            "ranking": heldout["ranking"],
            "health_feature_ablation": {
                side: {
                    "probability_metrics": _compact_probability_metrics(
                        values["probability_metrics"]
                    ),
                    "ranking_metrics": values["ranking_metrics"],
                }
                for side, values in heldout["health_feature_ablation"].items()
                if side in {"with_health", "without_health"}
            }
            | {
                "delta_with_minus_without": heldout["health_feature_ablation"][
                    "delta_with_minus_without"
                ]
            },
            "incident_adjacent_slices": {
                name: _compact_probability_metrics(metrics)
                for name, metrics in heldout["incident_adjacent_slices"].items()
            },
            "failure_family_slices": {
                name: _compact_probability_metrics(metrics)
                for name, metrics in heldout["failure_family_slices"].items()
            },
            "calibration_safety_gate": heldout["calibration_safety_gate"],
            "model_quality_gate": heldout["model_quality_gate"],
            "recommended_model": heldout["recommended_model"],
        },
        "shap": {
            "role": evidence["shap"]["explanation_role"],
            "global_top_10": evidence["shap"]["global_mean_absolute_shap"][:10],
            "gain_top_10": evidence["shap"]["global_gain_importance"][:10],
            "example_local_action_comparison": evidence["shap"]["local_action_comparisons"][0],
        },
        "runtime_seconds": {
            "training_logged_generation": _report_runtime(
                root / "reports" / "training-logging-audit-v1.json"
            ),
            "development_logged_generation": _report_runtime(
                root / "reports" / "development-logging-audit-v1.json"
            ),
            "model_training_and_selection": development["runtime_seconds"],
            "calibration_logged_generation": calibration["logged_generation_runtime_seconds"],
            "calibration_fit": calibration["runtime_seconds"],
            "heldout_logged_generation": heldout["logged_generation_runtime_seconds"],
            "heldout_evaluation": heldout["runtime_seconds"],
        },
        "artifact_sha256": {name: sha256_file(path) for name, path in tracked_artifacts.items()},
        "phase_boundaries": {
            "intelligent_policy_executed": False,
            "erv_optimizer_implemented": False,
            "gemini_called": False,
            "razorpay_called": False,
            "final_benchmark_executed": False,
        },
    }
    output = root / "phase4-summary-v1.json"
    write_json(output, summary)
    return output


def _compact_probability_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "sample_count",
        "positive_count",
        "positive_rate",
        "brier_score",
        "log_loss",
        "expected_calibration_error",
        "roc_auc",
        "pr_auc",
    )
    return {key: metrics.get(key) for key in keys if key in metrics}


def _report_runtime(path: Path) -> float:
    report = json.loads(path.read_text(encoding="utf-8"))
    return float(report["runtime_seconds"])


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")
