import json
from pathlib import Path
from recoveriq_simulator.seeds import DIAGNOSTIC_SEEDS
from recoveriq_sequential_policy.models import FrozenSequentialBaselines
from recoveriq_policy_evaluation.diagnostic import run_paired_diagnostic

def main():
    print("Loading baselines...")
    baselines_path = Path("artifacts/policy/recoveriq-sequential-v2/development-baselines-v2.json")
    with open(baselines_path, "r", encoding="utf-8") as f:
        baselines = FrozenSequentialBaselines.model_validate(json.load(f))

    print("Running diagnostic...")
    result = run_paired_diagnostic(
        seeds=DIAGNOSTIC_SEEDS,
        baselines=baselines,
        normalized_margin_threshold=0.0,
        model_root=Path("artifacts/ml/models/recovery-model-v2"),
        calibration_root=Path("artifacts/ml/calibration/recovery-model-v2"),
    )

    out_dir = Path("artifacts/evaluation/multi-action-counterfactual-v1")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "multi-action-counterfactual-summary-v1.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    
    print(f"Artifact written to {out_file}")

if __name__ == "__main__":
    main()
