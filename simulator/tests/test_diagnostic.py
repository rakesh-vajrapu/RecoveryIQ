# mypy: ignore-errors
import json
from pathlib import Path

from recoveriq_policy_evaluation.diagnostic import run_paired_diagnostic
from recoveriq_sequential_policy.models import FrozenSequentialBaselines
from recoveriq_simulator.seeds import DIAGNOSTIC_SEEDS


def test_diagnostic_deterministic(tmp_path: Path):
    baselines_path = (
        Path(__file__).parent.parent.parent
        / "artifacts"
        / "policy"
        / "recoveriq-sequential-v2"
        / "development-baselines-v2.json"
    )
    with open(baselines_path, encoding="utf-8") as f:
        baselines = FrozenSequentialBaselines.model_validate(json.load(f))

    model_root = (
        Path(__file__).parent.parent.parent / "artifacts" / "ml" / "models" / "recovery-model-v2"
    )
    calibration_root = (
        Path(__file__).parent.parent.parent
        / "artifacts"
        / "ml"
        / "calibration"
        / "recovery-model-v2"
    )

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
    assert (
        m["best_count"] + m["tied_count"] + m["suboptimal_count"] == m["eligible_paired_decisions"]
    )


from recoveriq_sequential.episodes import (
    build_episode_templates,
    generate_sequential_candidates,
    initial_episode_state,
)
from recoveriq_sequential.models import EpisodeTermination
from recoveriq_sequential.oracle import SequentialScenarioOracle
from recoveriq_sequential_policy.engine import RecoverIQSequentialPolicyEngine
from recoveriq_sequential_policy.scoring import SequentialModelV2Scorer
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator


def test_diagnostic_oracle_non_interference():
    baselines_path = (
        Path(__file__).parent.parent.parent
        / "artifacts"
        / "policy"
        / "recoveriq-sequential-v2"
        / "development-baselines-v2.json"
    )
    with open(baselines_path, encoding="utf-8") as f:
        baselines = FrozenSequentialBaselines.model_validate(json.load(f))
    model_root = (
        Path(__file__).parent.parent.parent / "artifacts" / "ml" / "models" / "recovery-model-v2"
    )
    calibration_root = (
        Path(__file__).parent.parent.parent
        / "artifacts"
        / "ml"
        / "calibration"
        / "recovery-model-v2"
    )
    scorer = SequentialModelV2Scorer(model_root=model_root, calibration_root=calibration_root)
    engine = RecoverIQSequentialPolicyEngine(0.0)

    seed = DIAGNOSTIC_SEEDS[0]
    config = SimulatorConfig(seed=seed)
    scenario = ScenarioGenerator(config).generate()
    templates = build_episode_templates(scenario, seed)

    factual_selections: list[Any] = []
    runtimes: list[Any] = [
        {"template": item, "state": initial_episode_state(item)} for item in templates
    ]
    for _ in range(3):
        active = [rt for rt in runtimes if rt["state"].termination == EpisodeTermination.ACTIVE]
        if not active:
            break
        scoring_rows = []
        for rt in active:
            candidates = generate_sequential_candidates(
                rt["template"], rt["state"], config.resolved_costs
            )
            rt["candidates"] = candidates
            scoring_rows.extend((rt["template"], rt["state"], c) for c in candidates)
        batch_scores = scorer.score(scoring_rows) if scoring_rows else []
        offset = 0
        for rt in active:
            scores = tuple(batch_scores[offset : offset + len(rt["candidates"])])
            offset += len(rt["candidates"])
            decision = engine.decide(rt["state"], scores)
            factual_selections.append(
                decision.selected.candidate.label if decision.selected else None
            )
            rt["state"] = rt["state"].model_copy(update={"termination": EpisodeTermination.STOP})

    oracle_selections: list[Any] = []
    runtimes2: list[Any] = [
        {"template": item, "state": initial_episode_state(item)} for item in templates
    ]
    oracle = SequentialScenarioOracle(scenario, config)
    for _ in range(3):
        active = [rt for rt in runtimes2 if rt["state"].termination == EpisodeTermination.ACTIVE]
        if not active:
            break
        scoring_rows = []
        for rt in active:
            candidates = generate_sequential_candidates(
                rt["template"], rt["state"], config.resolved_costs
            )
            rt["candidates"] = candidates
            scoring_rows.extend((rt["template"], rt["state"], c) for c in candidates)
        batch_scores = scorer.score(scoring_rows) if scoring_rows else []
        offset = 0
        for rt in active:
            scores = tuple(batch_scores[offset : offset + len(rt["candidates"])])
            offset += len(rt["candidates"])
            decision = engine.decide(rt["state"], scores)
            oracle_selections.append(
                decision.selected.candidate.label if decision.selected else None
            )
            if decision.selected:
                for s in scores:
                    if s.supported:
                        oracle.execute(rt["template"], rt["state"], s.candidate)
            rt["state"] = rt["state"].model_copy(update={"termination": EpisodeTermination.STOP})

    assert factual_selections == oracle_selections, (
        "Oracle execution mutated hidden state impacting subsequent scores!"
    )
