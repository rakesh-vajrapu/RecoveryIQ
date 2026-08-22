from __future__ import annotations

import argparse
import sys
from pathlib import Path

from recoveriq_sequential_policy.development import run_policy_development
from recoveriq_sequential_policy.freeze import freeze_sequential_policy
from recoveriq_sequential_policy.validation import run_policy_validation_once


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recovery-sequential-policy")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("develop")
    commands.add_parser("freeze")
    commands.add_parser("validate-once")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = repository_root()
    logged_root = root / "artifacts" / "ml" / "logged_v2"
    model_root = root / "artifacts" / "ml" / "models" / "recovery-model-v2"
    calibration_root = root / "artifacts" / "ml" / "calibration" / "recovery-model-v2"
    artifact_root = root / "artifacts" / "policy" / "recoveriq-sequential-v2"
    try:
        if args.command == "develop":
            report = run_policy_development(
                logged_root=logged_root,
                artifact_root=artifact_root,
                model_root=model_root,
                calibration_root=calibration_root,
            )
            print(f"selected sequential margin {report['selected_normalized_margin_threshold']}")
            return 0
        if args.command == "freeze":
            policy = freeze_sequential_policy(
                artifact_root=artifact_root,
                model_root=model_root,
                calibration_root=calibration_root,
            )
            print(f"froze Sequential Policy V2 {policy.config_hash}")
            return 0
        if args.command == "validate-once":
            report = run_policy_validation_once(
                artifact_root=artifact_root,
                model_root=model_root,
                calibration_root=calibration_root,
            )
            claims = report["preregistered_validation_claims"]
            print(f"Sequential Policy V2 validation safety={claims['safety']['status']}")
            return 0
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
