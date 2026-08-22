from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from recoveriq_simulator.analysis import assert_sane, build_analysis
from recoveriq_simulator.artifacts import ARTIFACT_NAMES, write_experiment
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.results import BenchmarkResult


def test_analysis_sanity_checks_pass(
    shared_scenario: GeneratedScenario,
    shared_config: SimulatorConfig,
    shared_benchmark: BenchmarkResult,
) -> None:
    analysis = build_analysis(shared_scenario, shared_config, shared_benchmark)
    assert_sane(analysis)
    assert all(analysis["sanity_checks"].values())


def test_experiment_artifacts_are_complete(
    tmp_path: Path,
    shared_scenario: GeneratedScenario,
    shared_config: SimulatorConfig,
    shared_benchmark: BenchmarkResult,
) -> None:
    output = write_experiment(
        scenario=shared_scenario,
        config=shared_config,
        benchmark=shared_benchmark,
        artifact_root=tmp_path,
    )
    assert all((output / artifact_name).exists() for artifact_name in ARTIFACT_NAMES)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == shared_config.seed
    assert manifest["number_of_payment_attempts"] == 1_200
    assert manifest["number_of_failures"] == len(shared_scenario.public.failure_observations)
    assert len(pd.read_parquet(output / "observable" / "payments.parquet")) == 1_200
    observable_columns = set(
        pd.read_parquet(output / "observable" / "failure_observations.parquet").columns
    )
    assert "true_failure_cause" not in observable_columns
    assert "incident_id" not in observable_columns
    assert "initial_success_probability" not in observable_columns
    assert (output / "ground_truth" / "outcomes.parquet").exists()
