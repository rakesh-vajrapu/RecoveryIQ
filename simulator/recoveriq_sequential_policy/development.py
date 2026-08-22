from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from recoveriq_ml.artifacts import write_json
from recoveriq_ml_v2.logging import generate_and_write_logged_group, read_logged_group
from recoveriq_sequential.config import SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS
from recoveriq_sequential_policy.baselines import fit_sequential_baselines
from recoveriq_sequential_policy.evaluation import RECOVERIQ, evaluate_policy_seed_group
from recoveriq_sequential_policy.models import FrozenSequentialBaselines

MARGIN_CANDIDATES = (0.0, 0.001, 0.0025, 0.005, 0.01)
MIN_AUTONOMOUS_COVERAGE = 0.70


def run_policy_development(
    *,
    logged_root: Path,
    artifact_root: Path,
    model_root: Path,
    calibration_root: Path,
) -> dict[str, Any]:
    output = artifact_root / "development-policy-v2.json"
    if output.exists():
        raise FileExistsError("Sequential Policy V2 development is already complete")
    started = perf_counter()
    manifest_path = logged_root / "sequential-policy-development-manifest-v2.json"
    if not manifest_path.exists():
        generate_and_write_logged_group(
            group="policy-development",
            seeds=SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
            logged_root=logged_root,
        )
    frame = read_logged_group(logged_root, "policy-development")
    baselines = fit_sequential_baselines(frame, SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS)
    artifact_root.mkdir(parents=True, exist_ok=True)
    write_json(
        artifact_root / "development-baselines-v2.json",
        baselines.model_dump(mode="json"),
    )

    candidate_results: list[dict[str, Any]] = []
    for threshold in MARGIN_CANDIDATES:
        report, _, _ = evaluate_policy_seed_group(
            seeds=SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
            baselines=baselines,
            normalized_margin_threshold=threshold,
            model_root=model_root,
            calibration_root=calibration_root,
            strategies=(RECOVERIQ,),
            capture_traces=False,
        )
        metrics = report["strategies"][RECOVERIQ]
        candidate_results.append(
            {
                "normalized_margin_threshold": threshold,
                "metrics": metrics,
                "eligible": (
                    metrics["policy_violations"] == 0
                    and metrics["autonomous_decision_coverage"] >= MIN_AUTONOMOUS_COVERAGE
                ),
            }
        )
    selected = _select_margin(candidate_results)
    selected_threshold = float(selected["normalized_margin_threshold"])
    full_report, records, traces = evaluate_policy_seed_group(
        seeds=SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
        baselines=baselines,
        normalized_margin_threshold=selected_threshold,
        model_root=model_root,
        calibration_root=calibration_root,
    )
    records.to_parquet(artifact_root / "development-episode-records-v2.parquet", index=False)
    write_json(
        artifact_root / "development-successful-trace-v2.json", traces["successful_adaptive_trace"]
    )
    write_json(artifact_root / "development-failure-trace-v2.json", traces["bounded_failure_trace"])
    payload = {
        "artifact_type": "sequential_policy_v2_development",
        "development_seeds": SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS,
        "margin_candidates": candidate_results,
        "selection_rule": (
            "maximum simulated net value subject to zero violations and at least "
            "70% autonomous decision coverage; ties favor coverage then smaller margin"
        ),
        "selected_normalized_margin_threshold": selected_threshold,
        "full_horizon_development": full_report,
        "runtime_seconds": perf_counter() - started,
    }
    write_json(output, payload)
    return payload


def load_frozen_baselines(artifact_root: Path) -> FrozenSequentialBaselines:
    return FrozenSequentialBaselines.model_validate_json(
        (artifact_root / "development-baselines-v2.json").read_text(encoding="utf-8")
    )


def _select_margin(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["eligible"]]
    if not eligible:
        raise RuntimeError("no preregistered Sequential Policy V2 margin is eligible")
    return min(
        eligible,
        key=lambda row: (
            -int(row["metrics"]["simulated_net_recovery_value_minor"]),
            -float(row["metrics"]["autonomous_decision_coverage"]),
            float(row["normalized_margin_threshold"]),
        ),
    )
