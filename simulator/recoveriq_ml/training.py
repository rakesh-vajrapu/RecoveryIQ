from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from recoveriq_ml import FEATURE_SCHEMA_VERSION, RECOVERY_MODEL_VERSION
from recoveriq_ml.artifacts import sha256_file, software_versions, write_json
from recoveriq_ml.config import (
    LIGHTGBM_DEVELOPMENT_CANDIDATES,
    ML_DEVELOPMENT_SEEDS,
    ML_TRAINING_SEEDS,
    MODEL_RANDOM_STATE,
    LightGBMCandidate,
)
from recoveriq_ml.metrics import binary_probability_metrics
from recoveriq_ml.models import (
    CATEGORICAL_FEATURES,
    FEATURE_SCHEMA_HASH,
    HEALTH_FEATURES,
    MODEL_FEATURE_ALLOWLIST,
    FrozenModelManifest,
)

MODEL_FILENAMES = {
    "logistic": "logistic-regression-v1.joblib",
    "lightgbm": "lightgbm-v1.joblib",
    "lightgbm_without_health": "lightgbm-without-health-v1.joblib",
}


def train_and_freeze_models(
    training: pd.DataFrame,
    development: pd.DataFrame,
    model_root: Path,
) -> dict[str, Any]:
    validate_model_frame(training)
    validate_model_frame(development)
    started = perf_counter()
    all_features = list(MODEL_FEATURE_ALLOWLIST)
    without_health = [name for name in all_features if name not in HEALTH_FEATURES]
    y_train = training["recovered_within_48h"].astype(int)
    y_development = development["recovered_within_48h"].astype(int)

    logistic = build_logistic_pipeline(all_features)
    logistic.fit(training[all_features], y_train)
    logistic_metrics = binary_probability_metrics(
        y_development,
        predict_probabilities(logistic, development[all_features]),
    )

    candidate_rows: list[dict[str, Any]] = []
    fitted_candidates: list[Pipeline] = []
    for index, candidate in enumerate(LIGHTGBM_DEVELOPMENT_CANDIDATES):
        pipeline = build_lightgbm_pipeline(candidate, all_features)
        pipeline.fit(training[all_features], y_train)
        metrics = binary_probability_metrics(
            y_development,
            predict_probabilities(pipeline, development[all_features]),
        )
        fitted_candidates.append(pipeline)
        candidate_rows.append(
            {
                "candidate_index": index,
                "hyperparameters": candidate.model_dump(mode="json"),
                "metrics": metrics,
            }
        )
    chosen_row = min(candidate_rows, key=_selection_key)
    chosen_index = int(chosen_row["candidate_index"])
    lightgbm = fitted_candidates[chosen_index]
    chosen_config = LIGHTGBM_DEVELOPMENT_CANDIDATES[chosen_index]

    lightgbm_without_health = build_lightgbm_pipeline(chosen_config, without_health)
    lightgbm_without_health.fit(training[without_health], y_train)
    without_health_metrics = binary_probability_metrics(
        y_development,
        predict_probabilities(lightgbm_without_health, development[without_health]),
    )

    model_root.mkdir(parents=True, exist_ok=True)
    models = {
        "logistic": logistic,
        "lightgbm": lightgbm,
        "lightgbm_without_health": lightgbm_without_health,
    }
    paths: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for name, model in models.items():
        path = model_root / MODEL_FILENAMES[name]
        joblib.dump(model, path, compress=3)
        paths[name] = path.name
        hashes[name] = sha256_file(path)

    action_counts = training["action_type"].value_counts().sort_index().astype(int).to_dict()
    report = {
        "phase": "model_development_selection",
        "selection_rule": "minimum Brier, then log loss, then ECE",
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "training_prevalence": float(y_train.mean()),
        "training_example_count": len(training),
        "development_example_count": len(development),
        "action_counts": action_counts,
        "logistic_regression": logistic_metrics,
        "lightgbm_candidates": candidate_rows,
        "selected_lightgbm_candidate_index": chosen_index,
        "selected_lightgbm": chosen_row["metrics"],
        "selected_lightgbm_without_health": without_health_metrics,
        "runtime_seconds": perf_counter() - started,
    }
    manifest = FrozenModelManifest(
        model_version=RECOVERY_MODEL_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_schema_hash=FEATURE_SCHEMA_HASH,
        training_seeds=ML_TRAINING_SEEDS,
        development_seeds=ML_DEVELOPMENT_SEEDS,
        selected_lightgbm_candidate_index=chosen_index,
        selected_lightgbm_hyperparameters=chosen_config.model_dump(mode="json"),
        model_artifacts=paths,
        model_sha256=hashes,
        development_metrics=report,
        training_example_count=len(training),
        action_counts=action_counts,
        training_timestamp=datetime.now(UTC),
        software_versions=software_versions(),
    )
    write_json(model_root / "model-manifest-v1.json", manifest.model_dump(mode="json"))
    write_json(model_root.parent.parent / "reports" / "development-selection-v1.json", report)
    return report


def load_models(model_root: Path) -> dict[str, Pipeline]:
    return {name: joblib.load(model_root / filename) for name, filename in MODEL_FILENAMES.items()}


def build_logistic_pipeline(features: list[str]) -> Pipeline:
    numeric, categorical = _split_features(features)
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )
    return Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1_000,
                    random_state=MODEL_RANDOM_STATE,
                    solver="lbfgs",
                ),
            ),
        ]
    )


def build_lightgbm_pipeline(
    candidate: LightGBMCandidate,
    features: list[str],
) -> Pipeline:
    numeric, categorical = _split_features(features)
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                SimpleImputer(strategy="median", add_indicator=True),
                numeric,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )
    classifier = LGBMClassifier(
        objective="binary",
        random_state=MODEL_RANDOM_STATE,
        n_jobs=1,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
        importance_type="gain",
        **candidate.model_dump(mode="python"),
    )
    return Pipeline([("preprocessor", preprocessor), ("classifier", classifier)])


def predict_probabilities(model: Pipeline, frame: pd.DataFrame) -> np.ndarray:
    expected = tuple(str(name) for name in model.feature_names_in_)
    if tuple(frame.columns) != expected:
        raise ValueError("inference feature columns do not match the frozen model schema")
    probabilities = model.predict_proba(frame)
    return np.asarray(probabilities[:, 1], dtype=float)


def model_feature_names(model: Pipeline) -> list[str]:
    preprocessor = model.named_steps["preprocessor"]
    return [str(name) for name in preprocessor.get_feature_names_out()]


def _split_features(features: list[str]) -> tuple[list[str], list[str]]:
    categorical = [name for name in features if name in CATEGORICAL_FEATURES]
    numeric = [name for name in features if name not in categorical]
    return numeric, categorical


def _selection_key(row: dict[str, Any]) -> tuple[float, float, float]:
    metrics = row["metrics"]
    return (
        float(metrics["brier_score"]),
        float(metrics["log_loss"]),
        float(metrics["expected_calibration_error"]),
    )


def validate_model_frame(frame: pd.DataFrame) -> None:
    missing = set(MODEL_FEATURE_ALLOWLIST) - set(frame.columns)
    if missing:
        raise ValueError(f"model frame is missing frozen features: {sorted(missing)}")
    forbidden = {
        "customer_id",
        "payment_id",
        "subscription_id",
        "event_id",
        "merchant_id",
        "seed",
        "true_failure_cause",
        "incident_id",
        "instrument_state",
        "oracle_probability",
        "counterfactual_outcome",
    }
    present = forbidden & set(frame.columns)
    if present:
        raise ValueError(f"forbidden leakage columns present: {sorted(present)}")
