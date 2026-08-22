from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from recoveriq_ml.artifacts import sha256_file, software_versions, write_json
from recoveriq_ml.metrics import binary_probability_metrics
from recoveriq_ml_v2 import FEATURE_SCHEMA_V2_VERSION, RECOVERY_MODEL_V2_VERSION
from recoveriq_ml_v2.config import (
    LIGHTGBM_V2_DEVELOPMENT_CANDIDATES,
    MODEL_V2_DEVELOPMENT_SEEDS,
    MODEL_V2_RANDOM_STATE,
    SEQUENTIAL_TRAINING_SEEDS,
    LightGBMV2Candidate,
)
from recoveriq_ml_v2.models import (
    FEATURE_SCHEMA_V2_HASH,
    MODEL_V2_CATEGORICAL_FEATURES,
    MODEL_V2_FEATURE_ALLOWLIST,
    FrozenModelV2Manifest,
)

MODEL_V2_FILENAMES = {
    "logistic": "logistic-regression-v2.joblib",
    "lightgbm": "lightgbm-v2.joblib",
}
TARGET_COLUMN = "action_recovered_before_next_decision"


def train_and_freeze_model_v2(
    *,
    training: pd.DataFrame,
    development: pd.DataFrame,
    model_root: Path,
    report_root: Path,
) -> dict[str, Any]:
    validate_model_v2_frame(training)
    validate_model_v2_frame(development)
    output = model_root / "model-manifest-v2.json"
    if output.exists():
        raise FileExistsError("Recovery Model V2 is already frozen")
    started = perf_counter()
    features = list(MODEL_V2_FEATURE_ALLOWLIST)
    y_train = training[TARGET_COLUMN].astype(int)
    y_development = development[TARGET_COLUMN].astype(int)

    logistic = build_logistic_v2_pipeline(features)
    logistic.fit(training[features], y_train)
    logistic_metrics = binary_probability_metrics(
        y_development,
        predict_v2_probabilities(logistic, development[features]),
    )

    candidates: list[dict[str, Any]] = []
    fitted: list[Pipeline] = []
    for index, candidate in enumerate(LIGHTGBM_V2_DEVELOPMENT_CANDIDATES):
        pipeline = build_lightgbm_v2_pipeline(candidate, features)
        pipeline.fit(training[features], y_train)
        metrics = binary_probability_metrics(
            y_development,
            predict_v2_probabilities(pipeline, development[features]),
        )
        fitted.append(pipeline)
        candidates.append(
            {
                "candidate_index": index,
                "hyperparameters": candidate.model_dump(mode="json"),
                "metrics": metrics,
            }
        )
    selected = min(candidates, key=_selection_key)
    selected_index = int(selected["candidate_index"])
    lightgbm = fitted[selected_index]
    selected_config = LIGHTGBM_V2_DEVELOPMENT_CANDIDATES[selected_index]

    model_root.mkdir(parents=True, exist_ok=True)
    models = {"logistic": logistic, "lightgbm": lightgbm}
    paths: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for name, model in models.items():
        path = model_root / MODEL_V2_FILENAMES[name]
        joblib.dump(model, path, compress=3)
        paths[name] = path.name
        hashes[name] = sha256_file(path)
    action_stage_counts: dict[str, int] = {}
    grouped_support = training.groupby(["selected_action_label", "decision_index"]).size()
    for group_key, count in grouped_support.items():
        action, decision_index = cast(tuple[str, int], group_key)
        action_stage_counts[f"{action}|{decision_index}"] = int(count)
    report = {
        "phase": "model_v2_development_selection",
        "primary_hypothesis": "NO_HEALTH_TABULAR_LIGHTGBM",
        "selection_rule": "minimum Brier, then log loss, then ECE",
        "feature_schema_hash": FEATURE_SCHEMA_V2_HASH,
        "training_prevalence": float(y_train.mean()),
        "training_decision_count": len(training),
        "training_episode_count": int(training["episode_id"].nunique()),
        "development_decision_count": len(development),
        "development_episode_count": int(development["episode_id"].nunique()),
        "logistic_regression": logistic_metrics,
        "lightgbm_candidates": candidates,
        "selected_lightgbm_candidate_index": selected_index,
        "selected_lightgbm": selected["metrics"],
        "runtime_seconds": perf_counter() - started,
    }
    manifest = FrozenModelV2Manifest(
        model_version=RECOVERY_MODEL_V2_VERSION,
        feature_schema_version=FEATURE_SCHEMA_V2_VERSION,
        feature_schema_hash=FEATURE_SCHEMA_V2_HASH,
        training_seeds=SEQUENTIAL_TRAINING_SEEDS,
        development_seeds=MODEL_V2_DEVELOPMENT_SEEDS,
        selected_lightgbm_candidate_index=selected_index,
        selected_lightgbm_hyperparameters=selected_config.model_dump(mode="json"),
        model_artifacts=paths,
        model_sha256=hashes,
        development_metrics=report,
        training_decision_count=len(training),
        training_episode_count=int(training["episode_id"].nunique()),
        action_stage_counts=action_stage_counts,
        training_timestamp=datetime.now(UTC),
        software_versions=software_versions(),
    )
    write_json(output, manifest.model_dump(mode="json"))
    write_json(report_root / "development-selection-v2.json", report)
    return report


def validate_model_v2_frame(frame: pd.DataFrame) -> None:
    missing = set(MODEL_V2_FEATURE_ALLOWLIST) - set(frame.columns)
    if missing:
        raise ValueError(f"Model V2 frame is missing frozen features: {sorted(missing)}")
    forbidden = {
        "seed",
        "customer_id",
        "payment_id",
        "subscription_id",
        "merchant_id",
        "true_failure_cause",
        "hidden_failure_family",
        "incident_id",
        "instrument_state",
        "oracle_probability",
        "counterfactual_outcome",
    }
    present = forbidden & set(MODEL_V2_FEATURE_ALLOWLIST)
    if present:
        raise ValueError(f"forbidden Model V2 features: {sorted(present)}")
    health = [name for name in MODEL_V2_FEATURE_ALLOWLIST if name.startswith("health_")]
    if health:
        raise ValueError(f"primary Model V2 includes health features: {health}")
    if TARGET_COLUMN not in frame:
        raise ValueError("Model V2 target is absent")


def build_logistic_v2_pipeline(features: list[str]) -> Pipeline:
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
                    random_state=MODEL_V2_RANDOM_STATE,
                    solver="lbfgs",
                ),
            ),
        ]
    )


def build_lightgbm_v2_pipeline(
    candidate: LightGBMV2Candidate,
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
        random_state=MODEL_V2_RANDOM_STATE,
        n_jobs=1,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
        importance_type="gain",
        **candidate.model_dump(mode="python"),
    )
    return Pipeline([("preprocessor", preprocessor), ("classifier", classifier)])


def load_model_v2(model_root: Path) -> dict[str, Pipeline]:
    return {
        name: joblib.load(model_root / filename) for name, filename in MODEL_V2_FILENAMES.items()
    }


def predict_v2_probabilities(model: Pipeline, frame: pd.DataFrame) -> np.ndarray:
    expected = tuple(str(name) for name in model.feature_names_in_)
    if tuple(frame.columns) != expected:
        raise ValueError("Model V2 inference columns do not match frozen schema")
    probabilities = model.predict_proba(frame)
    return np.asarray(probabilities[:, 1], dtype=float)


def _split_features(features: list[str]) -> tuple[list[str], list[str]]:
    categorical = [name for name in features if name in MODEL_V2_CATEGORICAL_FEATURES]
    numeric = [name for name in features if name not in categorical]
    return numeric, categorical


def _selection_key(row: dict[str, Any]) -> tuple[float, float, float]:
    metrics = row["metrics"]
    return (
        float(metrics["brier_score"]),
        float(metrics["log_loss"]),
        float(metrics["expected_calibration_error"]),
    )
