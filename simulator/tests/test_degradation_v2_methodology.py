from __future__ import annotations

import hashlib
from pathlib import Path

from recoveriq_detector_v2.cli import main
from recoveriq_detector_v2.config import (
    DEVELOPMENT_CANDIDATES,
    FINAL_EVALUATION_SEEDS,
    HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY,
    HARD_POLICY_MIN_CONFIRMED_EPISODES,
    HARD_POLICY_MIN_PRECISION,
    HIGH_EVIDENCE_RULE,
    V1_CONSUMED_VALIDATION_SEEDS,
    V2_DEVELOPMENT_SEEDS,
    V2_VALIDATION_SEEDS,
)
from recoveriq_detector_v2.demo import DEMO_LABEL, run_v2_demo


def test_v2_seed_groups_are_pre_registered_and_disjoint() -> None:
    assert tuple(range(20_261_201, 20_261_211)) == V2_VALIDATION_SEEDS
    assert not set(V2_DEVELOPMENT_SEEDS) & set(V2_VALIDATION_SEEDS)
    assert not set(V1_CONSUMED_VALIDATION_SEEDS) & set(V2_VALIDATION_SEEDS)
    assert not set(FINAL_EVALUATION_SEEDS) & set(V2_VALIDATION_SEEDS)


def test_original_validation_is_not_a_v2_tuning_group() -> None:
    assert V1_CONSUMED_VALIDATION_SEEDS != V2_DEVELOPMENT_SEEDS
    assert V1_CONSUMED_VALIDATION_SEEDS != V2_VALIDATION_SEEDS


def test_high_evidence_and_safety_gate_are_non_outcome_based() -> None:
    assert set(type(HIGH_EVIDENCE_RULE).model_fields) == {
        "first_horizon_hours",
        "min_attempts_first_horizon",
        "baseline_lookback_days",
        "min_prior_baseline_attempts",
    }
    assert HARD_POLICY_MIN_PRECISION == 0.70
    assert HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY == 0.005
    assert HARD_POLICY_MIN_CONFIRMED_EPISODES == 5


def test_normal_commands_reject_consumed_validation_and_final_seeds(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    assert (
        main(
            [
                "--artifact-root",
                str(tmp_path),
                "replay",
                "--seed",
                str(V1_CONSUMED_VALIDATION_SEEDS[0]),
            ]
        )
        == 2
    )
    assert "forbidden" in capsys.readouterr().err
    assert (
        main(
            [
                "--artifact-root",
                str(tmp_path),
                "replay",
                "--seed",
                str(FINAL_EVALUATION_SEEDS[0]),
            ]
        )
        == 2
    )
    assert "MUST REMAIN UNTOUCHED" in capsys.readouterr().err


def test_v1_artifacts_remain_byte_reproducible() -> None:
    repository = Path(__file__).resolve().parents[2]
    expected = {
        "degradation-detector-v1.json": (
            "b1faea3bb3abfc3a808047dee8d7f4d0a9082cda65570a5a262085ceeeee35f9"
        ),
        "development-report-v1.md": (
            "eeffc002e1251b665b29bb46aea2049380501f91b5015498ec339ff325cdb795"
        ),
        "validation-report-v1.md": (
            "5ab1d3367d5a19d20304b78b7bd220b4997aff874430e9aea3581d9d71ba866c"
        ),
        "demo-scenario-not-benchmark-v1.json": (
            "b1021513c27c66b64a7d99f2be7241f9cd3968fb9ca973214085bd43474882ab"
        ),
    }
    for name, digest in expected.items():
        content = (repository / "artifacts" / "detector" / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest


def test_v2_demo_exhibits_full_tiered_lifecycle() -> None:
    result = run_v2_demo(DEVELOPMENT_CANDIDATES[1])
    assert result == run_v2_demo(DEVELOPMENT_CANDIDATES[1])
    assert result["label"] == DEMO_LABEL
    assert result["benchmark_data"] is False
    issuer_episode = result["episodes"][0]
    levels = [transition["evidence_level"] for transition in issuer_episode["transitions"]]
    transition_keys = [
        (
            transition["timestamp"],
            transition["evidence_level"],
            transition["severity"],
        )
        for transition in issuer_episode["transitions"]
    ]
    assert len(transition_keys) == len(set(transition_keys))
    assert "WATCH" in levels
    assert "CONFIRMED" in levels
    assert "RECOVERING" in levels
    assert "RESOLVED" in levels
    assert issuer_episode["failure_distribution"]["dominant_shifts"]
