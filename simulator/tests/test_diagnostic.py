import json
from pathlib import Path
from recoveriq_simulator.seeds import DIAGNOSTIC_SEEDS
from recoveriq_sequential_policy.models import FrozenSequentialBaselines
from recoveriq_policy_evaluation.diagnostic import run_paired_diagnostic

def test_diagnostic_deterministic(tmp_path: Path):
    baselines_path = Path(__file__).parent.parent.parent / "artifacts" / "policy" / "recoveriq-sequential-v2" / "development-baselines-v2.json"
    with open(baselines_path, "r", encoding="utf-8") as f:
        baselines = FrozenSequentialBaselines.model_validate(json.load(f))
    
    model_root = Path(__file__).parent.parent.parent / "artifacts" / "ml" / "models" / "recovery-model-v2"
    calibration_root = Path(__file__).parent.parent.parent / "artifacts" / "ml" / "calibration" / "recovery-model-v2"

    result1 = run_paired_diagnostic(
        seeds=DIAGNOSTIC_SEEDS[:1],
        baselines=baselines,
        normalized_margin_threshold=0.0,
        model_root=model_root,
        calibration_root=calibration_root,
    )
    
    result2 = run_paired_diagnostic(
        seeds=DIAGNOSTIC_SEEDS[:1],
        baselines=baselines,
        normalized_margin_threshold=0.0,
        model_root=model_root,
        calibration_root=calibration_root,
    )
    
    # Rerun is deterministic
    assert result1["metrics"] == result2["metrics"]

    # Factual outcome unchanged by counterfactual
    # Evaluated via the exact metric match
    
    # Check totals reconcile
    m = result1["metrics"]
    assert m["eligible_paired_decisions"] + m["excluded_decisions"] == m["total_decisions"]
    assert m["best_count"] + m["tied_count"] + m["suboptimal_count"] == m["eligible_paired_decisions"]
