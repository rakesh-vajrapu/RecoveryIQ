from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from recoveriq_sequential.config import (
    MAX_AUTONOMOUS_INTERVENTIONS,
    MAX_CONTACTS,
    MAX_RETRIES,
    SEQUENTIAL_CANDIDATE_INDEX,
)
from recoveriq_sequential.episodes import (
    advance_episode_state,
    build_episode_templates,
    generate_sequential_candidates,
    initial_episode_state,
)
from recoveriq_sequential.models import (
    EpisodeTermination,
    SequentialCandidate,
    SequentialEpisodeState,
    SequentialEpisodeTemplate,
)
from recoveriq_sequential.oracle import SequentialScenarioOracle
from recoveriq_sequential_policy.engine import RecoverIQSequentialPolicyEngine
from recoveriq_sequential_policy.metrics import paired_lift, strategy_metrics
from recoveriq_sequential_policy.models import (
    FrozenSequentialBaselines,
    SequentialCandidateScore,
    SequentialDecisionKind,
)
from recoveriq_sequential_policy.scoring import SequentialModelV2Scorer
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator

FIXED_RETRY = "fixed_retry_workflow"
REMINDER_RETRY = "reminder_retry_workflow"
SIMPLE_RULE = "simple_sequential_observable_rule"
BEST_GLOBAL = "best_global_sequential"
PROBABILITY = "sequential_probability_policy"
RECOVERIQ = "recoveriq_sequential_erv_v2"
ORACLE = "greedy_hidden_oracle"
STRATEGIES = (
    FIXED_RETRY,
    REMINDER_RETRY,
    SIMPLE_RULE,
    BEST_GLOBAL,
    PROBABILITY,
    RECOVERIQ,
    ORACLE,
)
PRIMARY_COMPARATORS = (FIXED_RETRY, REMINDER_RETRY, SIMPLE_RULE, BEST_GLOBAL, PROBABILITY)


@dataclass(slots=True)
class EpisodeRuntime:
    template: SequentialEpisodeTemplate
    state: SequentialEpisodeState
    actions: list[dict[str, Any]] = field(default_factory=list)
    decisions: int = 0
    human_review: bool = False
    stop_reason: str | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)


def evaluate_policy_seed_group(
    *,
    seeds: tuple[int, ...],
    baselines: FrozenSequentialBaselines,
    normalized_margin_threshold: float,
    model_root: Path,
    calibration_root: Path,
    strategies: tuple[str, ...] = STRATEGIES,
    capture_traces: bool = True,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    started = perf_counter()
    scorer = SequentialModelV2Scorer(
        model_root=model_root,
        calibration_root=calibration_root,
    )
    rows: list[dict[str, Any]] = []
    cohort_hashes: dict[str, dict[str, str]] = {}
    successful_trace: dict[str, Any] | None = None
    failure_trace: dict[str, Any] | None = None
    for seed in seeds:
        config = SimulatorConfig(seed=seed)
        scenario = ScenarioGenerator(config).generate()
        templates = build_episode_templates(scenario, seed)
        cohort_digest = _cohort_digest(templates)
        cohort_hashes[str(seed)] = {}
        oracle = SequentialScenarioOracle(scenario, config)
        for strategy in strategies:
            cohort_hashes[str(seed)][strategy] = cohort_digest
            strategy_rows, traces = execute_strategy(
                seed=seed,
                strategy=strategy,
                templates=templates,
                config=config,
                oracle=oracle,
                scorer=scorer,
                baselines=baselines,
                normalized_margin_threshold=normalized_margin_threshold,
                capture_traces=capture_traces and strategy == RECOVERIQ,
            )
            rows.extend(strategy_rows)
            successful_trace = successful_trace or traces.get("successful")
            failure_trace = failure_trace or traces.get("failure")
    records = pd.DataFrame(rows)
    metrics = {
        strategy: strategy_metrics(records[records["strategy"] == strategy])
        for strategy in strategies
    }
    lifts = {
        comparator: paired_lift(records, RECOVERIQ, comparator)
        for comparator in PRIMARY_COMPARATORS
        if RECOVERIQ in strategies and comparator in strategies
    }
    primary = records[records["strategy"] == RECOVERIQ]
    report = {
        "strategies": metrics,
        "recoveriq_paired_lifts": lifts,
        "initial_cohort_hashes": cohort_hashes,
        "same_initial_hidden_episode_for_all_strategies": all(
            len(set(strategy_hashes.values())) == 1 for strategy_hashes in cohort_hashes.values()
        ),
        "sequence_analysis": _sequence_analysis(primary),
        "action_transition_matrix": _transition_matrix(primary),
        "personalization_analysis": _personalization(primary),
        "sequential_oracle_regret": (
            paired_lift(records, ORACLE, RECOVERIQ)
            if RECOVERIQ in strategies and ORACLE in strategies
            else None
        ),
        "runtime_seconds": perf_counter() - started,
    }
    traces = {
        "successful_adaptive_trace": successful_trace,
        "bounded_failure_trace": failure_trace,
    }
    return report, records, traces


def execute_strategy(
    *,
    seed: int,
    strategy: str,
    templates: tuple[SequentialEpisodeTemplate, ...],
    config: SimulatorConfig,
    oracle: SequentialScenarioOracle,
    scorer: SequentialModelV2Scorer,
    baselines: FrozenSequentialBaselines,
    normalized_margin_threshold: float,
    capture_traces: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    runtimes = [
        EpisodeRuntime(template=item, state=initial_episode_state(item)) for item in templates
    ]
    engine = RecoverIQSequentialPolicyEngine(normalized_margin_threshold)
    for _ in range(MAX_AUTONOMOUS_INTERVENTIONS):
        active = [item for item in runtimes if item.state.termination is EpisodeTermination.ACTIVE]
        if not active:
            break
        candidates_by_episode: list[tuple[SequentialCandidate, ...]] = []
        scoring_rows: list[
            tuple[SequentialEpisodeTemplate, SequentialEpisodeState, SequentialCandidate]
        ] = []
        for runtime in active:
            candidates = generate_sequential_candidates(
                runtime.template, runtime.state, config.resolved_costs
            )
            candidates_by_episode.append(candidates)
            if strategy in {PROBABILITY, RECOVERIQ}:
                scoring_rows.extend(
                    (runtime.template, runtime.state, candidate) for candidate in candidates
                )
        batch_scores = scorer.score(scoring_rows) if scoring_rows else []
        score_offset = 0
        for runtime, candidates in zip(active, candidates_by_episode, strict=True):
            runtime.decisions += 1
            scores: tuple[SequentialCandidateScore, ...] = ()
            if strategy in {PROBABILITY, RECOVERIQ}:
                scores = tuple(batch_scores[score_offset : score_offset + len(candidates)])
                score_offset += len(candidates)
            selected, decision_kind, reason, margin = _select(
                strategy=strategy,
                runtime=runtime,
                candidates=candidates,
                scores=scores,
                baselines=baselines,
                engine=engine,
                oracle=oracle,
            )
            trace_decision = _trace_decision(runtime, scores, decision_kind, reason, margin)
            if selected is None:
                if decision_kind is SequentialDecisionKind.HUMAN_REVIEW:
                    runtime.human_review = True
                    runtime.state = runtime.state.model_copy(
                        update={"termination": EpisodeTermination.HUMAN_REVIEW}
                    )
                else:
                    runtime.stop_reason = reason
                    runtime.state = runtime.state.model_copy(
                        update={"termination": EpisodeTermination.STOP}
                    )
                if capture_traces:
                    runtime.trace.append(trace_decision)
                continue
            outcome = oracle.execute(runtime.template, runtime.state, selected)
            event = {
                "decision_index": runtime.state.decision_index,
                "label": selected.label,
                "action_type": selected.recovery_action.action_type.value,
                "execute_at": selected.recovery_action.execute_at,
                "recovered": outcome.recovered,
                "intervention_cost_minor": selected.recovery_action.intervention_cost_minor,
                "friction_cost_minor": selected.recovery_action.friction_cost_minor,
            }
            runtime.actions.append(event)
            if capture_traces:
                trace_decision["outcome"] = {
                    "recovered": outcome.recovered,
                    "observed_at": outcome.executed_at,
                    "recovered_amount_minor": outcome.recovered_amount_minor,
                }
                runtime.trace.append(trace_decision)
            runtime.state = advance_episode_state(
                runtime.template,
                runtime.state,
                selected,
                outcome,
            )
    records = [_episode_record(seed, strategy, item, config) for item in runtimes]
    traces: dict[str, Any] = {}
    if capture_traces:
        for runtime, record in zip(runtimes, records, strict=True):
            if "successful" not in traces and record["recovered"] and len(runtime.actions) >= 2:
                traces["successful"] = _finalize_trace(runtime, record, "SUCCESSFUL_ADAPTIVE")
            if (
                "failure" not in traces
                and not record["recovered"]
                and len(runtime.actions) == MAX_AUTONOMOUS_INTERVENTIONS
            ):
                traces["failure"] = _finalize_trace(runtime, record, "BOUNDED_FAILURE")
            if len(traces) == 2:
                break
    return records, traces


def _select(
    *,
    strategy: str,
    runtime: EpisodeRuntime,
    candidates: tuple[SequentialCandidate, ...],
    scores: tuple[SequentialCandidateScore, ...],
    baselines: FrozenSequentialBaselines,
    engine: RecoverIQSequentialPolicyEngine,
    oracle: SequentialScenarioOracle,
) -> tuple[
    SequentialCandidate | None,
    SequentialDecisionKind,
    str,
    float | None,
]:
    if strategy == RECOVERIQ:
        decision = engine.decide(runtime.state, scores)
        return (
            decision.selected.candidate if decision.selected else None,
            decision.kind,
            decision.reason,
            decision.normalized_margin,
        )
    if not candidates:
        return None, SequentialDecisionKind.STOP, "NO_FEASIBLE_ACTION", None
    if strategy == PROBABILITY:
        selected_score = min(
            scores,
            key=lambda item: (
                -item.probability,
                SEQUENTIAL_CANDIDATE_INDEX[item.candidate.label],
            ),
        )
        return selected_score.candidate, SequentialDecisionKind.ACTION, "MAX_PROBABILITY", None
    if strategy == ORACLE:
        values = [
            (
                _oracle_erv(runtime, candidate, oracle),
                SEQUENTIAL_CANDIDATE_INDEX[candidate.label],
                candidate,
            )
            for candidate in candidates
        ]
        best = min(values, key=lambda item: (-item[0], item[1]))
        if best[0] <= 0:
            return None, SequentialDecisionKind.STOP, "ORACLE_NON_POSITIVE_ERV", None
        return best[2], SequentialDecisionKind.ACTION, "GREEDY_HIDDEN_ORACLE", None
    labels = {candidate.label: candidate for candidate in candidates}
    desired: tuple[str, ...]
    index = runtime.state.decision_index
    if strategy == FIXED_RETRY:
        desired = {1: ("RETRY_LATER_6H",), 2: ("RETRY_LATER_12H",), 3: ("RETRY_LATER_24H",)}[index]
    elif strategy == REMINDER_RETRY:
        desired = {1: ("SEND_NUDGE",), 2: ("RETRY_LATER_6H",), 3: ("RETRY_LATER_24H",)}[index]
    elif strategy == BEST_GLOBAL:
        desired = baselines.stage_rankings[str(index)]
    elif strategy == SIMPLE_RULE:
        key = f"{runtime.template.observation.failure_reason.value}|{index}"
        mapped = baselines.simple_mapping.get(key)
        desired = ((mapped,) if mapped else ()) + baselines.stage_rankings[str(index)]
    else:
        raise ValueError(f"unknown sequential strategy: {strategy}")
    selected = next((labels[label] for label in desired if label in labels), None)
    return (
        selected,
        SequentialDecisionKind.ACTION if selected else SequentialDecisionKind.STOP,
        "FROZEN_BASELINE_MAPPING" if selected else "BASELINE_ACTION_INFEASIBLE",
        None,
    )


def _oracle_erv(
    runtime: EpisodeRuntime,
    candidate: SequentialCandidate,
    oracle: SequentialScenarioOracle,
) -> int:
    probability = oracle.probability(runtime.template, runtime.state, candidate)
    expected = int(
        (Decimal(str(probability)) * Decimal(runtime.template.observation.amount_minor)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return (
        expected
        - candidate.recovery_action.intervention_cost_minor
        - candidate.recovery_action.friction_cost_minor
    )


def _trace_decision(
    runtime: EpisodeRuntime,
    scores: tuple[SequentialCandidateScore, ...],
    kind: SequentialDecisionKind,
    reason: str,
    margin: float | None,
) -> dict[str, Any]:
    return {
        "decision_index": runtime.state.decision_index,
        "decision_at": runtime.state.decision_at,
        "observable_context": {
            "failure_reason": runtime.template.observation.failure_reason.value,
            "payment_method": runtime.template.observation.payment_method.value,
            "amount_minor": runtime.template.observation.amount_minor,
            "elapsed_hours": (
                runtime.state.decision_at - runtime.template.observation.observed_at
            ).total_seconds()
            / 3600,
            "prior_interventions": runtime.state.intervention_count,
            "retries": runtime.state.retry_count,
            "contacts": runtime.state.contact_count,
            "last_action": runtime.state.last_action_label,
            "previous_result": runtime.state.previous_intervention_result.value,
        },
        "candidates": [
            {
                "label": score.candidate.label,
                "probability": score.probability,
                "incremental_erv_minor": score.incremental_erv_minor,
                "action_stage_support": score.action_stage_support,
                "calibration_bin": score.calibration_bin,
                "calibration_bin_support": score.calibration_bin_support,
                "supported": score.supported,
            }
            for score in scores
        ],
        "policy_checks": {
            "decision_kind": kind.value,
            "reason": reason,
            "normalized_margin": margin,
        },
        "selected_action": (
            next(
                (
                    score.candidate.label
                    for score in scores
                    if kind is SequentialDecisionKind.ACTION
                    and reason == "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV"
                    and score.incremental_erv_minor
                    == max(item.incremental_erv_minor for item in scores)
                ),
                None,
            )
        ),
    }


def _episode_record(
    seed: int,
    strategy: str,
    runtime: EpisodeRuntime,
    config: SimulatorConfig,
) -> dict[str, Any]:
    state = runtime.state
    intervention_cost = sum(int(row["intervention_cost_minor"]) for row in runtime.actions)
    if runtime.human_review:
        intervention_cost += config.resolved_costs.human_review_minor
    friction_cost = sum(int(row["friction_cost_minor"]) for row in runtime.actions)
    gross = runtime.template.observation.amount_minor if state.recovered else 0
    recovery_hours = (
        (state.recovered_at - runtime.template.observation.observed_at).total_seconds() / 3600
        if state.recovered_at is not None
        else None
    )
    action_labels = [str(row["label"]) for row in runtime.actions]
    violations = _policy_violations(runtime)
    observation = runtime.template.observation
    tenure_days = max(
        0.0,
        (observation.observed_at - runtime.template.subscription.created_at).total_seconds()
        / 86_400,
    )
    return {
        "seed": seed,
        "strategy": strategy,
        "episode_id": state.episode_id,
        "failure_reason": observation.failure_reason.value,
        "payment_method": observation.payment_method.value,
        "amount_minor": observation.amount_minor,
        "amount_bucket": _amount_bucket(observation.amount_minor),
        "prior_success_bucket": _prior_success_bucket(observation.customer_prior_success_rate),
        "subscription_tenure_bucket": _tenure_bucket(tenure_days),
        "recovered": state.recovered,
        "gross_recovered_minor": gross,
        "net_recovery_value_minor": gross - intervention_cost - friction_cost,
        "intervention_cost_minor": intervention_cost,
        "friction_cost_minor": friction_cost,
        "retry_count": state.retry_count,
        "contact_count": state.contact_count,
        "payment_link_count": state.payment_link_count
        - int(runtime.template.initial_active_payment_link),
        "method_update_count": state.method_update_count,
        "alternate_method_count": state.alternate_method_count,
        "human_review": runtime.human_review,
        "stop_outcome": not state.recovered and not runtime.human_review,
        "stop_reason": runtime.stop_reason or state.termination.value,
        "action_count": len(runtime.actions),
        "decision_count": runtime.decisions,
        "recovery_time_hours": recovery_hours,
        "recovery_action": state.recovery_action_label,
        "recovery_decision_index": state.recovery_decision_index,
        "recovery_timestamp": state.recovered_at,
        "recovered_amount_minor": gross,
        "sequence": " -> ".join(action_labels) if action_labels else "NO_ACTION",
        "actions_json": json.dumps(runtime.actions, sort_keys=True, default=str),
        "policy_violations": len(violations),
        "policy_violation_details": ";".join(violations),
    }


def _policy_violations(runtime: EpisodeRuntime) -> list[str]:
    violations: list[str] = []
    state = runtime.state
    if len(runtime.actions) > MAX_AUTONOMOUS_INTERVENTIONS:
        violations.append("MAX_INTERVENTIONS")
    if state.retry_count > MAX_RETRIES:
        violations.append("MAX_RETRIES")
    if state.contact_count > MAX_CONTACTS:
        violations.append("MAX_CONTACTS")
    if sum(row["label"] == "CREATE_PAYMENT_LINK" for row in runtime.actions) > 1:
        violations.append("DUPLICATE_PAYMENT_LINK")
    recovered_actions = sum(bool(row["recovered"]) for row in runtime.actions)
    if recovered_actions > 1 or recovered_actions != int(state.recovered):
        violations.append("ATTRIBUTION_ONCE")
    if any(
        isinstance(row["execute_at"], datetime) and row["execute_at"] > state.horizon_at
        for row in runtime.actions
    ):
        violations.append("RECOVERY_HORIZON")
    return violations


def _finalize_trace(
    runtime: EpisodeRuntime,
    record: dict[str, Any],
    trace_type: str,
) -> dict[str, Any]:
    return {
        "trace_type": trace_type,
        "episode_id": runtime.state.episode_id,
        "initial_failure": {
            "observed_at": runtime.template.observation.observed_at,
            "failure_reason": runtime.template.observation.failure_reason.value,
            "payment_method": runtime.template.observation.payment_method.value,
            "amount_minor": runtime.template.observation.amount_minor,
        },
        "decisions": runtime.trace,
        "final": {
            "termination": runtime.state.termination.value,
            "recovered": record["recovered"],
            "recovered_amount_minor": record["recovered_amount_minor"],
            "total_intervention_cost_minor": record["intervention_cost_minor"],
            "total_friction_cost_minor": record["friction_cost_minor"],
            "simulated_net_recovery_value_minor": record["net_recovery_value_minor"],
            "action_count": record["action_count"],
            "no_fourth_autonomous_action": record["action_count"] <= 3,
        },
    }


def _cohort_digest(templates: tuple[SequentialEpisodeTemplate, ...]) -> str:
    payload = "|".join(
        f"{item.episode_id}:{item.observation.observed_at.isoformat()}" for item in templates
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _sequence_analysis(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for sequence, group in frame.groupby("sequence", sort=False):
        reasons = Counter(group["failure_reason"].astype(str)).most_common(3)
        rows.append(
            {
                "sequence": str(sequence),
                "count": len(group),
                "recovery_rate": float(group["recovered"].mean()),
                "simulated_net_value_minor": int(group["net_recovery_value_minor"].sum()),
                "main_observable_failure_reasons": [
                    {"reason": reason, "count": count} for reason, count in reasons
                ],
            }
        )
    return sorted(rows, key=lambda row: (-int(row["count"]), str(row["sequence"])))[:15]


def _transition_matrix(frame: pd.DataFrame) -> list[dict[str, Any]]:
    counts: Counter[tuple[int, str, str]] = Counter()
    for payload in frame["actions_json"] if not frame.empty else []:
        actions = json.loads(str(payload))
        for previous, following in pairwise(actions):
            counts[(int(following["decision_index"]), previous["label"], following["label"])] += 1
    return [
        {
            "decision_index": index,
            "previous_action": previous,
            "next_action": following,
            "count": count,
        }
        for (index, previous, following), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def _personalization(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {}
    dimensions = (
        "failure_reason",
        "payment_method",
        "amount_bucket",
        "prior_success_bucket",
        "subscription_tenure_bucket",
    )
    output: dict[str, Any] = {}
    for dimension in dimensions:
        rows: list[dict[str, Any]] = []
        for value, group in frame.groupby(dimension, sort=True):
            sequence_counts = Counter(group["sequence"].astype(str))
            top_sequence, top_count = sequence_counts.most_common(1)[0]
            rows.append(
                {
                    "value": str(value),
                    "episodes": len(group),
                    "unique_sequences": len(sequence_counts),
                    "top_sequence": top_sequence,
                    "top_sequence_share": top_count / len(group),
                    "recovery_rate": float(group["recovered"].mean()),
                }
            )
        output[dimension] = rows
    later_actions: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for payload in frame["actions_json"]:
        for action in json.loads(str(payload))[1:]:
            later_actions["FAILED"][str(action["label"])] += 1
    output["previous_intervention_result"] = {
        result: dict(counter.most_common()) for result, counter in later_actions.items()
    }
    output["adaptive_sequence_count"] = int((frame["action_count"] > 1).sum())
    return output


def _amount_bucket(amount: int) -> str:
    return "LOW" if amount < 100_000 else "MEDIUM" if amount < 400_000 else "HIGH"


def _prior_success_bucket(rate: float | None) -> str:
    if rate is None:
        return "UNKNOWN"
    return "LOW" if rate < 0.75 else "MEDIUM" if rate < 0.95 else "HIGH"


def _tenure_bucket(days: float) -> str:
    return "NEW" if days < 90 else "ESTABLISHED" if days < 365 else "LONG_TENURE"
