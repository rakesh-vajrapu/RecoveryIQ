from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from recoveriq_ml.calibration import ProbabilityCalibrator
from recoveriq_ml_v2.calibration import load_calibrators_v2
from recoveriq_ml_v2.features import build_feature_snapshot_v2
from recoveriq_ml_v2.models import MODEL_V2_FEATURE_ALLOWLIST
from recoveriq_ml_v2.training import load_model_v2, predict_v2_probabilities
from recoveriq_sequential.models import (
    SequentialCandidate,
    SequentialEpisodeState,
    SequentialEpisodeTemplate,
)
from recoveriq_sequential_policy.models import SequentialCandidateScore


class SequentialModelV2Scorer:
    def __init__(
        self,
        *,
        model_root: Path,
        calibration_root: Path,
    ) -> None:
        self.model = load_model_v2(model_root)["lightgbm"]
        self.calibrator: ProbabilityCalibrator = load_calibrators_v2(calibration_root)["lightgbm"]
        model_manifest = json.loads(
            (model_root / "model-manifest-v2.json").read_text(encoding="utf-8")
        )
        calibration_manifest = json.loads(
            (calibration_root / "calibration-manifest-v2.json").read_text(encoding="utf-8")
        )
        self.action_stage_support = {
            str(key): int(value) for key, value in model_manifest["action_stage_counts"].items()
        }
        reliability = calibration_manifest["calibrated_metrics"]["lightgbm"]["reliability_bins"]
        self.calibration_bin_support = {int(row["bin"]): int(row["count"]) for row in reliability}

    def score(
        self,
        rows: list[tuple[SequentialEpisodeTemplate, SequentialEpisodeState, SequentialCandidate]],
    ) -> list[SequentialCandidateScore]:
        if not rows:
            return []
        snapshots = [
            build_feature_snapshot_v2(template, state, candidate)
            for template, state, candidate in rows
        ]
        frame = pd.DataFrame(snapshot.model_features() for snapshot in snapshots)
        raw = predict_v2_probabilities(self.model, frame[list(MODEL_V2_FEATURE_ALLOWLIST)])
        probabilities = np.asarray(self.calibrator.transform(raw), dtype=float)
        scores: list[SequentialCandidateScore] = []
        for (template, state, candidate), probability in zip(rows, probabilities, strict=True):
            action = candidate.recovery_action
            amount = template.observation.amount_minor
            expected_value = int(
                (Decimal(str(float(probability))) * Decimal(amount)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            incremental_erv = (
                expected_value - action.intervention_cost_minor - action.friction_cost_minor
            )
            calibration_bin = min(int(float(probability) * 10), 9)
            scores.append(
                SequentialCandidateScore(
                    candidate=candidate,
                    probability=float(probability),
                    incremental_erv_minor=incremental_erv,
                    normalized_erv=incremental_erv / amount,
                    action_stage_support=self.action_stage_support.get(
                        f"{candidate.label}|{state.decision_index}", 0
                    ),
                    calibration_bin=calibration_bin,
                    calibration_bin_support=self.calibration_bin_support.get(calibration_bin, 0),
                )
            )
        return scores
