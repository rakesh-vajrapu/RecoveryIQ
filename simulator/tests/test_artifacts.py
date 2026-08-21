from __future__ import annotations

import json

import pandas as pd

from recoveriq_simulator.analysis import assert_sane, build_analysis
from recoveriq_simulator.artifacts import ARTIFACT_NAMES, write_experiment


def test_analysis_sanity_checks_pass(
    shared_scenario,
    shared_config,
    shared_benchmark,  # type: ignore[no-untyped-def]
) -> None:
    analysis = build_analysis(shared_scenario, shared_config, shared_benchmark)
    assert_sane(analysis)
    assert all(analysis["sanity_checks"].values())


def test_experiment_artifacts_are_complete(
    tmp_path,
    shared_scenario,
    shared_config,
    shared_benchmark,  # type: ignore[no-untyped-def]
) -> None:
    output = write_experiment(
        scenario=shared_scenario,
        config=shared_config,
        benchmark=shared_benchmark,
        artifact_root=tmp_path,
    )
    assert {path.name for path in output.iterdir()} == set(ARTIFACT_NAMES)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == shared_config.seed
    assert manifest["number_of_payment_attempts"] == 1_200
    assert manifest["number_of_failures"] == len(shared_scenario.public.failure_observations)
    assert len(pd.read_parquet(output / "payments.parquet")) == 1_200
