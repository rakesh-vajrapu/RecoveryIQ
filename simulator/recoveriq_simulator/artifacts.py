"""Stable JSON and Parquet experiment artifact output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel

from recoveriq_simulator.analysis import build_analysis, render_quality_markdown
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.results import BenchmarkResult
from recoveriq_simulator.scenario import scenario_digest

ARTIFACT_NAMES = (
    "manifest.json",
    "observable/events.parquet",
    "observable/payments.parquet",
    "observable/subscriptions.parquet",
    "observable/failure_observations.parquet",
    "ground_truth/incidents.parquet",
    "ground_truth/outcomes.parquet",
    "baseline_results.json",
    "analysis.json",
    "quality_report.md",
)


def default_artifact_root() -> Path:
    return Path(__file__).resolve().parents[2] / "artifacts" / "simulations"


def write_experiment(
    *,
    scenario: GeneratedScenario,
    config: SimulatorConfig,
    benchmark: BenchmarkResult | None,
    artifact_root: Path | None = None,
) -> Path:
    output = (artifact_root or default_artifact_root()) / config.experiment_id
    observable = output / "observable"
    ground_truth = output / "ground_truth"
    observable.mkdir(parents=True, exist_ok=True)
    ground_truth.mkdir(parents=True, exist_ok=True)
    _write_parquet(observable / "events.parquet", scenario.public.observable_events)
    _write_parquet(observable / "payments.parquet", scenario.public.payments)
    _write_parquet(observable / "subscriptions.parquet", scenario.public.subscriptions)
    _write_parquet(
        observable / "failure_observations.parquet",
        scenario.public.failure_observations,
    )
    _write_parquet(ground_truth / "incidents.parquet", scenario.ground_truth.incidents)
    _write_parquet(
        ground_truth / "outcomes.parquet",
        tuple(scenario.ground_truth.payments.values()),
    )
    analysis = build_analysis(scenario, config, benchmark)
    _write_json(output / "analysis.json", analysis)
    (output / "quality_report.md").write_text(
        render_quality_markdown(analysis), encoding="utf-8", newline="\n"
    )
    _write_json(
        output / "baseline_results.json",
        benchmark.model_dump(mode="json") if benchmark is not None else {"policies": []},
    )
    manifest = {
        "experiment_id": config.experiment_id,
        "simulator_version": config.simulator_version,
        "seed": config.seed,
        # A logical creation timestamp keeps the complete experiment reproducible.
        "creation_timestamp": config.start_time.isoformat(),
        "configuration_hash": config.configuration_hash,
        "scenario_digest": scenario_digest(scenario),
        "number_of_merchants": len(scenario.public.merchants),
        "number_of_customers": len(scenario.public.customers),
        "number_of_subscriptions": len(scenario.public.subscriptions),
        "number_of_payment_attempts": len(scenario.public.payments),
        "number_of_failures": len(scenario.public.failure_observations),
        "number_of_hidden_incidents": len(scenario.ground_truth.incidents),
        "output_artifact_names": list(ARTIFACT_NAMES),
        "configuration": config.model_dump(mode="json"),
        "resolved_synthetic_costs": config.resolved_costs.model_dump(mode="json"),
        "artifact_boundary": {
            "observable": "policy-visible evidence only",
            "ground_truth": "environment-owned; never direct model input",
        },
    }
    _write_json(output / "manifest.json", manifest)
    return output


def load_summary(experiment_id: str, artifact_root: Path | None = None) -> dict[str, Any]:
    directory = (artifact_root or default_artifact_root()) / experiment_id
    if not directory.is_dir():
        raise FileNotFoundError(f"experiment not found: {experiment_id}")
    with (directory / "manifest.json").open(encoding="utf-8") as manifest_file:
        manifest: dict[str, Any] = json.load(manifest_file)
    with (directory / "analysis.json").open(encoding="utf-8") as analysis_file:
        analysis: dict[str, Any] = json.load(analysis_file)
    return {"manifest": manifest, "analysis": analysis}


def _write_parquet(path: Path, records: tuple[BaseModel, ...]) -> None:
    rows = [record.model_dump(mode="python") for record in records]
    pd.DataFrame.from_records(rows).to_parquet(path, index=False)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
