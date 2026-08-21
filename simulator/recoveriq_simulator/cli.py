"""Command-line entry point for deterministic simulation experiments."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from recoveriq_simulator.analysis import assert_sane, build_analysis
from recoveriq_simulator.artifacts import load_summary, write_experiment
from recoveriq_simulator.benchmark import run_benchmark
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recoveriq-simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "benchmark"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--seed", type=int, default=20_260_821)
        command_parser.add_argument("--attempts", type=int, default=20_000)
        command_parser.add_argument("--output", type=Path)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("experiment_id")
    inspect_parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect":
        print(json.dumps(load_summary(args.experiment_id, args.output), indent=2))
        return 0

    config = SimulatorConfig(seed=args.seed, num_payment_attempts=args.attempts)
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
