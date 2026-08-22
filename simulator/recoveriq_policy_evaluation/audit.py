from __future__ import annotations

import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import fmean, median
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from recoveriq_ml.artifacts import sha256_file, write_json, write_markdown
from recoveriq_policy.candidates import generate_candidate_actions
from recoveriq_policy.config import (
    CANDIDATE_INDEX,
    CANDIDATE_LABELS,
    HETEROGENEITY_MIN_SUPPORT,
    POLICY_DEVELOPMENT_SEEDS,
    PRIMARY_COST_REGIME,
    REASON_BASELINE_MIN_SUPPORT,
    REASON_METHOD_BASELINE_MIN_SUPPORT,
)
from recoveriq_policy.economics import economic_score, expected_recovered_minor
from recoveriq_policy.models import FrozenBaselineArtifact
from recoveriq_policy.scoring import FrozenRecoveryModelScorer
from recoveriq_policy_evaluation.contexts import generate_observable_policy_cases
from recoveriq_policy_evaluation.oracle import ScenarioOracle
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator

SLICE_COLUMNS = (
    "failure_reason",
    "payment_method",
    "amount_bucket",
    "customer_history_bucket",
    "subscription_tenure_bucket",
    "prior_retry_bucket",
    "health_evidence_bucket",
    "time_since_failure_bucket",
)


def run_development_audit(
    *,
    artifact_root: Path,
    model_root: Path,
    calibration_root: Path,
    frozen_detector_path: Path,
) -> dict[str, Any]:
    output = artifact_root / "development-audit-v1.json"
    if output.exists():
        raise FileExistsError("development audit exists; refusing overwrite")
    started = perf_counter()
    primary = FrozenRecoveryModelScorer(
        model_root=model_root,
        calibration_root=calibration_root,
        model_name="lightgbm",
    )
    no_health = FrozenRecoveryModelScorer(
        model_root=model_root,
        calibration_root=calibration_root,
        model_name="lightgbm_without_health",
    )
    rows: list[dict[str, Any]] = []
    seed_counts: dict[str, int] = {}
    for seed in POLICY_DEVELOPMENT_SEEDS:
        config = SimulatorConfig(seed=seed, cost_regime=PRIMARY_COST_REGIME)
        scenario = ScenarioGenerator(config).generate()
        cases = generate_observable_policy_cases(
            scenario=scenario,
            config=config,
            frozen_detector_path=frozen_detector_path,
        )
        contexts = tuple(case.context for case in cases)
        actions = tuple(
            generate_candidate_actions(case.context, config.resolved_costs) for case in cases
        )
        primary_scores = primary.score_contexts(contexts, actions)
        no_health_scores = no_health.score_contexts(contexts, actions)
        oracle = ScenarioOracle(scenario, config)
        seed_counts[str(seed)] = len(cases)
        for case in cases:
            truth_family = oracle.hidden_family(case.observation)
            during_incident = oracle.during_hidden_incident(case.observation)
            primary_by_label = {
                item.candidate.label: item for item in primary_scores[case.context.decision_key]
            }
            no_health_by_label = {
                item.candidate.label: item for item in no_health_scores[case.context.decision_key]
            }
            for label in CANDIDATE_LABELS:
                prediction = primary_by_label[label]
                no_health_prediction = no_health_by_label[label]
                probability = oracle.probability(case.observation, prediction.candidate)
                realized = oracle.realized_outcome(
                    case.observation,
                    prediction.candidate,
                    probability,
                )
                economics = economic_score(
                    prediction,
                    case.observation.amount_minor,
                )
                oracle_expected = expected_recovered_minor(
                    _decimal(probability),
                    case.observation.amount_minor,
                )
                action = prediction.candidate.recovery_action
                rows.append(
                    {
                        "seed": seed,
                        "decision_key": case.context.decision_key,
                        "decision_at": case.context.decision_at,
                        "payment_amount_minor": case.observation.amount_minor,
                        "failure_reason": case.context.base_features.failure_reason,
                        "payment_method": case.context.base_features.payment_method,
                        "amount_bucket": case.amount_bucket,
                        "customer_history_bucket": case.customer_history_bucket,
                        "subscription_tenure_bucket": case.subscription_tenure_bucket,
                        "prior_retry_bucket": case.prior_retry_bucket,
                        "health_evidence_bucket": case.health_evidence_bucket,
                        "time_since_failure_bucket": case.time_since_failure_bucket,
                        "hidden_failure_family": truth_family,
                        "during_hidden_incident": during_incident,
                        "customer_contact_allowed": (
                            case.context.operational.customer_contact_allowed
                        ),
                        "existing_active_payment_link": (
                            case.context.operational.existing_active_payment_link
                        ),
                        "alternate_method_available": (
                            case.context.operational.alternate_method_available
                        ),
                        "quiet_hours": case.context.operational.quiet_hours,
                        "current_retry_count": case.context.base_features.current_retry_count,
                        "current_contact_count": case.context.base_features.current_contact_count,
                        "candidate_label": label,
                        "candidate_rank": CANDIDATE_INDEX[label],
                        "action_type": action.action_type.value,
                        "delay_hours": action.scheduled_delay_hours,
                        "intervention_cost_minor": action.intervention_cost_minor,
                        "friction_cost_minor": action.friction_cost_minor,
                        "primary_raw_probability": float(prediction.raw_probability),
                        "primary_probability": float(prediction.calibrated_probability),
                        "primary_erv_minor": economics.erv_minor,
                        "no_health_probability": float(no_health_prediction.calibrated_probability),
                        "oracle_probability": probability,
                        "oracle_erv_minor": oracle_expected
                        - action.intervention_cost_minor
                        - action.friction_cost_minor,
                        "realized_recovery": realized,
                        "action_training_count": prediction.support.action_training_count,
                        "calibration_bin": prediction.support.calibration_bin,
                        "calibration_bin_count": prediction.support.calibration_bin_count,
                        "low_support": prediction.support.low_support,
                        "support_reasons": json.dumps(prediction.support.reasons),
                    }
                )
    frame = pd.DataFrame(rows)
    artifact_root.mkdir(parents=True, exist_ok=True)
    candidates_path = artifact_root / "development-candidates-v1.parquet"
    frame.to_parquet(candidates_path, index=False)
    source_digest = sha256_file(candidates_path)
    report, baselines = analyze_development_frame(frame, source_digest)
    report["seed_decision_counts"] = seed_counts
    report["candidate_row_count"] = len(frame)
    report["runtime_seconds"] = perf_counter() - started
    write_json(output, report)
    write_json(
        artifact_root / "development-baselines-v1.json",
        baselines.model_dump(mode="json"),
    )
    write_markdown(
        artifact_root / "development-audit-v1.md",
        render_development_audit(report),
    )
    return report


def analyze_development_frame(
    frame: pd.DataFrame,
    source_digest: str,
) -> tuple[dict[str, Any], FrozenBaselineArtifact]:
    decision_count = int(frame["decision_key"].nunique())
    oracle_probability_top = _top_rows(frame, "oracle_probability")
    oracle_erv_top = _top_rows(frame, "oracle_erv_minor")
    model_top = _top_rows(frame, "primary_probability")
    no_health_top = _top_rows(frame, "no_health_probability")
    global_table = (
        frame.groupby("candidate_label", sort=False)
        .agg(
            mean_oracle_probability=("oracle_probability", "mean"),
            mean_oracle_erv_minor=("oracle_erv_minor", "mean"),
            mean_primary_probability=("primary_probability", "mean"),
        )
        .reset_index()
    )
    global_table["candidate_rank"] = global_table["candidate_label"].map(CANDIDATE_INDEX)
    global_order = tuple(
        global_table.sort_values(
            ["mean_oracle_erv_minor", "candidate_rank"],
            ascending=[False, True],
            kind="stable",
        )["candidate_label"].astype(str)
    )
    global_probability_best = str(
        global_table.sort_values(
            ["mean_oracle_probability", "candidate_rank"],
            ascending=[False, True],
            kind="stable",
        ).iloc[0]["candidate_label"]
    )
    global_best = global_order[0]
    reason_mapping = _lookup_mapping(
        frame,
        ("failure_reason",),
        REASON_BASELINE_MIN_SUPPORT,
        global_best,
    )
    reason_method_mapping = _lookup_mapping(
        frame,
        ("failure_reason", "payment_method"),
        REASON_METHOD_BASELINE_MIN_SUPPORT,
        global_best,
    )
    selections = {
        "model_v1_top_probability": model_top[["decision_key", "candidate_label"]],
        "no_health_top_probability": no_health_top[["decision_key", "candidate_label"]],
        "best_global_action": _constant_selection(frame, global_best),
        "failure_reason_rule": _mapping_selection(
            frame,
            reason_mapping,
            ("failure_reason",),
            global_best,
        ),
        "failure_reason_method_rule": _mapping_selection(
            frame,
            reason_method_mapping,
            ("failure_reason", "payment_method"),
            global_best,
        ),
    }
    strategy_audit = {
        name: _selection_performance(frame, selected, oracle_erv_top)
        for name, selected in selections.items()
    }
    baseline_payload = {
        "development_seeds": POLICY_DEVELOPMENT_SEEDS,
        "selection_metric": "maximum mean hidden oracle ERV minor on policy development",
        "global_best_action": global_best,
        "global_action_order": global_order,
        "failure_reason_mapping": reason_mapping,
        "failure_reason_method_mapping": reason_method_mapping,
        "reason_min_support": REASON_BASELINE_MIN_SUPPORT,
        "reason_method_min_support": REASON_METHOD_BASELINE_MIN_SUPPORT,
        "source_digest": source_digest,
    }
    config_hash = hashlib.sha256(
        json.dumps(
            baseline_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=list,
        ).encode()
    ).hexdigest()
    baselines = FrozenBaselineArtifact.model_validate(
        {**baseline_payload, "config_hash": config_hash}
    )
    dominance = max(Counter(model_top["candidate_label"]).values()) / decision_count
    report = {
        "phase": "policy_development_personalization_audit",
        "development_seeds": list(POLICY_DEVELOPMENT_SEEDS),
        "decision_count": decision_count,
        "candidate_count_per_decision": len(CANDIDATE_LABELS),
        "oracle_best_probability_distribution": _distribution(oracle_probability_top),
        "oracle_best_erv_distribution": _distribution(oracle_erv_top),
        "model_v1_top_action_distribution": _distribution(model_top),
        "no_health_top_action_distribution": _distribution(no_health_top),
        "best_global_action_by_erv": global_best,
        "best_global_action_by_probability": global_probability_best,
        "global_single_action_table": global_table.drop(columns=["candidate_rank"]).to_dict(
            orient="records"
        ),
        "frozen_simple_baselines": baselines.model_dump(mode="json"),
        "development_strategy_audit": strategy_audit,
        "model_probability_ranking": _probability_ranking(frame, model_top),
        "context_action_heterogeneity": _heterogeneity(frame),
        "model_top_action_dominance": dominance,
        "learnability_conclusion": _learnability_conclusion(strategy_audit, dominance),
        "source_digest": source_digest,
    }
    return report, baselines


def _top_rows(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    return (
        frame.sort_values(
            ["decision_key", metric, "candidate_rank"],
            ascending=[True, False, True],
            kind="stable",
        )
        .groupby("decision_key", sort=False, as_index=False)
        .first()
    )


def _distribution(frame: pd.DataFrame) -> dict[str, dict[str, int | float]]:
    counts = Counter(str(value) for value in frame["candidate_label"])
    total = len(frame)
    return {
        label: {"count": counts.get(label, 0), "rate": counts.get(label, 0) / total}
        for label in CANDIDATE_LABELS
    }


def _lookup_mapping(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    minimum_support: int,
    fallback: str,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    keys = list(columns)
    for group_values, subset in frame.groupby(keys, sort=True):
        values = group_values if isinstance(group_values, tuple) else (group_values,)
        support = int(subset["decision_key"].nunique())
        key = "|".join(str(value) for value in values)
        if support < minimum_support:
            mapping[key] = fallback
            continue
        means = (
            subset.groupby("candidate_label", sort=False)["oracle_erv_minor"].mean().reset_index()
        )
        means["candidate_rank"] = means["candidate_label"].map(CANDIDATE_INDEX)
        mapping[key] = str(
            means.sort_values(
                ["oracle_erv_minor", "candidate_rank"],
                ascending=[False, True],
                kind="stable",
            ).iloc[0]["candidate_label"]
        )
    return mapping


def _constant_selection(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    decisions = frame[["decision_key"]].drop_duplicates().copy()
    decisions["candidate_label"] = label
    return decisions


def _mapping_selection(
    frame: pd.DataFrame,
    mapping: dict[str, str],
    columns: tuple[str, ...],
    fallback: str,
) -> pd.DataFrame:
    decisions = frame[["decision_key", *columns]].drop_duplicates().copy()
    decisions["lookup_key"] = decisions[list(columns)].astype(str).agg("|".join, axis=1)
    decisions["candidate_label"] = decisions["lookup_key"].map(mapping).fillna(fallback)
    return decisions[["decision_key", "candidate_label"]]


def _selection_performance(
    frame: pd.DataFrame,
    selections: pd.DataFrame,
    oracle_erv_top: pd.DataFrame,
) -> dict[str, Any]:
    chosen = selections.merge(
        frame,
        on=["decision_key", "candidate_label"],
        how="left",
        validate="one_to_one",
    )
    best = oracle_erv_top[["decision_key", "candidate_label", "oracle_erv_minor"]].rename(
        columns={
            "candidate_label": "oracle_best_label",
            "oracle_erv_minor": "oracle_best_erv_minor",
        }
    )
    chosen = chosen.merge(best, on="decision_key", validate="one_to_one")
    regrets = chosen["oracle_best_erv_minor"] - chosen["oracle_erv_minor"]
    return {
        "mean_oracle_erv_minor": float(chosen["oracle_erv_minor"].mean()),
        "mean_oracle_erv_regret_minor": float(regrets.mean()),
        "median_oracle_erv_regret_minor": float(regrets.median()),
        "p90_oracle_erv_regret_minor": float(regrets.quantile(0.9)),
        "top_1_oracle_erv_agreement": float(
            (chosen["candidate_label"] == chosen["oracle_best_label"]).mean()
        ),
        "action_distribution": _distribution(chosen),
    }


def _probability_ranking(frame: pd.DataFrame, model_top: pd.DataFrame) -> dict[str, Any]:
    oracle_top = _top_rows(frame, "oracle_probability")
    joined = model_top[["decision_key", "candidate_label"]].merge(
        oracle_top[["decision_key", "candidate_label"]].rename(
            columns={"candidate_label": "oracle_label"}
        ),
        on="decision_key",
    )
    top_two = (
        frame.sort_values(
            ["decision_key", "primary_probability", "candidate_rank"],
            ascending=[True, False, True],
            kind="stable",
        )
        .groupby("decision_key", sort=False)
        .head(2)
        .groupby("decision_key")["candidate_label"]
        .agg(tuple)
    )
    oracle_labels = {
        str(key): str(value)
        for key, value in oracle_top.set_index("decision_key")["candidate_label"].items()
    }
    top2 = fmean(float(oracle_labels[str(key)] in labels) for key, labels in top_two.items())
    pair_correct = 0.0
    pair_count = 0
    probability_regrets: list[float] = []
    for _, subset in frame.groupby("decision_key", sort=False):
        oracle = subset["oracle_probability"].to_numpy(dtype=float)
        predicted = subset["primary_probability"].to_numpy(dtype=float)
        chosen = int(np.argmax(predicted))
        best = int(np.argmax(oracle))
        probability_regrets.append(float(oracle[best] - oracle[chosen]))
        for left in range(len(subset)):
            for right in range(left + 1, len(subset)):
                delta = oracle[left] - oracle[right]
                if abs(delta) < 1e-12:
                    continue
                predicted_delta = predicted[left] - predicted[right]
                pair_count += 1
                if abs(predicted_delta) < 1e-12:
                    pair_correct += 0.5
                elif (predicted_delta > 0) == (delta > 0):
                    pair_correct += 1
    ordered = sorted(probability_regrets)
    return {
        "top_1_oracle_agreement": float(
            (joined["candidate_label"] == joined["oracle_label"]).mean()
        ),
        "top_2_oracle_coverage": top2,
        "pairwise_ranking_accuracy": pair_correct / pair_count,
        "probability_regret": {
            "mean": fmean(probability_regrets),
            "median": median(probability_regrets),
            "p90": ordered[round((len(ordered) - 1) * 0.9)],
        },
    }


def _heterogeneity(frame: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for column in SLICE_COLUMNS:
        rows: list[dict[str, Any]] = []
        for value, subset in frame.groupby(column, sort=True):
            count = int(subset["decision_key"].nunique())
            if count < HETEROGENEITY_MIN_SUPPORT:
                continue
            action = (
                subset.groupby("candidate_label", sort=False)
                .agg(
                    mean_oracle_erv_minor=("oracle_erv_minor", "mean"),
                    mean_oracle_probability=("oracle_probability", "mean"),
                    mean_predicted_probability=("primary_probability", "mean"),
                )
                .reset_index()
            )
            action["candidate_rank"] = action["candidate_label"].map(CANDIDATE_INDEX)
            oracle_order = action.sort_values(
                ["mean_oracle_erv_minor", "candidate_rank"],
                ascending=[False, True],
                kind="stable",
            )
            model_order = action.sort_values(
                ["mean_predicted_probability", "candidate_rank"],
                ascending=[False, True],
                kind="stable",
            )
            rows.append(
                {
                    "slice": str(value),
                    "sample_count": count,
                    "oracle_best_action": str(oracle_order.iloc[0]["candidate_label"]),
                    "model_preferred_action": str(model_order.iloc[0]["candidate_label"]),
                    "oracle_advantage_best_vs_second_minor": float(
                        oracle_order.iloc[0]["mean_oracle_erv_minor"]
                        - oracle_order.iloc[1]["mean_oracle_erv_minor"]
                    ),
                    "average_predicted_probability_by_action": {
                        str(row["candidate_label"]): float(row["mean_predicted_probability"])
                        for _, row in action.iterrows()
                    },
                }
            )
        output[column] = rows
    return output


def _learnability_conclusion(
    strategy_audit: dict[str, dict[str, Any]],
    dominance: float,
) -> str:
    model_regret = strategy_audit["model_v1_top_probability"]["mean_oracle_erv_regret_minor"]
    simple_regret = min(
        strategy_audit["best_global_action"]["mean_oracle_erv_regret_minor"],
        strategy_audit["failure_reason_rule"]["mean_oracle_erv_regret_minor"],
        strategy_audit["failure_reason_method_rule"]["mean_oracle_erv_regret_minor"],
    )
    if dominance >= 0.8:
        return (
            "MODEL_TOP_ACTION_IS_HIGHLY_CONCENTRATED; PERSONALIZATION_VALUE_REQUIRES_"
            "VALIDATION_AGAINST_SIMPLE_BASELINES"
        )
    if model_regret < simple_regret:
        return "DEVELOPMENT_SUGGESTS_CONTEXT_VALUE; VALIDATION_REQUIRED"
    return "DEVELOPMENT_DOES_NOT_SHOW_MODEL_ADVANTAGE_OVER_SIMPLE_BASELINES"


def render_development_audit(report: dict[str, Any]) -> str:
    ranking = report["model_probability_ranking"]
    strategies = report["development_strategy_audit"]
    lines = [
        "# Policy V1 Development Personalization Audit",
        "",
        f"Decisions: {report['decision_count']}",
        f"Best global ERV action: `{report['best_global_action_by_erv']}`",
        f"Best global probability action: `{report['best_global_action_by_probability']}`",
        f"Model top-action dominance: {report['model_top_action_dominance']:.6f}",
        "",
        f"Model top-1 oracle-probability agreement: {ranking['top_1_oracle_agreement']:.6f}",
        f"Model top-2 oracle-probability coverage: {ranking['top_2_oracle_coverage']:.6f}",
        f"Model pairwise ranking accuracy: {ranking['pairwise_ranking_accuracy']:.6f}",
        "",
        "## Development ERV-regret comparison",
        "",
    ]
    for name, values in strategies.items():
        lines.append(
            f"- `{name}`: mean oracle ERV {values['mean_oracle_erv_minor']:.2f}; "
            f"mean regret {values['mean_oracle_erv_regret_minor']:.2f}; "
            f"top-1 {values['top_1_oracle_erv_agreement']:.6f}"
        )
    lines.extend(
        (
            "",
            f"Conclusion: **{report['learnability_conclusion']}**",
            "",
            "Hidden oracle values were used only in the development evaluation layer.",
            "No RecoverIQ policy configuration or validation result exists yet.",
        )
    )
    return "\n".join(lines)


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))
