# mypy: ignore-errors
"""Paired Multi-Action Counterfactual Diagnostic execution."""

from datetime import datetime
from pathlib import Path
from typing import Any

from recoveriq_sequential.config import MAX_AUTONOMOUS_INTERVENTIONS
from recoveriq_sequential.episodes import (
    advance_episode_state,
    build_episode_templates,
    generate_sequential_candidates,
    initial_episode_state,
)
from recoveriq_sequential.models import (
    EpisodeTermination,
)
from recoveriq_sequential.oracle import SequentialScenarioOracle
from recoveriq_sequential_policy.engine import RecoverIQSequentialPolicyEngine
from recoveriq_sequential_policy.models import FrozenSequentialBaselines, SequentialDecisionKind
from recoveriq_sequential_policy.scoring import SequentialModelV2Scorer
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator

ARTIFACT_TYPE = "post_hoc_simulated_counterfactual_diagnostic"
DIAGNOSTIC_VERSION = "2.0.0"


def run_paired_diagnostic(
    seeds: tuple[int, ...],
    baselines: FrozenSequentialBaselines,
    normalized_margin_threshold: float,
    model_root: Path,
    calibration_root: Path,
) -> dict[str, Any]:
    scorer = SequentialModelV2Scorer(
        model_root=model_root,
        calibration_root=calibration_root,
    )
    engine = RecoverIQSequentialPolicyEngine(normalized_margin_threshold)

    total_decisions = 0
    eligible_decisions = 0
    excluded_decisions = 0

    factual_recoveries = 0
    cf_best_recoveries = 0
    factual_recovered_value = 0
    cf_best_recovered_value = 0

    total_regret = 0
    best_count = 0
    tied_count = 0
    suboptimal_count = 0
    feasible_alternatives_sum = 0
    advantage_vs_second_best_sum = 0
    value_capture_num = 0
    value_capture_den = 0

    action_breakdown: dict[str, dict[str, Any]] = {}
    reason_breakdown: dict[str, dict[str, Any]] = {}
    method_breakdown: dict[str, dict[str, Any]] = {}
    index_breakdown: dict[str, dict[str, Any]] = {}

    def _track(
        dimension: dict[str, dict[str, Any]],
        key: str,
        is_factual_recovery: bool,
        is_cf_recovery: bool,
        factual_val: int,
        cf_val: int,
        regret: int,
        best: bool,
        tied: bool,
        suboptimal: bool,
        adv2: int,
    ):
        if key not in dimension:
            dimension[key] = {
                "eligible_decisions": 0,
                "factual_recoveries": 0,
                "counterfactual_recoveries": 0,
                "factual_net_value_minor": 0,
                "counterfactual_net_value_minor": 0,
                "regret_minor": 0,
                "best_count": 0,
                "tied_count": 0,
                "suboptimal_count": 0,
                "advantage_vs_second_best_minor": 0,
            }

        dimension[key]["eligible_decisions"] += 1
        dimension[key]["factual_recoveries"] += int(is_factual_recovery)
        dimension[key]["counterfactual_recoveries"] += int(is_cf_recovery)
        dimension[key]["factual_net_value_minor"] += factual_val
        dimension[key]["counterfactual_net_value_minor"] += cf_val
        dimension[key]["regret_minor"] += regret
        dimension[key]["best_count"] += int(best)
        dimension[key]["tied_count"] += int(tied)
        dimension[key]["suboptimal_count"] += int(suboptimal)
        dimension[key]["advantage_vs_second_best_minor"] += adv2

    for seed in seeds:
        config = SimulatorConfig(seed=seed)
        scenario = ScenarioGenerator(config).generate()
        templates = build_episode_templates(scenario, seed)
        oracle = SequentialScenarioOracle(scenario, config)

        runtimes = [{"template": item, "state": initial_episode_state(item)} for item in templates]

        for _ in range(MAX_AUTONOMOUS_INTERVENTIONS):
            active = [rt for rt in runtimes if rt["state"].termination is EpisodeTermination.ACTIVE]
            if not active:
                break

            scoring_rows = []
            for rt in active:
                candidates = generate_sequential_candidates(
                    rt["template"], rt["state"], config.resolved_costs
                )
                rt["candidates"] = candidates
                scoring_rows.extend(
                    (rt["template"], rt["state"], candidate) for candidate in candidates
                )

            batch_scores = scorer.score(scoring_rows) if scoring_rows else []
            score_offset = 0

            for rt in active:
                total_decisions += 1
                candidates = rt["candidates"]
                scores = tuple(batch_scores[score_offset : score_offset + len(candidates)])
                score_offset += len(candidates)

                decision = engine.decide(rt["state"], scores)

                # Check eligibility
                if decision.kind != SequentialDecisionKind.ACTION or not decision.selected:
                    excluded_decisions += 1
                    rt["state"] = rt["state"].model_copy(
                        update={
                            "termination": EpisodeTermination.HUMAN_REVIEW
                            if decision.kind == SequentialDecisionKind.HUMAN_REVIEW
                            else EpisodeTermination.STOP
                        }
                    )
                    continue

                # Filter to feasible candidates (supported by the model)
                feasible_scores = [s for s in scores if s.supported]
                feasible_candidates = [s.candidate for s in feasible_scores]

                if len(feasible_candidates) < 2:
                    # Exclude if there are not at least 2 feasible candidates
                    excluded_decisions += 1
                    rt["state"] = rt["state"].model_copy(
                        update={"termination": EpisodeTermination.STOP}
                    )
                    continue

                eligible_decisions += 1
                selected_candidate = decision.selected.candidate
                feasible_alternatives_sum += len(feasible_candidates) - 1

                # Evaluate all feasible candidates
                evaluations = []
                for cand in feasible_candidates:
                    outcome = oracle.execute(rt["template"], rt["state"], cand)
                    amount = rt["template"].observation.amount_minor if outcome.recovered else 0
                    cost = (
                        cand.recovery_action.intervention_cost_minor
                        + cand.recovery_action.friction_cost_minor
                    )
                    net_val = amount - cost
                    evaluations.append(
                        {
                            "candidate": cand,
                            "outcome": outcome,
                            "net_val": net_val,
                            "is_selected": cand.label == selected_candidate.label,
                        }
                    )

                # Factual Outcome
                factual_eval = next(e for e in evaluations if e["is_selected"])
                factual_val = factual_eval["net_val"]

                # Counterfactual Outcomes (excluding the selected one)
                cf_evaluations = [e for e in evaluations if not e["is_selected"]]
                best_cf = max(cf_evaluations, key=lambda x: x["net_val"])

                # Regret and Advantage
                regret = max(0, best_cf["net_val"] - factual_val)
                total_regret += regret

                # Second best alternative for advantage vs second-best
                sorted_cfs = sorted(cf_evaluations, key=lambda x: x["net_val"], reverse=True)
                # the best alternative is sorted_cfs[0]. The second best *feasible alternative* is sorted_cfs[1] if it exists, else we just use best_cf
                second_best_cf = sorted_cfs[1] if len(sorted_cfs) > 1 else sorted_cfs[0]
                adv2 = factual_val - second_best_cf["net_val"]
                advantage_vs_second_best_sum += adv2

                if factual_val > best_cf["net_val"]:
                    best_count += 1
                    is_best, is_tied, is_sub = True, False, False
                elif factual_val == best_cf["net_val"]:
                    tied_count += 1
                    is_best, is_tied, is_sub = False, True, False
                else:
                    suboptimal_count += 1
                    is_best, is_tied, is_sub = False, False, True

                # Value capture
                best_overall_val = max(factual_val, best_cf["net_val"])
                if best_overall_val > 0:
                    value_capture_den += best_overall_val
                    value_capture_num += max(0, factual_val)

                factual_recoveries += int(factual_eval["outcome"].recovered)
                cf_best_recoveries += int(best_cf["outcome"].recovered)
                factual_recovered_value += factual_val
                cf_best_recovered_value += best_cf["net_val"]

                # Breakdowns
                action_label = selected_candidate.label
                reason = rt["template"].observation.failure_reason.value
                method = rt["template"].observation.payment_method.value
                dec_idx = str(rt["state"].decision_index)

                _track(
                    action_breakdown,
                    action_label,
                    factual_eval["outcome"].recovered,
                    best_cf["outcome"].recovered,
                    factual_val,
                    best_cf["net_val"],
                    regret,
                    is_best,
                    is_tied,
                    is_sub,
                    adv2,
                )
                _track(
                    reason_breakdown,
                    reason,
                    factual_eval["outcome"].recovered,
                    best_cf["outcome"].recovered,
                    factual_val,
                    best_cf["net_val"],
                    regret,
                    is_best,
                    is_tied,
                    is_sub,
                    adv2,
                )
                _track(
                    method_breakdown,
                    method,
                    factual_eval["outcome"].recovered,
                    best_cf["outcome"].recovered,
                    factual_val,
                    best_cf["net_val"],
                    regret,
                    is_best,
                    is_tied,
                    is_sub,
                    adv2,
                )
                _track(
                    index_breakdown,
                    dec_idx,
                    factual_eval["outcome"].recovered,
                    best_cf["outcome"].recovered,
                    factual_val,
                    best_cf["net_val"],
                    regret,
                    is_best,
                    is_tied,
                    is_sub,
                    adv2,
                )

                rt["state"] = advance_episode_state(
                    rt["template"], rt["state"], selected_candidate, factual_eval["outcome"]
                )

    def _compute_derived(node: dict[str, Any]) -> None:
        eligible = node.get("eligible_decisions") or node.get("eligible_paired_decisions")
        if not eligible:
            return
        node["factual_recovery_rate"] = node["factual_recoveries"] / eligible
        node["best_counterfactual_recovery_rate"] = node["counterfactual_recoveries"] / eligible
        node["mean_regret_minor"] = node["regret_minor"] / eligible
        node["fraction_best"] = node["best_count"] / eligible
        node["fraction_tied"] = node["tied_count"] / eligible
        node["fraction_suboptimal"] = node["suboptimal_count"] / eligible
        node["mean_advantage_vs_second_best_minor"] = (
            node["advantage_vs_second_best_minor"] / eligible
        )

    def _compute_breakdowns(breakdown: dict[str, dict[str, Any]]) -> None:
        for val in breakdown.values():
            _compute_derived(val)

    _compute_breakdowns(action_breakdown)
    _compute_breakdowns(reason_breakdown)
    _compute_breakdowns(method_breakdown)
    _compute_breakdowns(index_breakdown)

    headline = {
        "total_decisions": total_decisions,
        "eligible_paired_decisions": eligible_decisions,
        "excluded_decisions": excluded_decisions,
        "mean_feasible_alternatives": feasible_alternatives_sum / eligible_decisions
        if eligible_decisions
        else 0,
        "factual_recoveries": factual_recoveries,
        "counterfactual_recoveries": cf_best_recoveries,
        "factual_net_value_minor": factual_recovered_value,
        "counterfactual_net_value_minor": cf_best_recovered_value,
        "regret_minor": total_regret,
        "best_count": best_count,
        "tied_count": tied_count,
        "suboptimal_count": suboptimal_count,
        "advantage_vs_second_best_minor": advantage_vs_second_best_sum,
        "value_capture_fraction": value_capture_num / value_capture_den
        if value_capture_den > 0
        else 1.0,
    }
    _compute_derived(headline)

    return {
        "artifact_type": ARTIFACT_TYPE,
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "simulator_version": "0.3.0",
        "model_version": "2.0.0",
        "model_sha256": "60190d4c7c72dd2a482310d342131329673879137ce15be8e4451cb13dd2d898",
        "calibration_sha256": "1c5b13a613bf04f3c9015fbe43b27c7ac138c2346310dd346b6c32000c21f85e",
        "policy_version": "2.0.0",
        "policy_config_hash": "ce7712b1ee4e800d54a875eb65a7bc826680e59faa465b54cbc1db7472010b25",
        "seed_group": "final_diagnostic",
        "comparator_semantics": "Evaluate factual selected action vs all other feasible candidate actions. Window is specific to each candidate.",
        "eligibility_definition": "SequentialDecisionKind.ACTION selected, >=2 feasible modelled candidates.",
        "limitations": [
            "POST_HOC_SIMULATED_COUNTERFACTUAL_DIAGNOSTIC",
            "Matched outcomes are generated inside RecoveryIQ's frozen simulator.",
            "This is not production causal evidence.",
            "Simulator 0.3.0 does not model natural recovery during WAIT.",
            "This measures policy action quality inside the hand-designed simulator.",
        ],
        "metrics": headline,
        "breakdown": {
            "action": action_breakdown,
            "failure_reason": reason_breakdown,
            "payment_method": method_breakdown,
            "decision_index": index_breakdown,
        },
    }
