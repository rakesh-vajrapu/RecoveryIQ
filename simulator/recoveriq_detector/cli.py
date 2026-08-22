from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from recoveriq_detector.artifacts import (
    detector_artifact_root,
    load_frozen_config,
    render_evaluation_markdown,
    write_frozen_config,
    write_json,
    write_markdown,
)
from recoveriq_detector.audit import build_development_observability_audit
from recoveriq_detector.config import ELIGIBILITY_RULE
from recoveriq_detector.demo import run_demo
from recoveriq_detector.evaluation import aggregate_evaluations, evaluate_scenario
from recoveriq_detector.replay import replay_scenario
from recoveriq_detector.selection import (
    evaluate_frozen_config,
    select_development_config,
)
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator
from recoveriq_simulator.seeds import (
    DEVELOPMENT_SEEDS,
    FINAL_EVALUATION_SEEDS,
    VALIDATION_SEEDS,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="degradation")
    parser.add_argument("--artifact-root", type=Path, default=detector_artifact_root())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit", help="audit development incident observability")
    subparsers.add_parser("select", help="select and freeze detector on development seeds")
    subparsers.add_parser("validate", help="run frozen detector once on validation seeds")
    replay = subparsers.add_parser("replay", help="replay one development seed")
    replay.add_argument("--seed", type=int, default=DEVELOPMENT_SEEDS[0])
    subparsers.add_parser("demo", help="run the non-benchmark controlled demo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_root: Path = args.artifact_root
    if args.command == "audit":
        return _audit(artifact_root)
    if args.command == "select":
        return _select(artifact_root)
    if args.command == "validate":
        return _validate(artifact_root)
    if args.command == "replay":
        return _replay(artifact_root, int(args.seed))
    if args.command == "demo":
        return _demo(artifact_root)
    raise AssertionError("unreachable command")


def _audit(artifact_root: Path) -> int:
    report = build_development_observability_audit(DEVELOPMENT_SEEDS)
    path = artifact_root / "development-observability-audit-v1.json"
    write_json(path, report)
    print(f"wrote {path}")
    return 0


def _select(artifact_root: Path) -> int:
    selection = select_development_config(DEVELOPMENT_SEEDS)
    frozen_path = artifact_root / "degradation-detector-v1.json"
    if frozen_path.exists():
        existing = load_frozen_config(frozen_path)
        if existing.configuration_hash != selection.chosen_config.configuration_hash:
            print("refusing to replace a different frozen detector configuration", file=sys.stderr)
            return 2
    write_frozen_config(frozen_path, selection.chosen_config)
    report = selection.report
    report["configuration_hash"] = selection.chosen_config.configuration_hash
    report["seeds"] = list(DEVELOPMENT_SEEDS)
    report["eligibility_rule"] = ELIGIBILITY_RULE.model_dump(mode="json")
    write_json(artifact_root / "development-evaluation-v1.json", report)
    write_markdown(
        artifact_root / "development-report-v1.md",
        render_evaluation_markdown("Development Degradation Detection Report", report),
    )
    write_json(
        artifact_root / "development-false-positive-analysis-v1.json",
        {
            "false_positive_causes": report["metrics"]["false_positive_causes"],
            "incidents": report["metrics"]["false_positive_incidents"],
        },
    )
    _write_replay_samples(artifact_root, "development", selection.chosen_replays)
    print(f"froze detector config {selection.chosen_config.configuration_hash}")
    return 0


def _validate(artifact_root: Path) -> int:
    frozen_path = artifact_root / "degradation-detector-v1.json"
    output = artifact_root / "validation-evaluation-v1.json"
    if not frozen_path.exists():
        print("development detector configuration is not frozen", file=sys.stderr)
        return 2
    if output.exists():
        print("validation artifact already exists; refusing to rerun", file=sys.stderr)
        return 2
    config = load_frozen_config(frozen_path)
    report, replays = evaluate_frozen_config(VALIDATION_SEEDS, config)
    report["seeds"] = list(VALIDATION_SEEDS)
    report["eligibility_rule"] = ELIGIBILITY_RULE.model_dump(mode="json")
    write_json(output, report)
    write_markdown(
        artifact_root / "validation-report-v1.md",
        render_evaluation_markdown("Validation Degradation Detection Report", report),
    )
    write_json(
        artifact_root / "validation-false-positive-analysis-v1.json",
        {
            "false_positive_causes": report["metrics"]["false_positive_causes"],
            "incidents": report["metrics"]["false_positive_incidents"],
        },
    )
    _write_replay_samples(artifact_root, "validation", replays)
    print(f"wrote one-time validation result {output}")
    return 0


def _replay(artifact_root: Path, seed: int) -> int:
    if seed in FINAL_EVALUATION_SEEDS:
        print("FINAL EVALUATION SEEDS MUST REMAIN UNTOUCHED", file=sys.stderr)
        return 2
    if seed in VALIDATION_SEEDS:
        print("validation seeds may only be run by the one-time validate command", file=sys.stderr)
        return 2
    if seed not in DEVELOPMENT_SEEDS:
        print("replay accepts a registered development seed only", file=sys.stderr)
        return 2
    config_path = artifact_root / "degradation-detector-v1.json"
    if not config_path.exists():
        print("run development selection first", file=sys.stderr)
        return 2
    config = load_frozen_config(config_path)
    scenario = ScenarioGenerator(SimulatorConfig(seed=seed)).generate()
    replay = replay_scenario(scenario, config)
    evaluation = aggregate_evaluations([evaluate_scenario(scenario, replay.incidents)])
    output = artifact_root / "replays" / f"development-{seed}"
    write_json(output / "predicted-incidents.json", _incident_records((replay,)))
    write_json(
        output / "health-snapshot-sample.json",
        [snapshot.model_dump(mode="json") for snapshot in replay.snapshot_sample],
    )
    write_json(output / "evaluation.json", evaluation)
    print(f"wrote {output}")
    return 0


def _demo(artifact_root: Path) -> int:
    config_path = artifact_root / "degradation-detector-v1.json"
    if not config_path.exists():
        print("run development selection first", file=sys.stderr)
        return 2
    result = run_demo(load_frozen_config(config_path))
    path = artifact_root / "demo-scenario-not-benchmark-v1.json"
    write_json(path, result)
    print(f"wrote {path}")
    return 0


def _write_replay_samples(
    artifact_root: Path,
    group: str,
    replays: tuple[Any, ...],
) -> None:
    write_json(
        artifact_root / f"{group}-predicted-incidents-v1.json",
        _incident_records(replays),
    )
    snapshots = [
        snapshot.model_dump(mode="json")
        for replay in replays
        for snapshot in replay.snapshot_sample
    ]
    write_json(artifact_root / f"{group}-health-snapshot-sample-v1.json", snapshots)


def _incident_records(replays: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [incident.model_dump(mode="json") for replay in replays for incident in replay.incidents]


if __name__ == "__main__":
    raise SystemExit(main())
