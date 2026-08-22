from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from recoveriq_detector_v2.artifacts import (
    artifact_root_v2,
    load_frozen_v2_config,
    render_report,
    safety_gate,
    write_frozen_v2_config,
    write_json,
    write_markdown,
)
from recoveriq_detector_v2.audit import v2_incident_opportunity_rows
from recoveriq_detector_v2.config import (
    FINAL_EVALUATION_SEEDS,
    HIGH_EVIDENCE_RULE,
    V1_CONSUMED_VALIDATION_SEEDS,
    V2_DEVELOPMENT_SEEDS,
    V2_VALIDATION_SEEDS,
)
from recoveriq_detector_v2.demo import run_v2_demo
from recoveriq_detector_v2.evaluation import aggregate_v2_evaluations, evaluate_v2_scenario
from recoveriq_detector_v2.replay import ReplayV2Result, replay_v2_scenario
from recoveriq_detector_v2.selection import evaluate_v2_frozen, select_v2_on_development
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="degradation-v2")
    parser.add_argument("--artifact-root", type=Path, default=artifact_root_v2())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit")
    commands.add_parser("select")
    commands.add_parser("validate")
    commands.add_parser("summary")
    replay = commands.add_parser("replay")
    replay.add_argument("--seed", type=int, default=V2_DEVELOPMENT_SEEDS[0])
    commands.add_parser("demo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.artifact_root
    if args.command == "audit":
        return _audit(root)
    if args.command == "select":
        return _select(root)
    if args.command == "validate":
        return _validate(root)
    if args.command == "summary":
        return _summary(root)
    if args.command == "replay":
        return _replay(root, int(args.seed))
    if args.command == "demo":
        return _demo(root)
    raise AssertionError("unreachable command")


def _audit(root: Path) -> int:
    rows: list[dict[str, Any]] = []
    for seed in V2_DEVELOPMENT_SEEDS:
        scenario = ScenarioGenerator(SimulatorConfig(seed=seed)).generate()
        rows.extend(v2_incident_opportunity_rows(scenario))
    report = {
        "seed_group": "v2_development",
        "seeds": list(V2_DEVELOPMENT_SEEDS),
        "incident_count": len(rows),
        "original_eligible_count": sum(bool(row["eligible"]) for row in rows),
        "high_evidence_count": sum(bool(row["high_evidence"]) for row in rows),
        "high_evidence_rule": HIGH_EVIDENCE_RULE.model_dump(mode="json"),
        "severity_distribution": dict(Counter(str(row["severity"]) for row in rows)),
        "incidents": rows,
    }
    path = root / "development-observability-audit-v2.json"
    write_json(path, report)
    print(f"wrote {path}")
    return 0


def _select(root: Path) -> int:
    config, report, replays = select_v2_on_development(V2_DEVELOPMENT_SEEDS)
    frozen = root / "degradation-detector-v2.json"
    if frozen.exists():
        existing = load_frozen_v2_config(frozen)
        if existing.configuration_hash != config.configuration_hash:
            print("refusing to overwrite a different frozen v2 configuration", file=sys.stderr)
            return 2
    write_frozen_v2_config(frozen, config)
    write_json(root / "development-evaluation-v2.json", report)
    write_markdown(
        root / "development-report-v2.md",
        render_report("Detector V2 Development Report", report),
    )
    _write_replay_artifacts(root, "development", replays)
    print(f"froze detector v2 config {config.configuration_hash}")
    return 0


def _validate(root: Path) -> int:
    frozen = root / "degradation-detector-v2.json"
    output = root / "validation-evaluation-v2.json"
    if not frozen.exists():
        print("detector v2 development configuration is not frozen", file=sys.stderr)
        return 2
    if output.exists():
        print("v2 validation artifact already exists; refusing to rerun", file=sys.stderr)
        return 2
    config = load_frozen_v2_config(frozen)
    report, replays = evaluate_v2_frozen(V2_VALIDATION_SEEDS, config)
    report["hard_policy_safety_gate"] = safety_gate(report["metrics"])
    write_json(output, report)
    write_markdown(
        root / "validation-report-v2.md",
        render_report("Detector V2 One-Time Validation Report", report),
    )
    write_json(
        root / "validation-false-confirmed-exposure-v2.json",
        {
            "total_failed_payment_exposure": report["metrics"]["confirmed"][
                "false_confirmed_failed_payment_exposure"
            ],
            "episodes": report["metrics"]["false_confirmed"],
        },
    )
    _write_replay_artifacts(root, "validation", replays)
    print(f"wrote one-time detector v2 validation {output}")
    return 0


def _summary(root: Path) -> int:
    required = {
        "frozen": root / "degradation-detector-v2.json",
        "audit": root / "development-observability-audit-v2.json",
        "development": root / "development-evaluation-v2.json",
        "validation": root / "validation-evaluation-v2.json",
        "exposure": root / "validation-false-confirmed-exposure-v2.json",
        "demo": root / "demo-scenario-not-benchmark-v2.json",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        print(f"cannot summarize; missing artifacts: {', '.join(missing)}", file=sys.stderr)
        return 2
    values = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in required.items()}
    repository = Path(__file__).resolve().parents[2]
    v1_names = (
        "degradation-detector-v1.json",
        "development-report-v1.md",
        "validation-report-v1.md",
        "demo-scenario-not-benchmark-v1.json",
    )
    v1_root = repository / "artifacts" / "detector"
    v1_hashes = {
        name: hashlib.sha256((v1_root / name).read_bytes()).hexdigest() for name in v1_names
    }
    development = values["development"]
    validation = values["validation"]
    audit = values["audit"]
    exposure = values["exposure"]
    summary = {
        "phase": "3.5_operational_degradation_detector_v2",
        "detector_version": values["frozen"]["detector_version"],
        "configuration_hash": values["frozen"]["configuration_hash"],
        "frozen_config": values["frozen"]["config"],
        "policy_status": "ADVISORY_ONLY",
        "v1_historical_commit": "6bd0952bf4ff9182ed9c09b3e493a5807906d7fe",
        "v1_artifact_sha256": v1_hashes,
        "seed_protocol": {
            "development": list(V2_DEVELOPMENT_SEEDS),
            "v1_consumed_validation_forbidden": list(V1_CONSUMED_VALIDATION_SEEDS),
            "v2_validation_executed_once": list(V2_VALIDATION_SEEDS),
            "final_untouched": list(FINAL_EVALUATION_SEEDS),
        },
        "development_observability": {
            "incident_count": audit["incident_count"],
            "original_eligible_count": audit["original_eligible_count"],
            "high_evidence_count": audit["high_evidence_count"],
            "high_evidence_rule": audit["high_evidence_rule"],
        },
        "development": {
            "selection_objective": development["selection_objective"],
            "candidate_count": development["candidate_count"],
            "candidates": development["candidates"],
            "chosen_candidate_index": development["chosen_candidate_index"],
            "metrics": _compact_v2_metrics(development["metrics"]),
            "comparators": _compact_comparators(development["comparators"]),
            "throughput_events_per_second": development["throughput_events_per_second"],
            "mean_update_latency_ms": development["mean_update_latency_ms"],
        },
        "validation": {
            "run_count": 1,
            "metrics": _compact_v2_metrics(validation["metrics"]),
            "comparators": _compact_comparators(validation["comparators"]),
            "hard_policy_safety_gate": validation["hard_policy_safety_gate"],
            "throughput_events_per_second": validation["throughput_events_per_second"],
            "mean_update_latency_ms": validation["mean_update_latency_ms"],
        },
        "false_confirmed_exposure": {
            "episode_count": len(exposure["episodes"]),
            "total_failed_payments": exposure["total_failed_payment_exposure"],
            "detail_artifact": "validation-false-confirmed-exposure-v2.json",
        },
        "demo": {
            "label": values["demo"]["label"],
            "benchmark_data": values["demo"]["benchmark_data"],
            "artifact": "demo-scenario-not-benchmark-v2.json",
        },
    }
    path = root / "phase35-summary-v2.json"
    write_json(path, summary)
    print(f"wrote {path} without replaying any seed")
    return 0


def _compact_v2_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in metrics.items() if key not in {"per_seed", "false_confirmed"}
    }


def _compact_comparators(comparators: dict[str, Any]) -> dict[str, Any]:
    return {
        name: {
            key: value
            for key, value in metrics.items()
            if key not in {"per_seed", "false_positive_incidents"}
        }
        for name, metrics in comparators.items()
    }


def _replay(root: Path, seed: int) -> int:
    if seed in FINAL_EVALUATION_SEEDS:
        print("FINAL EVALUATION SEEDS MUST REMAIN UNTOUCHED", file=sys.stderr)
        return 2
    if seed in V1_CONSUMED_VALIDATION_SEEDS:
        print("detector v1 validation seeds are forbidden for v2 tuning", file=sys.stderr)
        return 2
    if seed in V2_VALIDATION_SEEDS:
        print("v2 validation seeds may only run through one-time validate", file=sys.stderr)
        return 2
    if seed not in V2_DEVELOPMENT_SEEDS:
        print("replay accepts a registered v2 development seed only", file=sys.stderr)
        return 2
    frozen = root / "degradation-detector-v2.json"
    if not frozen.exists():
        print("run v2 development selection first", file=sys.stderr)
        return 2
    config = load_frozen_v2_config(frozen)
    scenario = ScenarioGenerator(SimulatorConfig(seed=seed)).generate()
    replay = replay_v2_scenario(scenario, config)
    evaluation = aggregate_v2_evaluations([evaluate_v2_scenario(scenario, replay.episodes, config)])
    output = root / "replays" / f"development-{seed}"
    write_json(
        output / "episodes.json",
        [episode.model_dump(mode="json") for episode in replay.episodes],
    )
    write_json(output / "evaluation.json", evaluation)
    print(f"wrote {output}")
    return 0


def _demo(root: Path) -> int:
    frozen = root / "degradation-detector-v2.json"
    if not frozen.exists():
        print("run v2 development selection first", file=sys.stderr)
        return 2
    result = run_v2_demo(load_frozen_v2_config(frozen))
    path = root / "demo-scenario-not-benchmark-v2.json"
    write_json(path, result)
    print(f"wrote {path}")
    return 0


def _write_replay_artifacts(
    root: Path,
    group: str,
    replays: tuple[ReplayV2Result, ...],
) -> None:
    write_json(
        root / f"{group}-episodes-v2.json",
        [episode.model_dump(mode="json") for replay in replays for episode in replay.episodes],
    )
    write_json(
        root / f"{group}-health-snapshot-sample-v2.json",
        [
            snapshot.model_dump(mode="json")
            for replay in replays
            for snapshot in replay.snapshot_sample
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
