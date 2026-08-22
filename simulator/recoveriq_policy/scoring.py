from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from recoveriq_ml.calibration import ProbabilityCalibrator, load_calibrators
from recoveriq_ml.features import snapshot_for_action
from recoveriq_ml.models import (
    CATEGORICAL_FEATURES,
    HEALTH_FEATURES,
    MODEL_FEATURE_ALLOWLIST,
)
from recoveriq_ml.training import load_models, predict_probabilities
from recoveriq_policy.config import (
    MIN_ACTION_TRAINING_SUPPORT,
    MIN_CALIBRATION_BIN_SUPPORT,
)
from recoveriq_policy.models import (
    CandidateAction,
    CandidatePrediction,
    PolicyDecisionContext,
    SupportDiagnostic,
)


class FrozenRecoveryModelScorer:
    def __init__(
        self,
        *,
        model_root: Path,
        calibration_root: Path,
        model_name: str = "lightgbm",
    ) -> None:
        if model_name not in {"lightgbm", "lightgbm_without_health"}:
            raise ValueError("policy scoring is limited to frozen LightGBM artifacts")
        models = load_models(model_root)
        calibrators = load_calibrators(calibration_root)
        self.model_name = model_name
        self.model: Pipeline = models[model_name]
        self.calibrator: ProbabilityCalibrator = calibrators[model_name]
        self.features = [
            name
            for name in MODEL_FEATURE_ALLOWLIST
            if model_name != "lightgbm_without_health" or name not in HEALTH_FEATURES
        ]
        model_manifest = json.loads(
            (model_root / "model-manifest-v1.json").read_text(encoding="utf-8")
        )
        calibration_manifest = json.loads(
            (calibration_root / "calibration-manifest-v1.json").read_text(encoding="utf-8")
        )
        self.action_counts = {
            str(name): int(count) for name, count in model_manifest["action_counts"].items()
        }
        bins = calibration_manifest["calibrated_metrics"][model_name]["reliability_bins"]
        self.calibration_bin_counts = {int(row["bin"]): int(row["count"]) for row in bins}
        self.known_categories = self._known_categories()

    def score_contexts(
        self,
        contexts: tuple[PolicyDecisionContext, ...],
        actions_by_context: tuple[tuple[CandidateAction, ...], ...],
    ) -> dict[str, tuple[CandidatePrediction, ...]]:
        if len(contexts) != len(actions_by_context):
            raise ValueError("context/action collections are not aligned")
        pairs = [
            (context, action)
            for context, actions in zip(contexts, actions_by_context, strict=True)
            for action in actions
        ]
        rows = [
            snapshot_for_action(context.base_features, action.recovery_action).model_features()
            for context, action in pairs
        ]
        frame = pd.DataFrame(rows)
        raw = predict_probabilities(self.model, frame[self.features])
        calibrated = self.calibrator.transform(raw)
        output: dict[str, list[CandidatePrediction]] = {
            context.decision_key: [] for context in contexts
        }
        for index, (context, action) in enumerate(pairs):
            features = rows[index]
            probability = float(calibrated[index])
            bin_index = min(int(probability * 10), 9)
            action_count = self.action_counts.get(action.recovery_action.action_type.value, 0)
            unknown = tuple(
                name
                for name in CATEGORICAL_FEATURES
                if name in self.features
                and str(features[name]) not in self.known_categories.get(name, frozenset())
            )
            reasons: list[str] = []
            bin_count = self.calibration_bin_counts.get(bin_index, 0)
            if action_count < MIN_ACTION_TRAINING_SUPPORT:
                reasons.append("ACTION_TRAINING_SUPPORT")
            if bin_count < MIN_CALIBRATION_BIN_SUPPORT:
                reasons.append("CALIBRATION_BIN_SUPPORT")
            if unknown:
                reasons.append("UNKNOWN_CATEGORICAL_VALUE")
            output[context.decision_key].append(
                CandidatePrediction(
                    candidate=action,
                    raw_probability=Decimal(str(float(raw[index]))),
                    calibrated_probability=Decimal(str(probability)),
                    support=SupportDiagnostic(
                        action_training_count=action_count,
                        calibration_bin=bin_index,
                        calibration_bin_count=bin_count,
                        unknown_categories=unknown,
                        low_support=bool(reasons),
                        reasons=tuple(reasons),
                    ),
                    model_name=self.model_name,
                )
            )
        return {key: tuple(value) for key, value in output.items()}

    def _known_categories(self) -> dict[str, frozenset[str]]:
        preprocessor = self.model.named_steps["preprocessor"]
        categorical = preprocessor.named_transformers_["categorical"]
        onehot = categorical.named_steps["onehot"]
        categorical_names = [name for name in self.features if name in CATEGORICAL_FEATURES]
        return {
            name: frozenset(str(value) for value in values)
            for name, values in zip(categorical_names, onehot.categories_, strict=True)
        }


def probabilities_array(predictions: tuple[CandidatePrediction, ...]) -> np.ndarray:
    return np.asarray([float(item.calibrated_probability) for item in predictions], dtype=float)
