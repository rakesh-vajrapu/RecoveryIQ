from __future__ import annotations

import json
from pathlib import Path
from statistics import fmean, median
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from recoveriq_ml.artifacts import sha256_file, write_json, write_markdown
from recoveriq_ml.metrics import binary_probability_metrics, per_action_metrics
from recoveriq_ml_v2.calibration import load_calibrators_v2
from recoveriq_ml_v2.config import (
    LATER_DECISION_MAX_BRIER,
    LATER_DECISION_MAX_ECE,
    LATER_DECISION_MIN_ROWS,
    MIN_PAIRWISE_RANKING,
    MODEL_V2_HELDOUT_SEEDS,
    MODEL_V2_MAX_ECE,
)
from recoveriq_ml_v2.logging import generate_and_write_logged_group, read_logged_group
from recoveriq_ml_v2.models import MODEL_V2_FEATURE_ALLOWLIST
from recoveriq_ml_v2.training import (
    TARGET_COLUMN,
    load_model_v2,
    predict_v2_probabilities,
    validate_model_v2_frame,
)


def evaluate_model_v2_once(
    *,
    logged_root: Path,
    model_root: Path,
    calibration_root: Path,
    report_root: Path,
) -> dict[str, Any]:
    output = report_root / "heldout-evaluation-v2.json"
    attempt_path = report_root / "heldout-attempt-v2.json"
    if output.exists() or attempt_path.exists():
        raise FileExistsError("Model V2 held-out was already attempted; refusing rerun")
    _assert_frozen_model_inputs(model_root, calibration_root)
    report_root.mkdir(parents=True, exist_ok=True)
    write_json(
        attempt_path,
        {
            "artifact_type": "model_v2_registered_heldout_attempt",
            "heldout_seeds": MODEL_V2_HELDOUT_SEEDS,
            "status": "STARTED",
        },
    )
    started = perf_counter()
    generate_and_write_logged_group(
        group="heldout",
        seeds=MODEL_V2_HELDOUT_SEEDS,
        logged_root=logged_root,
        include_candidate_truth=True,
    )
    frame = read_logged_group(logged_root, "heldout")
    truth = pd.read_parquet(logged_root / "sequential-heldout-candidate-truth-v2.parquet")
    _assert_heldout_boundary(frame, truth, logged_root, model_root)
    models = load_model_v2(model_root)
    calibrators = load_calibrators_v2(calibration_root)
    features = list(MODEL_V2_FEATURE_ALLOWLIST)
    target = frame[TARGET_COLUMN].astype(int).to_numpy()
    raw = {name: predict_v2_probabilities(model, frame[features]) for name, model in models.items()}
    calibrated = {name: calibrators[name].transform(values) for name, values in raw.items()}
    probability_metrics = {
        name: {
            "raw": binary_probability_metrics(target, raw[name]),
            "calibrated": binary_probability_metrics(target, calibrated[name]),
        }
        for name in models
    }
    primary = calibrated["lightgbm"]
    by_index = {
        str(index): binary_probability_metrics(
            target[frame["decision_index"].to_numpy() == index],
            primary[frame["decision_index"].to_numpy() == index],
        )
        for index in (1, 2, 3)
    }
    per_action = per_action_metrics(
        target,
        primary,
        frame["selected_action_label"].astype(str),
    )
    ranking = _ranking_metrics_by_index(
        truth,
        models["lightgbm"],
        calibrators["lightgbm"],
    )
    gate = _quality_gate(
        probability_metrics["lightgbm"]["calibrated"],
        probability_metrics["logistic"]["calibrated"],
        by_index,
        ranking,
    )
    report = {
        "artifact_type": "model_v2_one_time_heldout_evaluation",
        "heldout_seeds": MODEL_V2_HELDOUT_SEEDS,
        "heldout_run_count": 1,
        "sample_count": len(frame),
        "episode_count": int(frame["episode_id"].nunique()),
        "decisions_by_index": {
            str(key): int(value)
            for key, value in frame["decision_index"].value_counts().sort_index().items()
        },
        "models": probability_metrics,
        "primary_per_action_metrics": per_action,
        "primary_metrics_by_decision_index": by_index,
        "ranking_by_decision_index": ranking,
        "model_v2_quality_gate": gate,
        "runtime_seconds": perf_counter() - started,
        "health_feature_research_comparator": "NOT_RUN_PRIMARY_IS_PREREGISTERED_NO_HEALTH",
    }
    write_json(output, report)
    write_markdown(report_root / "heldout-report-v2.md", render_model_v2_report(report))
    write_json(
        attempt_path,
        {
            "artifact_type": "model_v2_registered_heldout_attempt",
            "heldout_seeds": MODEL_V2_HELDOUT_SEEDS,
            "status": "COMPLETED",
            "result_sha256": sha256_file(output),
            "quality_gate": gate["status"],
        },
    )
    return report


def _ranking_metrics_by_index(
    truth: pd.DataFrame,
    model: Any,
    calibrator: Any,
) -> dict[str, Any]:
    features = list(MODEL_V2_FEATURE_ALLOWLIST)
    raw = predict_v2_probabilities(model, truth[features])
    scored = truth.copy()
    scored["predicted_probability"] = calibrator.transform(raw)
    return {
        str(index): _ranking_metrics(subset)
        for index, subset in scored.groupby("decision_index", sort=True)
    }


def _ranking_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    top_1 = 0
    top_2 = 0
    pair_correct = 0.0
    pair_count = 0
    regrets: list[float] = []
    decisions = 0
    for _, subset in frame.groupby("decision_key", sort=False):
        subset = subset.sort_values("candidate_rank", kind="stable")
        predicted = subset["predicted_probability"].to_numpy(dtype=float)
        oracle = subset["oracle_probability"].to_numpy(dtype=float)
        predicted_order = np.argsort(-predicted, kind="stable")
        oracle_best = int(np.argmax(oracle))
        chosen = int(predicted_order[0])
        top_1 += int(chosen == oracle_best)
        top_2 += int(oracle_best in predicted_order[:2])
        regrets.append(float(oracle[oracle_best] - oracle[chosen]))
        for left in range(len(subset)):
            for right in range(left + 1, len(subset)):
                oracle_delta = oracle[left] - oracle[right]
                if abs(oracle_delta) < 1e-12:
                    continue
                predicted_delta = predicted[left] - predicted[right]
                if abs(predicted_delta) < 1e-12:
                    pair_correct += 0.5
                elif (predicted_delta > 0) == (oracle_delta > 0):
                    pair_correct += 1
                pair_count += 1
        decisions += 1
    ordered = sorted(regrets)
    return {
        "decision_count": decisions,
        "top_1_oracle_action_agreement": top_1 / decisions,
        "top_2_oracle_action_coverage": top_2 / decisions,
        "pairwise_ranking_accuracy": pair_correct / pair_count if pair_count else None,
        "probability_regret": {
            "mean": fmean(regrets),
            "median": median(regrets),
            "p90": ordered[round((len(ordered) - 1) * 0.9)],
        },
    }


def _quality_gate(
    lightgbm: dict[str, Any],
    logistic: dict[str, Any],
    by_index: dict[str, dict[str, Any]],
    ranking: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    checks: dict[str, bool] = {
        "frozen_schema_and_leakage_boundary_valid": True,
        "lightgbm_brier_no_worse_than_logistic": float(lightgbm["brier_score"])
        <= float(logistic["brier_score"]),
        "overall_ece_at_most_0_05": float(lightgbm["expected_calibration_error"])
        <= MODEL_V2_MAX_ECE,
    }
    for index in (2, 3):
        metrics = by_index[str(index)]
        rank = ranking[str(index)]
        checks[f"decision_{index}_sample_at_least_500"] = (
            int(metrics["sample_count"]) >= LATER_DECISION_MIN_ROWS
        )
        checks[f"decision_{index}_brier_at_most_0_30"] = (
            float(metrics["brier_score"]) <= LATER_DECISION_MAX_BRIER
        )
        checks[f"decision_{index}_ece_at_most_0_10"] = (
            float(metrics["expected_calibration_error"]) <= LATER_DECISION_MAX_ECE
        )
        checks[f"decision_{index}_pairwise_at_least_0_55"] = (
            float(rank["pairwise_ranking_accuracy"]) >= MIN_PAIRWISE_RANKING
        )
    checks["decision_1_pairwise_at_least_0_55"] = (
        float(ranking["1"]["pairwise_ranking_accuracy"]) >= MIN_PAIRWISE_RANKING
    )
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _assert_frozen_model_inputs(model_root: Path, calibration_root: Path) -> None:
    manifest = json.loads((model_root / "model-manifest-v2.json").read_text(encoding="utf-8"))
    calibration = json.loads(
        (calibration_root / "calibration-manifest-v2.json").read_text(encoding="utf-8")
    )
    if not manifest["primary_excludes_health"]:
        raise RuntimeError("primary Model V2 must exclude health features")
    if manifest["feature_schema_hash"] != calibration["feature_schema_hash"]:
        raise RuntimeError("Model V2 calibration schema does not match model freeze")
    if calibration["selected_method"] not in {"sigmoid", "isotonic"}:
        raise RuntimeError("Model V2 calibration method is not frozen")


def _assert_heldout_boundary(
    frame: pd.DataFrame,
    truth: pd.DataFrame,
    logged_root: Path,
    model_root: Path,
) -> None:
    validate_model_v2_frame(frame)
    dataset_manifest = json.loads(
        (logged_root / "sequential-heldout-manifest-v2.json").read_text(encoding="utf-8")
    )
    model_manifest = json.loads((model_root / "model-manifest-v2.json").read_text(encoding="utf-8"))
    if dataset_manifest["feature_schema_hash"] != model_manifest["feature_schema_hash"]:
        raise RuntimeError("held-out feature schema does not match frozen Model V2")
    forbidden = {"oracle_probability", "hidden_failure_family"}
    if forbidden & set(frame.columns):
        raise RuntimeError("hidden held-out truth leaked into the predictive frame")
    if not forbidden.issubset(truth.columns):
        raise RuntimeError("evaluation-only candidate truth is incomplete")


def render_model_v2_report(report: dict[str, Any]) -> str:
    metrics = report["models"]["lightgbm"]["calibrated"]
    lines = [
        "# Recovery Model V2 One-Time Held-Out Report",
        "",
        f"Decisions: {report['sample_count']}",
        f"Episodes: {report['episode_count']}",
        f"Brier: {metrics['brier_score']:.6f}",
        f"Log loss: {metrics['log_loss']:.6f}",
        f"ECE: {metrics['expected_calibration_error']:.6f}",
        f"ROC-AUC: {metrics['roc_auc']:.6f}",
        f"PR-AUC: {metrics['pr_auc']:.6f}",
        "",
        f"Quality gate: **{report['model_v2_quality_gate']['status']}**",
        "",
    ]
    for index in ("1", "2", "3"):
        stage = report["primary_metrics_by_decision_index"][index]
        ranking = report["ranking_by_decision_index"][index]
        lines.append(
            f"- Decision {index}: n={stage['sample_count']}, Brier={stage['brier_score']:.6f}, "
            f"ECE={stage['expected_calibration_error']:.6f}, "
            f"pairwise={ranking['pairwise_ranking_accuracy']:.6f}"
        )
    lines.extend(
        (
            "",
            "Primary Model V2 contains no Detector V2/payment-health feature.",
            "Hidden candidate probabilities were joined only after frozen prediction.",
        )
    )
    return "\n".join(lines)
