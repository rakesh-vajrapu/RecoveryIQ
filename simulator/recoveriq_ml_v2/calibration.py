from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

import joblib
import pandas as pd

from recoveriq_ml.artifacts import sha256_file, write_json
from recoveriq_ml.calibration import ProbabilityCalibrator, fit_calibrator
from recoveriq_ml.metrics import binary_probability_metrics
from recoveriq_ml_v2.config import MODEL_V2_CALIBRATION_SEEDS
from recoveriq_ml_v2.models import FEATURE_SCHEMA_V2_HASH, MODEL_V2_FEATURE_ALLOWLIST
from recoveriq_ml_v2.training import (
    TARGET_COLUMN,
    load_model_v2,
    predict_v2_probabilities,
)

CALIBRATOR_V2_FILENAMES = {
    "logistic": "logistic-calibrator-v2.joblib",
    "lightgbm": "lightgbm-calibrator-v2.joblib",
}


def fit_and_freeze_calibration_v2(
    *,
    calibration: pd.DataFrame,
    model_root: Path,
    calibration_root: Path,
) -> dict[str, Any]:
    output = calibration_root / "calibration-manifest-v2.json"
    if output.exists():
        raise FileExistsError("Recovery Model V2 calibration is already frozen")
    started = perf_counter()
    models = load_model_v2(model_root)
    features = list(MODEL_V2_FEATURE_ALLOWLIST)
    target = calibration[TARGET_COLUMN].astype(int).to_numpy()
    raw = {
        name: predict_v2_probabilities(model, calibration[features])
        for name, model in models.items()
    }
    candidates: list[dict[str, Any]] = []
    for method in ("sigmoid", "isotonic"):
        calibrator = fit_calibrator(method, raw["lightgbm"], target)
        candidates.append(
            {
                "method": method,
                "metrics": binary_probability_metrics(
                    target, calibrator.transform(raw["lightgbm"])
                ),
            }
        )
    selected = min(candidates, key=_selection_key)
    selected_method = str(selected["method"])
    calibration_root.mkdir(parents=True, exist_ok=True)
    mappings: dict[str, dict[str, str]] = {}
    calibrated_metrics: dict[str, Any] = {}
    for name, probabilities in raw.items():
        calibrator = fit_calibrator(selected_method, probabilities, target)
        path = calibration_root / CALIBRATOR_V2_FILENAMES[name]
        joblib.dump(calibrator, path, compress=3)
        mappings[name] = {"artifact": path.name, "sha256": sha256_file(path)}
        calibrated_metrics[name] = binary_probability_metrics(
            target, calibrator.transform(probabilities)
        )
    report = {
        "phase": "model_v2_calibration_selection_and_freeze",
        "feature_schema_hash": FEATURE_SCHEMA_V2_HASH,
        "calibration_seeds": MODEL_V2_CALIBRATION_SEEDS,
        "selection_rule": "minimum Brier, then log loss, then ECE",
        "primary_method_candidates": candidates,
        "selected_method": selected_method,
        "calibration_mappings": mappings,
        "raw_metrics": {
            name: binary_probability_metrics(target, values) for name, values in raw.items()
        },
        "calibrated_metrics": calibrated_metrics,
        "runtime_seconds": perf_counter() - started,
    }
    write_json(output, report)
    return report


def load_calibrators_v2(calibration_root: Path) -> dict[str, ProbabilityCalibrator]:
    return {
        name: joblib.load(calibration_root / filename)
        for name, filename in CALIBRATOR_V2_FILENAMES.items()
    }


def _selection_key(row: dict[str, Any]) -> tuple[float, float, float]:
    metrics = row["metrics"]
    return (
        float(metrics["brier_score"]),
        float(metrics["log_loss"]),
        float(metrics["expected_calibration_error"]),
    )
