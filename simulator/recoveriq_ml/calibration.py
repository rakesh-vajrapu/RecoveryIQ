from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol, cast

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from recoveriq_ml.artifacts import sha256_file, write_json
from recoveriq_ml.config import ML_CALIBRATION_SEEDS, MODEL_RANDOM_STATE
from recoveriq_ml.metrics import binary_probability_metrics
from recoveriq_ml.models import FEATURE_SCHEMA_HASH, HEALTH_FEATURES, MODEL_FEATURE_ALLOWLIST
from recoveriq_ml.training import load_models, predict_probabilities

CALIBRATOR_FILENAMES = {
    "logistic": "logistic-calibrator-v1.joblib",
    "lightgbm": "lightgbm-calibrator-v1.joblib",
    "lightgbm_without_health": "lightgbm-without-health-calibrator-v1.joblib",
}


class ProbabilityCalibrator(Protocol):
    def transform(self, probabilities: np.ndarray) -> np.ndarray: ...


@dataclass(slots=True)
class SigmoidCalibrator:
    model: LogisticRegression

    def transform(self, probabilities: np.ndarray) -> np.ndarray:
        logits = _logit(probabilities).reshape(-1, 1)
        return np.asarray(self.model.predict_proba(logits)[:, 1], dtype=float)


@dataclass(slots=True)
class IsotonicCalibrator:
    model: IsotonicRegression

    def transform(self, probabilities: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict(probabilities), dtype=float)


def fit_and_freeze_calibration(
    calibration: pd.DataFrame,
    model_root: Path,
    calibration_root: Path,
) -> dict[str, Any]:
    started = perf_counter()
    models = load_models(model_root)
    all_features = list(MODEL_FEATURE_ALLOWLIST)
    without_health = [name for name in all_features if name not in HEALTH_FEATURES]
    features_by_name = {
        "logistic": all_features,
        "lightgbm": all_features,
        "lightgbm_without_health": without_health,
    }
    target = calibration["recovered_within_48h"].astype(int).to_numpy()
    raw = {
        name: predict_probabilities(model, calibration[features_by_name[name]])
        for name, model in models.items()
    }
    primary_candidates: list[dict[str, Any]] = []
    fitted_primary: dict[str, ProbabilityCalibrator] = {}
    for method in ("sigmoid", "isotonic"):
        calibrator = fit_calibrator(method, raw["lightgbm"], target)
        fitted_primary[method] = calibrator
        primary_candidates.append(
            {
                "method": method,
                "metrics": binary_probability_metrics(
                    target,
                    calibrator.transform(raw["lightgbm"]),
                ),
            }
        )
    selected = min(primary_candidates, key=_selection_key)
    selected_method = str(selected["method"])
    calibration_root.mkdir(parents=True, exist_ok=True)
    mappings: dict[str, dict[str, str]] = {}
    calibrated_metrics: dict[str, Any] = {}
    for name, probabilities in raw.items():
        calibrator = fit_calibrator(selected_method, probabilities, target)
        path = calibration_root / CALIBRATOR_FILENAMES[name]
        joblib.dump(calibrator, path, compress=3)
        mappings[name] = {"artifact": path.name, "sha256": sha256_file(path)}
        calibrated_metrics[name] = binary_probability_metrics(
            target,
            calibrator.transform(probabilities),
        )
    report = {
        "phase": "calibration_selection_and_freeze",
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "calibration_seeds": list(ML_CALIBRATION_SEEDS),
        "selection_rule": "minimum Brier, then log loss, then ECE",
        "primary_method_candidates": primary_candidates,
        "selected_method": selected_method,
        "calibration_mappings": mappings,
        "raw_metrics": {
            name: binary_probability_metrics(target, probabilities)
            for name, probabilities in raw.items()
        },
        "calibrated_metrics": calibrated_metrics,
        "runtime_seconds": perf_counter() - started,
    }
    write_json(calibration_root / "calibration-manifest-v1.json", report)
    return report


def load_calibrators(calibration_root: Path) -> dict[str, ProbabilityCalibrator]:
    return {
        name: joblib.load(calibration_root / filename)
        for name, filename in CALIBRATOR_FILENAMES.items()
    }


def fit_calibrator(
    method: str,
    probabilities: np.ndarray,
    targets: np.ndarray,
) -> ProbabilityCalibrator:
    if method == "sigmoid":
        model = LogisticRegression(
            random_state=MODEL_RANDOM_STATE,
            solver="lbfgs",
            max_iter=1_000,
        )
        model.fit(_logit(probabilities).reshape(-1, 1), targets)
        return SigmoidCalibrator(model)
    if method == "isotonic":
        model = IsotonicRegression(out_of_bounds="clip", y_min=1e-6, y_max=1 - 1e-6)
        model.fit(probabilities, targets)
        return IsotonicCalibrator(model)
    raise ValueError(f"unknown calibration method: {method}")


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    return cast(np.ndarray, np.log(clipped / (1 - clipped)))


def _selection_key(row: dict[str, Any]) -> tuple[float, float, float]:
    metrics = row["metrics"]
    return (
        float(metrics["brier_score"]),
        float(metrics["log_loss"]),
        float(metrics["expected_calibration_error"]),
    )
