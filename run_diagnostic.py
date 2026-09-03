import json
import sys
from pathlib import Path
from recoveriq_simulator.seeds import FINAL_DIAGNOSTIC_SEEDS
from recoveriq_sequential_policy.models import FrozenSequentialBaselines
from recoveriq_policy_evaluation.diagnostic import run_paired_diagnostic

def main():
    out_dir = Path("artifacts/evaluation/multi-action-counterfactual-v2")
    out_file = out_dir / "multi-action-counterfactual-summary-v2.json"
    attempt_marker = out_dir / ".attempt_sealed"

    if attempt_marker.exists() or out_file.exists():
        print("ERROR: Sealed attempt guard triggered. The final diagnostic has already been attempted or generated.")
        print("A genuine implementation defect requires a durable INVALIDATED attempt record and fresh seeds.")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    # Write the attempt marker BEFORE executing
    with open(attempt_marker, "w", encoding="utf-8") as f:
        f.write("SEALED_ATTEMPT_STARTED\n")

    print("Loading baselines...")
    baselines_path = Path("artifacts/policy/recoveriq-sequential-v2/development-baselines-v2.json")
    with open(baselines_path, "r", encoding="utf-8") as f:
        baselines = FrozenSequentialBaselines.model_validate(json.load(f))

    print("Running diagnostic...")
    result = run_paired_diagnostic(
        seeds=FINAL_DIAGNOSTIC_SEEDS,
        baselines=baselines,
        normalized_margin_threshold=0.0,
        model_root=Path("artifacts/ml/models/recovery-model-v2"),
        calibration_root=Path("artifacts/ml/calibration/recovery-model-v2"),
    )
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    
    print(f"Artifact written to {out_file}")

if __name__ == "__main__":
    main()
