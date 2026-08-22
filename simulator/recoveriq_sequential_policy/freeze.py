from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from recoveriq_ml.artifacts import sha256_file, write_json
from recoveriq_ml_v2 import RECOVERY_MODEL_V2_VERSION
from recoveriq_sequential.config import (
    EPISODE_HORIZON_HOURS,
    MAX_AUTONOMOUS_INTERVENTIONS,
    MAX_CONTACTS,
    MAX_RETRIES,
    MIN_RETRY_INTERVAL_HOURS,
    PRIMARY_COST_REGIME,
    SEQUENTIAL_CANDIDATE_LABELS,
    SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
    SEQUENTIAL_POLICY_VALIDATION_SEEDS,
)
from recoveriq_sequential_policy import SEQUENTIAL_POLICY_V2_VERSION
from recoveriq_sequential_policy.baselines import GLOBAL_MIN_SUPPORT, SIMPLE_MIN_SUPPORT
from recoveriq_sequential_policy.models import FrozenSequentialPolicy
from recoveriq_simulator.config import costs_for_regime

STOPPING_RULES = (
    "MAX_INTERVENTIONS",
    "MAX_RETRIES",
    "MAX_CONTACTS",
    "MIN_RETRY_INTERVAL",
    "CUSTOMER_OPT_OUT",
    "QUIET_HOURS_SCHEDULE",
    "DUPLICATE_PAYMENT_LINK",
    "RECOVERY_HORIZON",
    "ACTION_FEASIBILITY",
    "MODEL_SCHEMA_VALID",
    "MODEL_SUPPORT",
    "NON_POSITIVE_INCREMENTAL_ERV",
    "ATTRIBUTION_ONCE",
)


def freeze_sequential_policy(
    *,
    artifact_root: Path,
    model_root: Path,
    calibration_root: Path,
) -> FrozenSequentialPolicy:
    output = artifact_root / "recoveriq-sequential-policy-v2.json"
    if output.exists():
        raise FileExistsError("Sequential Policy V2 is already frozen")
    development: dict[str, Any] = json.loads(
        (artifact_root / "development-policy-v2.json").read_text(encoding="utf-8")
    )
    model: dict[str, Any] = json.loads(
        (model_root / "model-manifest-v2.json").read_text(encoding="utf-8")
    )
    calibration: dict[str, Any] = json.loads(
        (calibration_root / "calibration-manifest-v2.json").read_text(encoding="utf-8")
    )
    baseline_path = artifact_root / "development-baselines-v2.json"
    costs = costs_for_regime(PRIMARY_COST_REGIME).model_dump(mode="json")
    payload: dict[str, Any] = {
        "policy_version": SEQUENTIAL_POLICY_V2_VERSION,
        "model_version": RECOVERY_MODEL_V2_VERSION,
        "model_sha256": model["model_sha256"]["lightgbm"],
        "feature_schema_hash": model["feature_schema_hash"],
        "calibration_method": calibration["selected_method"],
        "calibration_sha256": calibration["calibration_mappings"]["lightgbm"]["sha256"],
        "candidate_labels": SEQUENTIAL_CANDIDATE_LABELS,
        "cost_regime": PRIMARY_COST_REGIME.value,
        "costs_minor": costs,
        "horizon_hours": EPISODE_HORIZON_HOURS,
        "max_interventions": MAX_AUTONOMOUS_INTERVENTIONS,
        "max_retries": MAX_RETRIES,
        "max_contacts": MAX_CONTACTS,
        "min_retry_interval_hours": MIN_RETRY_INTERVAL_HOURS,
        "action_stage_min_support": 500,
        "calibration_bin_min_support": 100,
        "normalized_erv_margin_threshold": development["selected_normalized_margin_threshold"],
        "stopping_rules": STOPPING_RULES,
        "development_seeds": SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
        "validation_seeds": SEQUENTIAL_POLICY_VALIDATION_SEEDS,
        "baseline_artifact": baseline_path.name,
        "baseline_sha256": sha256_file(baseline_path),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=list).encode()
    ).hexdigest()
    policy = FrozenSequentialPolicy(
        **payload,
        config_hash=digest,
        validation_status="FROZEN_NOT_RUN",
    )
    write_json(output, policy.model_dump(mode="json"))
    write_json(
        artifact_root / "policy-freeze-manifest-v2.json",
        {
            "artifact_type": "sequential_policy_v2_freeze",
            "policy_version": policy.policy_version,
            "policy_config_hash": policy.config_hash,
            "simple_baseline_min_support": SIMPLE_MIN_SUPPORT,
            "global_baseline_min_support": GLOBAL_MIN_SUPPORT,
            "validation_status": policy.validation_status,
        },
    )
    return policy
