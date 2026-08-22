from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

from recoveriq_ml.artifacts import (
    examples_to_feature_frame,
    frozen_detector_v2_path,
    ml_artifact_root,
    read_feature_group,
    write_json,
    write_logged_group,
    write_phase4_summary,
)
from recoveriq_ml.calibration import fit_and_freeze_calibration
from recoveriq_ml.config import (
    ML_CALIBRATION_SEEDS,
    ML_DEVELOPMENT_SEEDS,
    ML_HELDOUT_TEST_SEEDS,
    ML_TRAINING_SEEDS,
    OVERALL_FINAL_SEEDS,
)
from recoveriq_ml.evaluation import evaluate_frozen_models
from recoveriq_ml.logged_data import (
    HeldoutDecision,
    LoggedDatasetGenerator,
    audit_examples,
)
from recoveriq_ml.models import FEATURE_SCHEMA_HASH, LoggedRecoveryExample
from recoveriq_ml.training import train_and_freeze_models
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator

NORMAL_GROUPS = {
    "training": ML_TRAINING_SEEDS,
    "development": ML_DEVELOPMENT_SEEDS,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recovery-model")
    parser.add_argument("--artifact-root", type=Path, default=ml_artifact_root())
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate-logged")
    generate.add_argument("--group", choices=tuple(NORMAL_GROUPS), required=True)
    commands.add_parser("train")
    commands.add_parser("calibrate")
    commands.add_parser("evaluate-heldout")
    commands.add_parser("shap-report")
    commands.add_parser("phase4-summary")
    replay = commands.add_parser("replay-seed")
    replay.add_argument("--seed", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.artifact_root
    if args.command == "generate-logged":
        return _generate_group(root, str(args.group), NORMAL_GROUPS[str(args.group)])
    if args.command == "train":
        return _train(root)
    if args.command == "calibrate":
        return _calibrate(root)
    if args.command == "evaluate-heldout":
        return _evaluate_heldout(root)
    if args.command == "shap-report":
        return _shap_report(root)
    if args.command == "phase4-summary":
        return _phase4_summary(root)
    if args.command == "replay-seed":
        return _replay_seed(root, int(args.seed))
    raise AssertionError("unreachable command")


def _generate_group(root: Path, group: str, seeds: tuple[int, ...]) -> int:
    output = root / "logged" / f"{group}-manifest-v1.json"
    if output.exists():
        print(f"{group} logged artifact exists; refusing overwrite", file=sys.stderr)
        return 2
    examples, _, runtime = _generate_examples(seeds, include_evaluation_truth=False)
    manifest = write_logged_group(root, group, seeds, examples)
    audit = {**audit_examples(examples), "runtime_seconds": runtime}
    write_json(root / "reports" / f"{group}-logging-audit-v1.json", audit)
    print(
        f"wrote {manifest.example_count} one-action {group} examples "
        f"with schema {FEATURE_SCHEMA_HASH}"
    )
    return 0


def _train(root: Path) -> int:
    model_root = root / "models" / "recovery-model-v1"
    if (model_root / "model-manifest-v1.json").exists():
        print("model is already frozen; refusing to retrain", file=sys.stderr)
        return 2
    required = [
        root / "logged" / "training-manifest-v1.json",
        root / "logged" / "development-manifest-v1.json",
    ]
    if not all(path.exists() for path in required):
        print("generate training and development logged groups first", file=sys.stderr)
        return 2
    report = train_and_freeze_models(
        read_feature_group(root, "training"),
        read_feature_group(root, "development"),
        model_root,
    )
    print(
        "froze action-conditioned models with LightGBM candidate "
        f"{report['selected_lightgbm_candidate_index']}"
    )
    return 0


def _calibrate(root: Path) -> int:
    model_root = root / "models" / "recovery-model-v1"
    calibration_root = root / "calibration" / "recovery-model-v1"
    if not (model_root / "model-manifest-v1.json").exists():
        print("model architecture and hyperparameters are not frozen", file=sys.stderr)
        return 2
    if (calibration_root / "calibration-manifest-v1.json").exists():
        print("calibration is already frozen; refusing to refit", file=sys.stderr)
        return 2
    examples, _, runtime = _generate_examples(
        ML_CALIBRATION_SEEDS,
        include_evaluation_truth=False,
    )
    write_logged_group(root, "calibration", ML_CALIBRATION_SEEDS, examples)
    report = fit_and_freeze_calibration(
        examples_to_feature_frame(examples),
        model_root,
        calibration_root,
    )
    report["logged_generation_runtime_seconds"] = runtime
    write_json(calibration_root / "calibration-manifest-v1.json", report)
    print(f"froze {report['selected_method']} calibration before held-out test")
    return 0


def _evaluate_heldout(root: Path) -> int:
    model_root = root / "models" / "recovery-model-v1"
    calibration_root = root / "calibration" / "recovery-model-v1"
    report_root = root / "reports"
    output = report_root / "heldout-evaluation-v1.json"
    if output.exists():
        print("held-out model result exists; refusing a second run", file=sys.stderr)
        return 2
    if (
        not (model_root / "model-manifest-v1.json").exists()
        or not (calibration_root / "calibration-manifest-v1.json").exists()
    ):
        print("model and calibration must be frozen before held-out test", file=sys.stderr)
        return 2
    examples, decisions, generation_runtime = _generate_examples(
        ML_HELDOUT_TEST_SEEDS,
        include_evaluation_truth=True,
    )
    write_logged_group(root, "heldout", ML_HELDOUT_TEST_SEEDS, examples)
    manifest = json.loads((model_root / "model-manifest-v1.json").read_text(encoding="utf-8"))
    training_prevalence = float(manifest["development_metrics"]["training_prevalence"])
    report = evaluate_frozen_models(
        frame=examples_to_feature_frame(examples),
        decisions=decisions,
        model_root=model_root,
        calibration_root=calibration_root,
        report_root=report_root,
        training_prevalence=training_prevalence,
    )
    report["logged_generation_runtime_seconds"] = generation_runtime
    write_json(output, report)
    print(f"wrote one-time held-out model test {output}")
    return 0


def _shap_report(root: Path) -> int:
    path = root / "reports" / "shap-report-v1.json"
    if not path.exists():
        print("run one-time held-out evaluation to produce SHAP evidence", file=sys.stderr)
        return 2
    print(f"SHAP report already produced without replaying seeds: {path}")
    return 0


def _phase4_summary(root: Path) -> int:
    try:
        path = write_phase4_summary(root)
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"wrote seed-free Phase 4 checkpoint {path}")
    return 0


def _replay_seed(root: Path, seed: int) -> int:
    if seed in OVERALL_FINAL_SEEDS:
        print("OVERALL FINAL SEEDS MUST REMAIN UNTOUCHED", file=sys.stderr)
        return 2
    if seed in ML_CALIBRATION_SEEDS:
        print("calibration seeds may run only through the calibration stage", file=sys.stderr)
        return 2
    if seed in ML_HELDOUT_TEST_SEEDS:
        print("held-out seeds may run only through the one-time evaluation", file=sys.stderr)
        return 2
    group = next((name for name, values in NORMAL_GROUPS.items() if seed in values), None)
    if group is None:
        print("seed is not registered for a normal ML replay", file=sys.stderr)
        return 2
    examples, _, _ = _generate_examples((seed,), include_evaluation_truth=False)
    output = root / "replays" / f"{group}-{seed}"
    write_logged_group(output, group, (seed,), examples)
    print(f"wrote deterministic replay {output}")
    return 0


def _generate_examples(
    seeds: tuple[int, ...],
    *,
    include_evaluation_truth: bool,
) -> tuple[tuple[LoggedRecoveryExample, ...], tuple[HeldoutDecision, ...], float]:
    started = perf_counter()
    examples: list[LoggedRecoveryExample] = []
    decisions: list[HeldoutDecision] = []
    detector_path = frozen_detector_v2_path()
    for seed in seeds:
        config = SimulatorConfig(seed=seed)
        scenario = ScenarioGenerator(config).generate()
        generated = LoggedDatasetGenerator(config, detector_path).generate(
            scenario,
            include_evaluation_truth=include_evaluation_truth,
        )
        examples.extend(generated.examples)
        decisions.extend(generated.heldout_decisions)
    return tuple(examples), tuple(decisions), perf_counter() - started


if __name__ == "__main__":
    raise SystemExit(main())
