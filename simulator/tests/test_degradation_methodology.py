from __future__ import annotations

import json

from recoveriq_detector.artifacts import load_frozen_config, write_frozen_config
from recoveriq_detector.cli import main
from recoveriq_detector.config import (
    DEVELOPMENT_CANDIDATES,
    ELIGIBILITY_RULE,
    DetectorConfig,
)
from recoveriq_detector.demo import DEMO_LABEL, run_demo
from recoveriq_simulator.seeds import FINAL_EVALUATION_SEEDS


def test_eligibility_is_opportunity_only_and_pre_registered() -> None:
    assert ELIGIBILITY_RULE.min_incident_attempts == 5
    assert ELIGIBILITY_RULE.min_prior_baseline_attempts == 50
    fields = set(type(ELIGIBILITY_RULE).model_fields)
    assert fields == {
        "min_incident_attempts",
        "min_prior_baseline_attempts",
        "baseline_lookback_days",
    }


def test_development_candidates_are_small_and_explicit() -> None:
    assert 2 <= len(DEVELOPMENT_CANDIDATES) <= 12
    assert len({candidate.configuration_hash for candidate in DEVELOPMENT_CANDIDATES}) == len(
        DEVELOPMENT_CANDIDATES
    )


def test_frozen_configuration_artifact_is_reproducible(tmp_path) -> None:  # type: ignore[no-untyped-def]
    config = DetectorConfig()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_frozen_config(first, config)
    write_frozen_config(second, config)
    assert first.read_bytes() == second.read_bytes()
    assert load_frozen_config(first) == config
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["validation_must_load_this_artifact"] is True


def test_validation_refuses_without_frozen_config(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--artifact-root", str(tmp_path), "validate"]) == 2
    assert "not frozen" in capsys.readouterr().err


def test_validation_refuses_to_overwrite_existing_result(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    write_frozen_config(tmp_path / "degradation-detector-v1.json", DetectorConfig())
    (tmp_path / "validation-evaluation-v1.json").write_text("{}", encoding="utf-8")
    assert main(["--artifact-root", str(tmp_path), "validate"]) == 2
    assert "refusing to rerun" in capsys.readouterr().err


def test_validation_loads_the_frozen_configuration(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    config = DEVELOPMENT_CANDIDATES[1]
    write_frozen_config(tmp_path / "degradation-detector-v1.json", config)
    captured: dict[str, str] = {}

    def fake_evaluation(seeds, loaded_config):  # type: ignore[no-untyped-def]
        captured["hash"] = loaded_config.configuration_hash
        return (
            {
                "phase": "validation_frozen_configuration",
                "configuration_hash": loaded_config.configuration_hash,
                "config": loaded_config.model_dump(mode="json"),
                "metrics": {
                    "all_incident_count": 0,
                    "eligible_incident_count": 0,
                    "all_incident_recall": 0.0,
                    "eligible_incident_recall": 0.0,
                    "predicted_incident_precision": None,
                    "false_positive_incident_count": 0,
                    "false_incidents_per_scope_day": 0.0,
                    "detection_delay_minutes": {
                        "count": 0,
                        "mean": None,
                        "median": None,
                        "p90": None,
                    },
                    "false_positive_causes": {},
                    "false_positive_incidents": [],
                    "recall_by_hidden_severity": {},
                    "recall_by_traffic_volume": {},
                    "dominant_failure_shift": {},
                },
                "baseline_detector_comparison": {},
                "throughput_events_per_second": 0.0,
                "mean_update_latency_ms": 0.0,
            },
            (),
        )

    monkeypatch.setattr("recoveriq_detector.cli.evaluate_frozen_config", fake_evaluation)
    assert main(["--artifact-root", str(tmp_path), "validate"]) == 0
    assert captured["hash"] == config.configuration_hash


def test_final_seeds_cannot_be_replayed_by_default_command(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    seed = FINAL_EVALUATION_SEEDS[0]
    assert main(["--artifact-root", str(tmp_path), "replay", "--seed", str(seed)]) == 2
    assert "MUST REMAIN UNTOUCHED" in capsys.readouterr().err


def test_controlled_demo_is_resolved_and_never_benchmark_data() -> None:
    result = run_demo(DEVELOPMENT_CANDIDATES[1])
    assert result["label"] == DEMO_LABEL
    assert result["benchmark_data"] is False
    assert len(result["predicted_incidents"]) == 1
    incident = result["predicted_incidents"][0]
    assert incident["resolved_at"] is not None
    assert result["final_health_context"]["issuer_health"]["status"] == "HEALTHY"
