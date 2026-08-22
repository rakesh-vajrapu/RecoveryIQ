from __future__ import annotations

import argparse
import sys
from pathlib import Path

from recoveriq_ml_v2.calibration import fit_and_freeze_calibration_v2
from recoveriq_ml_v2.config import (
    MODEL_V2_CALIBRATION_SEEDS,
    MODEL_V2_DEVELOPMENT_SEEDS,
    SEQUENTIAL_TRAINING_SEEDS,
)
from recoveriq_ml_v2.evaluation import evaluate_model_v2_once
from recoveriq_ml_v2.logging import generate_and_write_logged_group, read_logged_group
from recoveriq_ml_v2.training import train_and_freeze_model_v2


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recovery-sequential")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate-logged")
    generate.add_argument(
        "--group", choices=("training", "development", "calibration"), required=True
    )
    commands.add_parser("train-model-v2")
    commands.add_parser("calibrate-model-v2")
    commands.add_parser("evaluate-model-v2-heldout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = repository_root()
    logged_root = root / "artifacts" / "ml" / "logged_v2"
    model_root = root / "artifacts" / "ml" / "models" / "recovery-model-v2"
    calibration_root = root / "artifacts" / "ml" / "calibration" / "recovery-model-v2"
    report_root = root / "artifacts" / "ml" / "reports_v2"
    try:
        if args.command == "generate-logged":
            seeds = {
                "training": SEQUENTIAL_TRAINING_SEEDS,
                "development": MODEL_V2_DEVELOPMENT_SEEDS,
                "calibration": MODEL_V2_CALIBRATION_SEEDS,
            }[args.group]
            report = generate_and_write_logged_group(
                group=str(args.group),
                seeds=seeds,
                logged_root=logged_root,
            )
            print(f"generated {report['decision_count']} sequential decisions for {args.group}")
            return 0
        if args.command == "train-model-v2":
            report = train_and_freeze_model_v2(
                training=read_logged_group(logged_root, "training"),
                development=read_logged_group(logged_root, "development"),
                model_root=model_root,
                report_root=report_root,
            )
            print(
                f"froze Recovery Model V2 candidate {report['selected_lightgbm_candidate_index']}"
            )
            return 0
        if args.command == "calibrate-model-v2":
            report = fit_and_freeze_calibration_v2(
                calibration=read_logged_group(logged_root, "calibration"),
                model_root=model_root,
                calibration_root=calibration_root,
            )
            print(f"froze Model V2 calibration: {report['selected_method']}")
            return 0
        if args.command == "evaluate-model-v2-heldout":
            report = evaluate_model_v2_once(
                logged_root=logged_root,
                model_root=model_root,
                calibration_root=calibration_root,
                report_root=report_root,
            )
            print(f"Model V2 held-out gate={report['model_v2_quality_gate']['status']}")
            return 0
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
