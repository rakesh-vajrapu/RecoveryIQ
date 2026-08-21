"""Command-line entry point for deterministic simulation experiments."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from recoveriq_simulator.analysis import assert_sane, build_analysis
from recoveriq_simulator.artifacts import load_summary, write_experiment
from recoveriq_simulator.benchmark import run_benchmark
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import CostRegime
from recoveriq_simulator.scenario import ScenarioGenerator
from recoveriq_simulator.seeds import SEED_GROUPS
from recoveriq_simulator.sensitivity import (
    run_sensitivity_sweep,
    write_sensitivity_report,
)
from recoveriq_simulator.suite import run_seed_suite, write_seed_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recoveriq-simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "benchmark", "quality-report"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--seed", type=int, default=20_260_821)
        command_parser.add_argument("--attempts", type=int, default=20_000)
        command_parser.add_argument("--output", type=Path)
        command_parser.add_argument(
            "--cost-regime",
            choices=[regime.value for regime in CostRegime],
            default=CostRegime.BALANCED.value,
        )
    suite_parser = subparsers.add_parser("benchmark-suite")
    suite_parser.add_argument("--group", choices=sorted(SEED_GROUPS), required=True)
    suite_parser.add_argument("--attempts", type=int, default=20_000)
    suite_parser.add_argument("--output", type=Path)
    suite_parser.add_argument("--acknowledge-final", action="store_true")
    sensitivity_parser = subparsers.add_parser("sensitivity")
    sensitivity_parser.add_argument("--attempts", type=int, default=5_000)
    sensitivity_parser.add_argument("--output", type=Path)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("experiment_id")
    inspect_parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect":
        print(json.dumps(load_summary(args.experiment_id, args.output), indent=2))
        return 0

    if args.command == "benchmark-suite":
        if args.group == "final" and not args.acknowledge_final:
            print(
                "FINAL EVALUATION SEEDS ARE RESERVED. Re-run with "
                "--acknowledge-final only when final evaluation is explicitly authorized.",
                file=sys.stderr,
            )
            return 2
        suite_report = run_seed_suite(
            group=args.group,
            base_config=SimulatorConfig(num_payment_attempts=args.attempts),
        )
        output = write_seed_suite(suite_report, args.output)
        print(
            json.dumps(
                {
                    "suite_id": suite_report.suite_id,
                    "artifact_directory": str(output.resolve()),
                    "seed_count": len(suite_report.seeds),
                    "total_runtime_seconds": suite_report.total_runtime_seconds,
                    "mean_runtime_per_environment_seconds": (
                        suite_report.mean_runtime_per_environment_seconds
                    ),
                    "report_artifact_bytes": suite_report.report_artifact_bytes,
                    "environment_metrics": {
                        key: value.model_dump(mode="json") if value is not None else None
                        for key, value in suite_report.environment_metrics.items()
                    },
                    "policy_metrics": {
                        policy: {
                            key: value.model_dump(mode="json") for key, value in metrics.items()
                        }
                        for policy, metrics in suite_report.policy_metrics.items()
                    },
                },
                indent=2,
            )
        )
        return 0

    if args.command == "sensitivity":
        sensitivity_report = run_sensitivity_sweep(attempts=args.attempts)
        output = write_sensitivity_report(sensitivity_report, args.output)
        print(
            json.dumps(
                {
                    "report_id": sensitivity_report.report_id,
                    "artifact_directory": str(output.resolve()),
                    "runtime_seconds": sensitivity_report.total_runtime_seconds,
                    "ranking_changes_from_control": (
                        sensitivity_report.ranking_changes_from_control
                    ),
                },
                indent=2,
            )
        )
        return 0

    config = SimulatorConfig(
        seed=args.seed,
        num_payment_attempts=args.attempts,
        cost_regime=CostRegime(args.cost_regime),
    )
    started = time.perf_counter()
    if args.command == "generate":
        scenario = ScenarioGenerator(config).generate()
        output = write_experiment(
            scenario=scenario,
            config=config,
            benchmark=None,
            artifact_root=args.output,
        )
        analysis = build_analysis(scenario, config)
    else:
        scenario, benchmark = run_benchmark(config)
        analysis = build_analysis(scenario, config, benchmark)
        assert_sane(analysis)
        output = write_experiment(
            scenario=scenario,
            config=config,
            benchmark=benchmark,
            artifact_root=args.output,
        )
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "experiment_id": config.experiment_id,
                "artifact_directory": str(output.resolve()),
                "runtime_seconds": round(elapsed, 3),
                "analysis": analysis,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
