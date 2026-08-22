from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from recoveriq_ml.cli import main
from recoveriq_ml.config import (
    LIGHTGBM_DEVELOPMENT_CANDIDATES,
    ML_CALIBRATION_SEEDS,
    ML_DEVELOPMENT_SEEDS,
    ML_HELDOUT_TEST_SEEDS,
    ML_TRAINING_SEEDS,
    OVERALL_FINAL_SEEDS,
)
from recoveriq_ml.models import (
    FEATURE_SCHEMA_HASH,
    HEALTH_FEATURES,
    MODEL_FEATURE_ALLOWLIST,
    FrozenModelManifest,
)
from recoveriq_ml.training import (
    build_lightgbm_pipeline,
    predict_probabilities,
    validate_model_frame,
)


def _synthetic_frame(rows: int = 120) -> pd.DataFrame:
    values: list[dict[str, object]] = []
    for index in range(rows):
        row: dict[str, object] = {}
        for name in MODEL_FEATURE_ALLOWLIST:
            if name == "payment_method":
                row[name] = ("UPI", "CARD")[index % 2]
            elif name == "issuer":
                row[name] = f"ISSUER_{index % 4}"
            elif name == "failure_reason":
                row[name] = ("ISSUER_UNAVAILABLE", "INSUFFICIENT_FUNDS")[index % 2]
            elif name == "failure_source":
                row[name] = ("ISSUER", "CUSTOMER")[index % 2]
            elif name == "action_type":
                row[name] = ("RETRY_NOW", "SEND_NUDGE", "RETRY_LATER")[index % 3]
            elif name.startswith("health_") and "available" not in name:
                row[name] = float(index % 7) / 10
            elif name.startswith("health_") or name.endswith("_action"):
                row[name] = bool(index % 2)
            else:
                row[name] = float(index % 11)
        row["selection_propensity"] = 1 / 6
        row["candidate_count"] = 9
        row["recovered_within_48h"] = int(index % 4 == 0 or index % 9 == 0)
        values.append(row)
    return pd.DataFrame(values)


def test_ml_seed_groups_are_preregistered_disjoint_and_final_is_untouched() -> None:
    assert tuple(range(20_270_101, 20_270_121)) == ML_TRAINING_SEEDS
    assert tuple(range(20_270_201, 20_270_211)) == ML_DEVELOPMENT_SEEDS
    assert tuple(range(20_270_301, 20_270_311)) == ML_CALIBRATION_SEEDS
    assert tuple(range(20_270_401, 20_270_411)) == ML_HELDOUT_TEST_SEEDS
    groups = (
        set(ML_TRAINING_SEEDS),
        set(ML_DEVELOPMENT_SEEDS),
        set(ML_CALIBRATION_SEEDS),
        set(ML_HELDOUT_TEST_SEEDS),
        set(OVERALL_FINAL_SEEDS),
    )
    for index, group in enumerate(groups):
        assert all(not group & other for other in groups[index + 1 :])


def test_normal_replay_rejects_calibration_heldout_and_final(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    for seed in (
        ML_CALIBRATION_SEEDS[0],
        ML_HELDOUT_TEST_SEEDS[0],
        OVERALL_FINAL_SEEDS[0],
    ):
        assert main(["--artifact-root", str(tmp_path), "replay-seed", "--seed", str(seed)]) == 2
        assert capsys.readouterr().err


def test_heldout_requires_frozen_model_and_calibration(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--artifact-root", str(tmp_path), "evaluate-heldout"]) == 2
    assert "must be frozen" in capsys.readouterr().err


def test_heldout_refuses_overwrite_without_replaying(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    output = tmp_path / "reports" / "heldout-evaluation-v1.json"
    output.parent.mkdir(parents=True)
    output.write_text("{}", encoding="utf-8")
    assert main(["--artifact-root", str(tmp_path), "evaluate-heldout"]) == 2
    assert "refusing a second run" in capsys.readouterr().err


def test_lightgbm_training_is_deterministic() -> None:
    frame = _synthetic_frame()
    features = list(MODEL_FEATURE_ALLOWLIST)
    target = frame["recovered_within_48h"]
    first = build_lightgbm_pipeline(LIGHTGBM_DEVELOPMENT_CANDIDATES[0], features)
    second = build_lightgbm_pipeline(LIGHTGBM_DEVELOPMENT_CANDIDATES[0], features)
    first.fit(frame[features], target)
    second.fit(frame[features], target)
    assert np.array_equal(
        predict_probabilities(first, frame[features]),
        predict_probabilities(second, frame[features]),
    )


def test_invalid_feature_schema_is_rejected_at_training_and_inference() -> None:
    frame = _synthetic_frame()
    validate_model_frame(frame)
    invalid = frame.drop(columns=[MODEL_FEATURE_ALLOWLIST[0]])
    with pytest.raises(ValueError, match="missing frozen features"):
        validate_model_frame(invalid)
    features = list(MODEL_FEATURE_ALLOWLIST)
    model = build_lightgbm_pipeline(LIGHTGBM_DEVELOPMENT_CANDIDATES[0], features)
    model.fit(frame[features], frame["recovered_within_48h"])
    with pytest.raises(ValueError, match="frozen model schema"):
        predict_probabilities(model, frame[features].drop(columns=[features[-1]]))


def test_model_manifest_requires_schema_version_and_provenance() -> None:
    required = {
        "model_version",
        "feature_schema_version",
        "feature_schema_hash",
        "training_seeds",
        "development_seeds",
        "selected_lightgbm_hyperparameters",
        "model_sha256",
        "software_versions",
    }
    assert required <= set(FrozenModelManifest.model_fields)
    assert len(FEATURE_SCHEMA_HASH) == 64


def test_shap_feature_space_cannot_include_identity_or_hidden_columns() -> None:
    forbidden = {
        "customer_id",
        "payment_id",
        "subscription_id",
        "merchant_id",
        "seed",
        "true_failure_cause",
        "incident_id",
        "oracle_probability",
    }
    assert set(MODEL_FEATURE_ALLOWLIST).isdisjoint(forbidden)
    assert set(HEALTH_FEATURES) <= set(MODEL_FEATURE_ALLOWLIST)


def test_recovery_model_document_preserves_preregistration_and_reports_results() -> None:
    repository = Path(__file__).resolve().parents[2]
    document = (repository / "docs" / "RECOVERY_MODEL.md").read_text(encoding="utf-8")
    for value in ("20270101", "20270201", "20270301", "20270401", "0.05", "0.15"):
        assert value in document
    assert "pre-registration before any Phase 4 seed was generated" in document
    assert "calibration safety gate **PASSED**" in document
    assert "Payment-health features did **not** improve" in document
    json.dumps({"feature_schema_hash": FEATURE_SCHEMA_HASH})
