from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

ML_TRAINING_SEEDS = tuple(range(20_270_101, 20_270_121))
ML_DEVELOPMENT_SEEDS = tuple(range(20_270_201, 20_270_211))
ML_CALIBRATION_SEEDS = tuple(range(20_270_301, 20_270_311))
ML_HELDOUT_TEST_SEEDS = tuple(range(20_270_401, 20_270_411))
OVERALL_FINAL_SEEDS = tuple(range(20_261_101, 20_261_121))

TARGET_HORIZON_HOURS = 48
RETRY_LATER_DELAYS_HOURS = (2.0, 6.0, 12.0, 24.0)
MODEL_RANDOM_STATE = 20_270_100

CALIBRATION_MAX_ECE = 0.05
CALIBRATION_MAX_RELIABILITY_GAP = 0.15
CALIBRATION_MIN_RELIABILITY_BIN_COUNT = 100
MODEL_MIN_PROBABILITY_IMPROVEMENT = 0.0001


class LightGBMCandidate(BaseModel):
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
    def validate_leaf_depth(self) -> LightGBMCandidate:
        if self.num_leaves > 2**self.max_depth:
            raise ValueError("num_leaves cannot exceed the selected maximum tree depth")
        return self


LIGHTGBM_DEVELOPMENT_CANDIDATES: tuple[LightGBMCandidate, ...] = (
    LightGBMCandidate(
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
    LightGBMCandidate(
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
    LightGBMCandidate(
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
    LightGBMCandidate(
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
