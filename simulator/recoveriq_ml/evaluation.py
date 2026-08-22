from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from statistics import fmean, median
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import shap

from recoveriq_ml.artifacts import write_json, write_markdown
from recoveriq_ml.calibration import load_calibrators
from recoveriq_ml.config import (
    CALIBRATION_MAX_ECE,
    CALIBRATION_MAX_RELIABILITY_GAP,
    CALIBRATION_MIN_RELIABILITY_BIN_COUNT,
    ML_HELDOUT_TEST_SEEDS,
    MODEL_MIN_PROBABILITY_IMPROVEMENT,
)
from recoveriq_ml.logged_data import HeldoutDecision
from recoveriq_ml.metrics import binary_probability_metrics, per_action_metrics
from recoveriq_ml.models import HEALTH_FEATURES, MODEL_FEATURE_ALLOWLIST
from recoveriq_ml.training import (
    load_models,
    model_feature_names,
    predict_probabilities,
)


def evaluate_frozen_models(
    *,
    frame: pd.DataFrame,
    decisions: tuple[HeldoutDecision, ...],
    model_root: Path,
    calibration_root: Path,
    report_root: Path,
    training_prevalence: float,
) -> dict[str, Any]:
    if len(frame) != len(decisions):
        raise ValueError("held-out logged rows and ranking decisions are not aligned")
    started = perf_counter()
    models = load_models(model_root)
    calibrators = load_calibrators(calibration_root)
    all_features = list(MODEL_FEATURE_ALLOWLIST)
    without_health = [name for name in all_features if name not in HEALTH_FEATURES]
    features_by_model = {
        "logistic": all_features,
        "lightgbm": all_features,
        "lightgbm_without_health": without_health,
    }
    target = frame["recovered_within_48h"].astype(int).to_numpy()
    actions = frame["action_type"].astype(str).to_numpy()
    raw_predictions = {
        name: predict_probabilities(model, frame[features_by_model[name]])
        for name, model in models.items()
    }
    calibrated_predictions = {
        name: calibrators[name].transform(raw_predictions[name]) for name in models
    }
    probability_metrics = {
        name: {
            "raw": binary_probability_metrics(target, raw_predictions[name]),
            "calibrated": binary_probability_metrics(
                target,
                calibrated_predictions[name],
            ),
        }
        for name in models
    }
    constant_predictions = np.full(len(target), training_prevalence, dtype=float)
    constant_metrics = binary_probability_metrics(target, constant_predictions)

    ranking = {
        name: _ranking_metrics(
            decisions,
            models[name],
            calibrators[name],
            features_by_model[name],
        )
        for name in models
    }
    lightgbm_metrics = probability_metrics["lightgbm"]["calibrated"]
    logistic_metrics = probability_metrics["logistic"]["calibrated"]
    calibration_gate = _calibration_gate(lightgbm_metrics, constant_metrics)
    quality_gate = _quality_gate(
        lightgbm_metrics,
        logistic_metrics,
        ranking["lightgbm"],
    )
    primary_predictions = calibrated_predictions["lightgbm"]
    slices = _evaluation_slices(target, primary_predictions, decisions)
    failure_families = _failure_family_slices(target, primary_predictions, decisions)
    per_action = per_action_metrics(target, primary_predictions, actions)
    health_ablation = {
        "with_health": {
            "probability_metrics": lightgbm_metrics,
            "ranking_metrics": ranking["lightgbm"],
        },
        "without_health": {
            "probability_metrics": probability_metrics["lightgbm_without_health"]["calibrated"],
            "ranking_metrics": ranking["lightgbm_without_health"],
        },
        "delta_with_minus_without": _ablation_delta(
            lightgbm_metrics,
            probability_metrics["lightgbm_without_health"]["calibrated"],
            ranking["lightgbm"],
            ranking["lightgbm_without_health"],
        ),
    }
    shap_report = _shap_report(
        models["lightgbm"],
        calibrators["lightgbm"],
        frame,
        decisions,
        all_features,
    )
    report = {
        "phase": "one_time_heldout_model_test",
        "heldout_seeds": list(ML_HELDOUT_TEST_SEEDS),
        "heldout_run_count": 1,
        "sample_count": len(frame),
        "training_prevalence": training_prevalence,
        "constant_prevalence_baseline": constant_metrics,
        "models": probability_metrics,
        "primary_per_action_metrics": per_action,
        "ranking": ranking,
        "health_feature_ablation": health_ablation,
        "incident_adjacent_slices": slices,
        "failure_family_slices": failure_families,
        "calibration_safety_gate": calibration_gate,
        "model_quality_gate": quality_gate,
        "recommended_model": "lightgbm" if quality_gate["status"] == "PASS" else "logistic",
        "shap": shap_report,
        "runtime_seconds": perf_counter() - started,
    }
    write_json(report_root / "heldout-evaluation-v1.json", report)
    write_json(report_root / "shap-report-v1.json", shap_report)
    write_markdown(report_root / "heldout-report-v1.md", render_heldout_report(report))
    return report


def _ranking_metrics(
    decisions: tuple[HeldoutDecision, ...],
    model: Any,
    calibrator: Any,
    features: list[str],
) -> dict[str, Any]:
    rows = [
        candidate.features.model_features()
        for decision in decisions
        for candidate in decision.candidates
    ]
    frame = pd.DataFrame(rows)
    raw = predict_probabilities(model, frame[features])
    predicted = calibrator.transform(raw)
    cursor = 0
    top_1 = 0
    top_2 = 0
    pair_correct = 0.0
    pair_count = 0
    regrets: list[float] = []
    random_agreement: list[float] = []
    for decision in decisions:
        count = len(decision.candidates)
        scores = predicted[cursor : cursor + count]
        cursor += count
        oracle = np.asarray(
            [candidate.oracle_probability for candidate in decision.candidates],
            dtype=float,
        )
        predicted_order = np.argsort(-scores, kind="stable")
        oracle_best = int(np.argmax(oracle))
        chosen = int(predicted_order[0])
        top_1 += int(chosen == oracle_best)
        top_2 += int(oracle_best in predicted_order[:2])
        regrets.append(float(oracle[oracle_best] - oracle[chosen]))
        random_agreement.append(1 / count)
        for left in range(count):
            for right in range(left + 1, count):
                oracle_delta = oracle[left] - oracle[right]
                if abs(oracle_delta) < 1e-12:
                    continue
                predicted_delta = scores[left] - scores[right]
                if abs(predicted_delta) < 1e-12:
                    pair_correct += 0.5
                elif (predicted_delta > 0) == (oracle_delta > 0):
                    pair_correct += 1
                pair_count += 1
    return {
        "decision_count": len(decisions),
        "mean_random_top_1_agreement": fmean(random_agreement),
        "top_1_oracle_action_agreement": top_1 / len(decisions),
        "top_2_oracle_action_coverage": top_2 / len(decisions),
        "pairwise_ranking_accuracy": pair_correct / pair_count if pair_count else None,
        "probability_regret": _summary(regrets),
    }


def _calibration_gate(
    metrics: dict[str, Any],
    constant: dict[str, Any],
) -> dict[str, Any]:
    qualifying_gaps = [
        float(row["absolute_gap"])
        for row in metrics["reliability_bins"]
        if int(row["count"]) >= CALIBRATION_MIN_RELIABILITY_BIN_COUNT
    ]
    maximum_gap = max(qualifying_gaps, default=0.0)
    checks = {
        "brier_beats_constant_prevalence": float(metrics["brier_score"])
        < float(constant["brier_score"]),
        "ece_at_most_0_05": float(metrics["expected_calibration_error"]) <= CALIBRATION_MAX_ECE,
        "no_supported_bin_gap_above_0_15": maximum_gap <= CALIBRATION_MAX_RELIABILITY_GAP,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "actual_brier": metrics["brier_score"],
        "constant_brier": constant["brier_score"],
        "actual_ece": metrics["expected_calibration_error"],
        "maximum_supported_reliability_gap": maximum_gap,
        "failure_behavior": "PROBABILITY_BANDS_OR_ADVISORY_CONFIDENCE_ONLY",
    }


def _quality_gate(
    lightgbm: dict[str, Any],
    logistic: dict[str, Any],
    ranking: dict[str, Any],
) -> dict[str, Any]:
    brier_improvement = float(logistic["brier_score"]) - float(lightgbm["brier_score"])
    log_loss_improvement = float(logistic["log_loss"]) - float(lightgbm["log_loss"])
    checks = {
        "probability_metric_improvement": max(brier_improvement, log_loss_improvement)
        >= MODEL_MIN_PROBABILITY_IMPROVEMENT,
        "pairwise_ranking_better_than_random": float(ranking["pairwise_ranking_accuracy"]) > 0.5,
        "top_1_better_than_random": float(ranking["top_1_oracle_action_agreement"])
        > float(ranking["mean_random_top_1_agreement"]),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "brier_improvement_over_logistic": brier_improvement,
        "log_loss_improvement_over_logistic": log_loss_improvement,
        "failure_behavior": "RETAIN_LOGISTIC_REGRESSION",
    }


def _evaluation_slices(
    targets: np.ndarray,
    probabilities: np.ndarray,
    decisions: tuple[HeldoutDecision, ...],
) -> dict[str, Any]:
    masks = {
        "during_hidden_incident": np.asarray(
            [decision.during_hidden_incident for decision in decisions]
        ),
        "outside_hidden_incident": np.asarray(
            [not decision.during_hidden_incident for decision in decisions]
        ),
        "near_incident_boundary_6h": np.asarray(
            [decision.near_incident_boundary for decision in decisions]
        ),
        "not_near_incident_boundary_6h": np.asarray(
            [not decision.near_incident_boundary for decision in decisions]
        ),
        "high_observable_health_evidence": np.asarray(
            [decision.high_observable_health_evidence for decision in decisions]
        ),
        "low_observable_health_evidence": np.asarray(
            [not decision.high_observable_health_evidence for decision in decisions]
        ),
    }
    return {
        name: binary_probability_metrics(targets[mask], probabilities[mask])
        for name, mask in masks.items()
    }


def _failure_family_slices(
    targets: np.ndarray,
    probabilities: np.ndarray,
    decisions: tuple[HeldoutDecision, ...],
) -> dict[str, Any]:
    indexes: defaultdict[str, list[int]] = defaultdict(list)
    for index, decision in enumerate(decisions):
        indexes[decision.hidden_cause].append(index)
    return {
        cause: binary_probability_metrics(
            targets[np.asarray(rows, dtype=int)],
            probabilities[np.asarray(rows, dtype=int)],
        )
        for cause, rows in sorted(indexes.items())
    }


def _ablation_delta(
    with_health: dict[str, Any],
    without_health: dict[str, Any],
    ranking_with: dict[str, Any],
    ranking_without: dict[str, Any],
) -> dict[str, float]:
    return {
        "brier_score": float(with_health["brier_score"]) - float(without_health["brier_score"]),
        "log_loss": float(with_health["log_loss"]) - float(without_health["log_loss"]),
        "expected_calibration_error": float(with_health["expected_calibration_error"])
        - float(without_health["expected_calibration_error"]),
        "top_1_oracle_action_agreement": float(ranking_with["top_1_oracle_action_agreement"])
        - float(ranking_without["top_1_oracle_action_agreement"]),
        "pairwise_ranking_accuracy": float(ranking_with["pairwise_ranking_accuracy"])
        - float(ranking_without["pairwise_ranking_accuracy"]),
        "mean_probability_regret": float(ranking_with["probability_regret"]["mean"])
        - float(ranking_without["probability_regret"]["mean"]),
    }


def _shap_report(
    model: Any,
    calibrator: Any,
    frame: pd.DataFrame,
    decisions: tuple[HeldoutDecision, ...],
    features: list[str],
) -> dict[str, Any]:
    preprocessor = model.named_steps["preprocessor"]
    classifier = model.named_steps["classifier"]
    sample_indexes = np.linspace(0, len(frame) - 1, min(1_000, len(frame)), dtype=int)
    transformed = preprocessor.transform(frame.iloc[sample_indexes][features])
    names = model_feature_names(model)
    explainer = shap.TreeExplainer(classifier, feature_perturbation="tree_path_dependent")
    values = np.asarray(explainer.shap_values(transformed), dtype=float)
    if values.ndim == 3:
        values = values[:, :, -1]
    mean_absolute = np.mean(np.abs(values), axis=0)
    global_rows = [
        {"feature": names[index], "mean_absolute_shap": float(mean_absolute[index])}
        for index in np.argsort(-mean_absolute)[:25]
    ]
    gain = np.asarray(classifier.feature_importances_, dtype=float)
    gain_rows = [
        {"feature": names[index], "gain_importance": float(gain[index])}
        for index in np.argsort(-gain)[:25]
    ]
    local: list[dict[str, Any]] = []
    for decision in decisions[:3]:
        candidate_frame = pd.DataFrame(
            [candidate.features.model_features() for candidate in decision.candidates]
        )
        raw = predict_probabilities(model, candidate_frame[features])
        calibrated = calibrator.transform(raw)
        indexes = [int(np.argmax(calibrated)), int(np.argmin(calibrated))]
        candidate_transformed = preprocessor.transform(candidate_frame.iloc[indexes][features])
        candidate_values = np.asarray(explainer.shap_values(candidate_transformed), dtype=float)
        if candidate_values.ndim == 3:
            candidate_values = candidate_values[:, :, -1]
        comparisons = []
        for position, index in enumerate(indexes):
            contribution = candidate_values[position]
            top = np.argsort(-np.abs(contribution))[:10]
            comparisons.append(
                {
                    "action_type": decision.candidates[index].action.action_type.value,
                    "delay_hours": decision.candidates[index].action.scheduled_delay_hours,
                    "raw_probability": float(raw[index]),
                    "calibrated_probability": float(calibrated[index]),
                    "top_contributions": [
                        {"feature": names[item], "shap_value": float(contribution[item])}
                        for item in top
                    ],
                }
            )
        local.append({"decision_key": decision.decision_key, "action_comparison": comparisons})
    return {
        "explanation_role": "STRUCTURED_EVIDENCE_ONLY_NO_POLICY_AUTHORITY",
        "global_mean_absolute_shap": global_rows,
        "global_gain_importance": gain_rows,
        "local_action_comparisons": local,
        "explained_sample_count": len(sample_indexes),
    }


def _summary(values: list[float]) -> dict[str, int | float | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "p90": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "mean": fmean(values),
        "median": median(values),
        "p90": ordered[round((len(ordered) - 1) * 0.9)],
    }


def render_heldout_report(report: dict[str, Any]) -> str:
    primary = report["models"]["lightgbm"]
    calibrated = primary["calibrated"]
    ranking = report["ranking"]["lightgbm"]
    return "\n".join(
        (
            "# Recovery Model V1 One-Time Held-Out Report",
            "",
            f"Samples: {report['sample_count']}",
            f"Brier: {calibrated['brier_score']:.6f}",
            f"Log loss: {calibrated['log_loss']:.6f}",
            f"ECE: {calibrated['expected_calibration_error']:.6f}",
            f"ROC-AUC: {calibrated['roc_auc']:.6f}",
            f"PR-AUC: {calibrated['pr_auc']:.6f}",
            "",
            f"Top-1 oracle agreement: {ranking['top_1_oracle_action_agreement']:.6f}",
            f"Top-2 oracle coverage: {ranking['top_2_oracle_action_coverage']:.6f}",
            f"Pairwise ranking accuracy: {ranking['pairwise_ranking_accuracy']:.6f}",
            "",
            f"Calibration safety gate: **{report['calibration_safety_gate']['status']}**",
            f"Model quality gate: **{report['model_quality_gate']['status']}**",
            f"Recommended model: `{report['recommended_model']}`",
            "",
            "Simulator counterfactual values were used only after frozen model prediction.",
            "No intelligent action policy was executed.",
        )
    )
