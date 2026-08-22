from __future__ import annotations

import argparse
import sys
from pathlib import Path

from recoveriq_policy_evaluation.audit import run_development_audit
from recoveriq_policy_evaluation.development import freeze_development_policy
from recoveriq_policy_evaluation.validation import run_validation_once


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_policy_artifact_root() -> Path:
    return repository_root() / "artifacts" / "policy" / "recoveriq-policy-v1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recovery-policy")
    parser.add_argument("--artifact-root", type=Path, default=default_policy_artifact_root())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit-development")
    commands.add_parser("develop-policy")
    commands.add_parser("evaluate-validation")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.artifact_root
    if args.command == "audit-development":
        return _audit_development(root)
    if args.command == "develop-policy":
        return _develop_policy(root)
    if args.command == "evaluate-validation":
        return _evaluate_validation(root)
    raise AssertionError("unreachable command")


def _audit_development(root: Path) -> int:
    repository = repository_root()
    try:
        report = run_development_audit(
            artifact_root=root,
            model_root=repository / "artifacts" / "ml" / "models" / "recovery-model-v1",
            calibration_root=repository / "artifacts" / "ml" / "calibration" / "recovery-model-v1",
            frozen_detector_path=repository
            / "artifacts"
            / "detector_v2"
            / "degradation-detector-v2.json",
        )
    except FileExistsError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(
        f"audited {report['decision_count']} development decisions; "
        f"best global action is {report['best_global_action_by_erv']}"
    )
    return 0


def _develop_policy(root: Path) -> int:
    repository = repository_root()
    try:
        report = freeze_development_policy(
            artifact_root=root,
            model_root=repository / "artifacts" / "ml" / "models" / "recovery-model-v1",
            calibration_root=repository / "artifacts" / "ml" / "calibration" / "recovery-model-v1",
        )
    except (FileExistsError, FileNotFoundError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(
        "froze RecoverIQ Policy V1 with normalized margin "
        f"{report['selected_normalized_margin_threshold']} and config "
        f"{report['frozen_policy_config_hash']}"
    )
    return 0


def _evaluate_validation(root: Path) -> int:
    repository = repository_root()
    try:
        report = run_validation_once(
            artifact_root=root,
            model_root=repository / "artifacts" / "ml" / "models" / "recovery-model-v1",
            calibration_root=repository / "artifacts" / "ml" / "calibration" / "recovery-model-v1",
            frozen_detector_path=repository
            / "artifacts"
            / "detector_v2"
            / "degradation-detector-v2.json",
        )
    except (FileExistsError, FileNotFoundError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    gate = report["validation_gates"]["overall"]["pass"]
    print(
        f"executed registered Policy V1 validation exactly once; gate={'PASS' if gate else 'FAIL'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
