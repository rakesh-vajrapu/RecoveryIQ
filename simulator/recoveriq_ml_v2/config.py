from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from recoveriq_sequential.config import (
    MODEL_V2_CALIBRATION_SEEDS,
    MODEL_V2_DEVELOPMENT_SEEDS,
    MODEL_V2_HELDOUT_SEEDS,
    OVERALL_FINAL_SEEDS,
    SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
    SEQUENTIAL_POLICY_VALIDATION_SEEDS,
    SEQUENTIAL_TRAINING_SEEDS,
)

MODEL_V2_RANDOM_STATE = 20_270_800
MIN_ACTION_STAGE_SUPPORT = 500
MIN_CALIBRATION_BIN_SUPPORT = 100
MODEL_V2_MAX_ECE = 0.05
LATER_DECISION_MAX_ECE = 0.10
LATER_DECISION_MAX_BRIER = 0.30
LATER_DECISION_MIN_ROWS = 500
MIN_PAIRWISE_RANKING = 0.55


class LightGBMV2Candidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    num_leaves: int = Field(ge=2)
    learning_rate: float = Field(gt=0, le=1)
    max_depth: int = Field(ge=1)
    min_child_samples: int = Field(ge=1)
    colsample_bytree: float = Field(gt=0, le=1)
    subsample: float = Field(gt=0, le=1)
    reg_alpha: float = Field(ge=0)
    reg_lambda: float = Field(ge=0)
    n_estimators: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_leaf_depth(self) -> LightGBMV2Candidate:
        if self.num_leaves > 2**self.max_depth:
            raise ValueError("num_leaves exceeds maximum tree depth")
        return self


LIGHTGBM_V2_DEVELOPMENT_CANDIDATES = (
    LightGBMV2Candidate(
        num_leaves=15,
        learning_rate=0.05,
        max_depth=5,
        min_child_samples=80,
        colsample_bytree=0.8,
        subsample=1.0,
        reg_alpha=0.0,
        reg_lambda=1.0,
        n_estimators=200,
    ),
    LightGBMV2Candidate(
        num_leaves=31,
        learning_rate=0.05,
        max_depth=8,
        min_child_samples=80,
        colsample_bytree=0.8,
        subsample=1.0,
        reg_alpha=0.1,
        reg_lambda=1.0,
        n_estimators=200,
    ),
    LightGBMV2Candidate(
        num_leaves=15,
        learning_rate=0.03,
        max_depth=5,
        min_child_samples=40,
        colsample_bytree=1.0,
        subsample=1.0,
        reg_alpha=0.0,
        reg_lambda=2.0,
        n_estimators=350,
    ),
    LightGBMV2Candidate(
        num_leaves=31,
        learning_rate=0.03,
        max_depth=8,
        min_child_samples=40,
        colsample_bytree=1.0,
        subsample=1.0,
        reg_alpha=0.1,
        reg_lambda=2.0,
        n_estimators=350,
    ),
)

__all__ = [
    "LIGHTGBM_V2_DEVELOPMENT_CANDIDATES",
    "MODEL_V2_CALIBRATION_SEEDS",
    "MODEL_V2_DEVELOPMENT_SEEDS",
    "MODEL_V2_HELDOUT_SEEDS",
    "OVERALL_FINAL_SEEDS",
    "SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS",
    "SEQUENTIAL_POLICY_VALIDATION_SEEDS",
    "SEQUENTIAL_TRAINING_SEEDS",
]
