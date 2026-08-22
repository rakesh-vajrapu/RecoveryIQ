from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import fmean, median
from time import perf_counter
from typing import Any

import pandas as pd

from recoveriq_ml.artifacts import sha256_file, write_json, write_markdown
from recoveriq_policy.config import (
    OVERALL_FINAL_SEEDS,
    PHASE4_HELDOUT_SEEDS,
    POLICY_DEVELOPMENT_SEEDS,
    POLICY_VALIDATION_SEEDS,
)
from recoveriq_policy.models import FrozenBaselineArtifact, FrozenPolicyArtifact
from recoveriq_policy_evaluation.dataset import generate_candidate_evaluation_frame
from recoveriq_policy_evaluation.metrics import (
    diagnostic_slices,
    paired_lift,
    strategy_metrics,
    strategy_metrics_by_seed,
)
from recoveriq_policy_evaluation.strategy import STRATEGIES, execute_strategies

PRIMARY_STRATEGY = "recoveriq_erv_policy_v1"
ORACLE_AMBIGUITY_NORMALIZED_MARGIN = 0.005
COMPARATORS = (
    "fixed_retry_first",
    "generic_reminder_first",
    "best_global_action",
    "failure_reason_rule",
    "failure_reason_method_rule",
    "model_probability_policy",
    "recoveriq_no_health_research",
)


def run_validation_once(
    *,
    artifact_root: Path,
    model_root: Path,
    calibration_root: Path,
    frozen_detector_path: Path,
) -> dict[str, Any]:
    """Execute the registered validation seeds once against the frozen policy."""
    output = artifact_root / "validation-evaluation-v1.json"
    attempt_path = artifact_root / "validation-attempt-v1.json"
    if output.exists() or attempt_path.exists():
        raise FileExistsError(
            "registered Policy V1 validation was already attempted; refusing overwrite or rerun"
        )
    policy_path = artifact_root / "recoveriq-policy-v1.json"
    baselines_path = artifact_root / "development-baselines-v1.json"
    policy = FrozenPolicyArtifact.model_validate_json(policy_path.read_text(encoding="utf-8"))
    baselines = FrozenBaselineArtifact.model_validate_json(
        baselines_path.read_text(encoding="utf-8")
    )
    _assert_frozen_protocol(policy, baselines, baselines_path)

    artifact_root.mkdir(parents=True, exist_ok=True)
    write_json(
        attempt_path,
        {
            "artifact_type": "registered_policy_validation_attempt",
            "policy_config_hash": policy.config_hash,
            "validation_seeds": POLICY_VALIDATION_SEEDS,
            "status": "STARTED",
            "rerun_rule": (
                "never overwrite; an implementation-bug rerun requires an explicit INVALID record"
            ),
        },
    )
    started = perf_counter()
    frame, seed_counts, workflows, generation_seconds = generate_candidate_evaluation_frame(
        seeds=POLICY_VALIDATION_SEEDS,
        model_root=model_root,
        calibration_root=calibration_root,
        frozen_detector_path=frozen_detector_path,
        include_existing_workflows=True,
    )
    frame.to_parquet(artifact_root / "validation-candidates-v1.parquet", index=False)
    report, records, trace, _ = evaluate_validation_frame(
        frame,
        policy=policy,
        baselines=baselines,
        workflows=workflows,
        capture_trace=True,
    )
    records.to_parquet(artifact_root / "validation-policy-records-v1.parquet", index=False)
    report.update(
        {
            "artifact_type": "recoveriq_policy_validation",
            "policy_version": policy.policy_version,
            "policy_config_hash": policy.config_hash,
            "validation_seeds": POLICY_VALIDATION_SEEDS,
            "seed_decision_counts": seed_counts,
            "candidate_row_count": len(frame),
            "dataset_generation_seconds": generation_seconds,
            "total_runtime_seconds": perf_counter() - started,
            "final_seeds_untouched": True,
            "overall_final_seeds": OVERALL_FINAL_SEEDS,
            "phase4_heldout_seeds_not_used": PHASE4_HELDOUT_SEEDS,
        }
    )
    if trace is not None:
        write_json(artifact_root / "decision-trace-example-v1.json", trace)
    write_json(output, report)
    write_markdown(artifact_root / "validation-report-v1.md", render_validation_report(report))
    write_json(
        attempt_path,
        {
            "artifact_type": "registered_policy_validation_attempt",
            "policy_config_hash": policy.config_hash,
            "validation_seeds": POLICY_VALIDATION_SEEDS,
            "status": "COMPLETED",
            "result_sha256": sha256_file(output),
            "overall_gate_pass": report["validation_gates"]["overall"]["pass"],
        },
    )
    validated_payload = policy.model_dump(mode="json")
    validated_payload["validation_status"] = (
        "EXECUTED_ONCE_PASS"
        if report["validation_gates"]["overall"]["pass"]
        else "EXECUTED_ONCE_FAIL"
    )
    write_json(policy_path, validated_payload)
    return report


def evaluate_validation_frame(
    frame: pd.DataFrame,
    *,
    policy: FrozenPolicyArtifact,
    baselines: FrozenBaselineArtifact,
    workflows: dict[str, Any] | None = None,
    capture_trace: bool = True,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any] | None, list[dict[str, Any]]]:
    """Evaluate a prepared frame; usable with unregistered smoke data before validation."""
    started = perf_counter()
    records, trace, block_rows = execute_strategies(
        frame,
        baselines=baselines,
        policy_config_hash=policy.config_hash,
        normalized_margin_threshold=policy.normalized_erv_margin_threshold,
        strategy_names=STRATEGIES,
        capture_trace=capture_trace,
    )
    metrics = {name: strategy_metrics(records[records["strategy"] == name]) for name in STRATEGIES}
    by_seed = {
        name: strategy_metrics_by_seed(records[records["strategy"] == name]) for name in STRATEGIES
    }
    lifts = {
        comparator: paired_lift(records, PRIMARY_STRATEGY, comparator) for comparator in COMPARATORS
    }
    primary = records[records["strategy"] == PRIMARY_STRATEGY].copy()
    report: dict[str, Any] = {
        "first_intervention_view": {
            "strategy_metrics": metrics,
            "strategy_metrics_by_seed": by_seed,
            "recoveriq_paired_lifts": lifts,
        },
        "existing_workflow_view": _existing_workflow_metrics(workflows or {}),
        "diagnostic_slices": {
            "hidden_failure_family": diagnostic_slices(primary, "hidden_failure_family"),
            "observable_failure_reason": diagnostic_slices(primary, "failure_reason"),
            "amount_bucket": diagnostic_slices(primary, "amount_bucket"),
        },
        "abstention_analysis": _abstention_analysis(primary, frame),
        "false_safety_analysis": _false_safety_analysis(frame, block_rows),
        "action_dominance_analysis": _action_dominance(metrics),
        "validation_gates": _validation_gates(metrics, lifts),
        "strategy_evaluation_seconds": perf_counter() - started,
    }
    if trace is not None:
        matching = primary[primary["decision_key"] == trace["observable_context"]["decision_key"]]
        if not matching.empty:
            selected = matching.iloc[0]
            trace["outcome"] = {
                "selected_action": selected["selected_action"],
                "recovered": bool(selected["recovered"]),
                "simulated_recovered_amount_minor": int(selected["gross_recovered_minor"]),
                "simulated_net_recovery_value_minor": int(selected["net_recovery_value_minor"]),
                "recovery_time_hours": (
                    None
                    if pd.isna(selected["recovery_time_hours"])
                    else float(selected["recovery_time_hours"])
                ),
            }
    return report, records, trace, block_rows


def rebuild_sealed_validation_analysis(*, artifact_root: Path, reason: str) -> dict[str, Any]:
    """Correct derived analysis from sealed records without rerunning registered worlds."""
    output = artifact_root / "validation-evaluation-v1.json"
    attempt_path = artifact_root / "validation-attempt-v1.json"
    frame_path = artifact_root / "validation-candidates-v1.parquet"
    records_path = artifact_root / "validation-policy-records-v1.parquet"
    attempt: dict[str, Any] = json.loads(attempt_path.read_text(encoding="utf-8"))
    if attempt.get("status") != "COMPLETED" or not output.exists():
        raise RuntimeError("sealed validation must be complete before analysis-only correction")
    report: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    frame = pd.read_parquet(frame_path)
    records = _normalize_oracle_stop_option(pd.read_parquet(records_path))
    metrics = {name: strategy_metrics(records[records["strategy"] == name]) for name in STRATEGIES}
    by_seed = {
        name: strategy_metrics_by_seed(records[records["strategy"] == name]) for name in STRATEGIES
    }
    lifts = {
        comparator: paired_lift(records, PRIMARY_STRATEGY, comparator) for comparator in COMPARATORS
    }
    primary = records[records["strategy"] == PRIMARY_STRATEGY].copy()
    report["first_intervention_view"] = {
        "strategy_metrics": metrics,
        "strategy_metrics_by_seed": by_seed,
        "recoveriq_paired_lifts": lifts,
    }
    report["diagnostic_slices"] = {
        "hidden_failure_family": diagnostic_slices(primary, "hidden_failure_family"),
        "observable_failure_reason": diagnostic_slices(primary, "failure_reason"),
        "amount_bucket": diagnostic_slices(primary, "amount_bucket"),
    }
    report["abstention_analysis"] = _abstention_analysis(primary, frame)
    report["action_dominance_analysis"] = _action_dominance(metrics)
    report["validation_gates"] = _validation_gates(metrics, lifts)
    corrections = list(report.get("analysis_corrections", []))
    corrections.append(
        {
            "reason": reason,
            "scope": "derived metrics and abstention analysis only",
            "registered_worlds_rerun": False,
            "strategy_decisions_rerun": False,
            "policy_changed": False,
        }
    )
    report["analysis_corrections"] = corrections
    records.to_parquet(records_path, index=False)
    write_json(output, report)
    write_markdown(artifact_root / "validation-report-v1.md", render_validation_report(report))
    attempt["result_sha256"] = sha256_file(output)
    attempt["analysis_correction_count"] = len(corrections)
    write_json(attempt_path, attempt)
    return report


def _normalize_oracle_stop_option(records: pd.DataFrame) -> pd.DataFrame:
    normalized = records.copy()
    normalized["oracle_best_erv_minor"] = normalized["oracle_best_erv_minor"].clip(lower=0)
    normalized["oracle_second_erv_minor"] = normalized["oracle_second_erv_minor"].clip(lower=0)
    normalized["oracle_erv_regret_minor"] = (
        normalized["oracle_best_erv_minor"] - normalized["selected_oracle_erv_minor"]
    )
    return normalized


def _assert_frozen_protocol(
    policy: FrozenPolicyArtifact,
    baselines: FrozenBaselineArtifact,
    baselines_path: Path,
) -> None:
    if policy.validation_status != "PENDING_AT_FREEZE":
        raise RuntimeError("frozen policy is not pending its first validation")
    if policy.development_seeds != POLICY_DEVELOPMENT_SEEDS:
        raise RuntimeError("frozen development seed protocol does not match registration")
    if policy.validation_seeds != POLICY_VALIDATION_SEEDS:
        raise RuntimeError("frozen validation seed protocol does not match registration")
    if policy.final_seeds != OVERALL_FINAL_SEEDS:
        raise RuntimeError("overall-final seed guard does not match registration")
    if baselines.development_seeds != POLICY_DEVELOPMENT_SEEDS:
        raise RuntimeError("baseline artifact was not frozen from development seeds only")
    if policy.baseline_artifact_sha256 != sha256_file(baselines_path):
        raise RuntimeError("frozen baseline artifact digest changed after policy freeze")
    forbidden = set(POLICY_DEVELOPMENT_SEEDS) & set(POLICY_VALIDATION_SEEDS)
    forbidden |= set(POLICY_VALIDATION_SEEDS) & set(OVERALL_FINAL_SEEDS)
    forbidden |= set(POLICY_VALIDATION_SEEDS) & set(PHASE4_HELDOUT_SEEDS)
    if forbidden:
        raise RuntimeError(f"registered seed groups overlap: {sorted(forbidden)}")


def _validation_gates(
    metrics: dict[str, dict[str, Any]],
    lifts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    primary = metrics[PRIMARY_STRATEGY]
    fixed_net = lifts["fixed_retry_first"]["net_recovery_value_minor_difference"]["mean"]
    personalization_details: dict[str, Any] = {}
    personalization_pass = False
    for comparator in ("best_global_action", "failure_reason_rule"):
        net = lifts[comparator]["net_recovery_value_minor_difference"]["mean"]
        regret = lifts[comparator]["oracle_erv_regret_minor_difference"]["mean"]
        comparator_pass = net > 0 or regret <= -1
        personalization_details[comparator] = {
            "mean_paired_net_value_difference_minor": net,
            "mean_paired_oracle_erv_regret_difference_minor": regret,
            "pass": comparator_pass,
        }
        personalization_pass = personalization_pass or comparator_pass
    abstentions = int(primary["human_review_decisions"])
    stops = int(primary["stop_decisions"])
    decisions = int(primary["failed_payments_evaluated"])
    gates = {
        "deterministic_safety": {
            "criterion": "zero deterministic policy violations",
            "observed": int(primary["deterministic_policy_violations"]),
            "pass": int(primary["deterministic_policy_violations"]) == 0,
        },
        "fixed_retry_value": {
            "criterion": "mean paired net-value difference versus fixed retry > 0",
            "observed_minor": fixed_net,
            "pass": fixed_net > 0,
        },
        "personalization_value": {
            "criterion": (
                "beat global or failure-reason policy on paired mean net value, or reduce "
                "mean oracle-ERV regret by at least one minor, with zero violations"
            ),
            "comparators": personalization_details,
            "pass": personalization_pass and int(primary["deterministic_policy_violations"]) == 0,
        },
        "abstention_transparency": {
            "criterion": "autonomous, human-review, STOP rates and review reasons reported",
            "autonomous_rate": int(primary["autonomous_decisions"]) / decisions,
            "human_review_rate": abstentions / decisions,
            "stop_rate": stops / decisions,
            "pass": True,
        },
        "reminder_comparison_reported": {
            "criterion": "paired Reminder comparison is reported without gating success",
            "mean_paired_net_value_difference_minor": lifts["generic_reminder_first"][
                "net_recovery_value_minor_difference"
            ]["mean"],
            "pass": True,
        },
    }
    gates["overall"] = {
        "pass": all(
            gates[name]["pass"]
            for name in (
                "deterministic_safety",
                "fixed_retry_value",
                "personalization_value",
                "abstention_transparency",
            )
        )
    }
    return gates


def _abstention_analysis(primary: pd.DataFrame, frame: pd.DataFrame) -> dict[str, Any]:
    review = primary[primary["decision_kind"] == "HUMAN_REVIEW"].copy()
    count = len(review)
    if count == 0:
        return {
            "human_review_count": 0,
            "human_review_rate": 0.0,
            "reason_distribution": {},
            "payment_value_distribution_minor": {},
            "top_model_action_analysis": {},
            "oracle_ambiguous_count": 0,
            "oracle_ambiguous_rate": 0.0,
        }
    reasons: Counter[str] = Counter()
    for payload in review["review_reasons"]:
        reasons.update(str(value) for value in json.loads(str(payload)))
    candidate_rows = frame[frame["decision_key"].isin(review["decision_key"])].copy()
    contact = candidate_rows["action_type"].isin(
        (
            "SEND_NUDGE",
            "CREATE_PAYMENT_LINK",
            "REQUEST_PAYMENT_METHOD_UPDATE",
            "OFFER_ALTERNATE_METHOD",
        )
    )
    retry = candidate_rows["action_type"].isin(("RETRY_NOW", "RETRY_LATER"))
    allowed = (~retry | (candidate_rows["current_retry_count"] < 2)) & (
        ~contact
        | (
            candidate_rows["customer_contact_allowed"]
            & (candidate_rows["current_contact_count"] < 2)
            & ~candidate_rows["quiet_hours"]
        )
    )
    allowed &= ~(
        (candidate_rows["action_type"] == "CREATE_PAYMENT_LINK")
        & candidate_rows["existing_active_payment_link"]
    )
    allowed &= ~(
        (candidate_rows["action_type"] == "OFFER_ALTERNATE_METHOD")
        & ~candidate_rows["alternate_method_available"]
    )
    top_model = (
        candidate_rows[allowed]
        .sort_values(
            ["decision_key", "primary_probability", "candidate_rank"],
            ascending=[True, False, True],
            kind="stable",
        )
        .drop_duplicates("decision_key")[
            [
                "decision_key",
                "candidate_label",
                "oracle_erv_minor",
                "realized_recovery",
            ]
        ]
        .rename(
            columns={
                "candidate_label": "top_model_action",
                "oracle_erv_minor": "top_model_oracle_erv_minor",
                "realized_recovery": "top_model_realized_recovery",
            }
        )
    )
    joined = review.merge(top_model, on="decision_key", how="left", validate="one_to_one")
    joined["top_model_oracle_erv_regret_minor"] = (
        joined["oracle_best_erv_minor"] - joined["top_model_oracle_erv_minor"]
    )
    correct = joined["top_model_action"] == joined["oracle_best_action"]
    normalized_oracle_margin = (
        joined["oracle_best_erv_minor"] - joined["oracle_second_erv_minor"]
    ) / joined["payment_amount_minor"]
    ambiguous = normalized_oracle_margin <= ORACLE_AMBIGUITY_NORMALIZED_MARGIN
    values = [int(value) for value in review["payment_amount_minor"]]
    return {
        "human_review_count": count,
        "human_review_rate": count / len(primary),
        "reason_distribution": dict(reasons),
        "payment_value_distribution_minor": {
            "mean": fmean(values),
            "median": median(values),
            "min": min(values),
            "max": max(values),
            "amount_bucket_counts": {
                str(key): int(value)
                for key, value in review["amount_bucket"].value_counts().items()
            },
        },
        "top_model_action_analysis": {
            "oracle_best_action_agreement_count": int(correct.sum()),
            "oracle_best_action_agreement_rate": float(correct.mean()),
            "mean_oracle_erv_regret_minor_if_executed": float(
                joined["top_model_oracle_erv_regret_minor"].mean()
            ),
            "realized_recovery_count_if_executed": int(joined["top_model_realized_recovery"].sum()),
            "realized_recovery_rate_if_executed": float(
                joined["top_model_realized_recovery"].mean()
            ),
        },
        "oracle_regret_of_no_autonomous_action_minor": {
            "mean": float(review["oracle_erv_regret_minor"].mean()),
            "median": float(review["oracle_erv_regret_minor"].median()),
        },
        "oracle_ambiguous_threshold": ORACLE_AMBIGUITY_NORMALIZED_MARGIN,
        "oracle_ambiguous_count": int(ambiguous.sum()),
        "oracle_ambiguous_rate": float(ambiguous.mean()),
        "interpretation": (
            "human-review outcomes are not simulated; top-model values are an evaluation-only "
            "counterfactual, not attributed recovery"
        ),
    }


def _false_safety_analysis(
    frame: pd.DataFrame,
    block_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not block_rows:
        return {"highest_predicted_erv_block_count": 0, "by_rule": {}}
    highest = (
        frame.sort_values(
            ["decision_key", "primary_erv_minor", "candidate_rank"],
            ascending=[True, False, True],
            kind="stable",
        )
        .drop_duplicates("decision_key")
        .set_index("decision_key")["candidate_label"]
        .to_dict()
    )
    blocked = pd.DataFrame(block_rows)
    blocked = blocked[
        blocked.apply(
            lambda row: highest.get(str(row["decision_key"])) == str(row["candidate_label"]),
            axis=1,
        )
    ]
    by_rule: dict[str, Any] = {}
    for policy_id, subset in blocked.groupby("policy_id", sort=True):
        by_rule[str(policy_id)] = {
            "block_count": len(subset),
            "oracle_erv_minor_forgone": int(subset["oracle_erv_minor"].clip(lower=0).sum()),
            "friction_cost_minor_avoided": int(subset["friction_cost_minor"].sum()),
            "customer_contact_exposures_avoided": int(subset["is_customer_contact"].sum()),
        }
    return {
        "definition": "rule blocks affecting the highest primary-model predicted-ERV candidate",
        "highest_predicted_erv_block_count": len(blocked),
        "by_rule": by_rule,
    }


def _action_dominance(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    adaptive = (
        "model_probability_policy",
        PRIMARY_STRATEGY,
        "recoveriq_no_health_research",
    )
    output: dict[str, Any] = {}
    for name in adaptive:
        distribution = metrics[name]["selected_action_distribution"]
        total = sum(int(value) for value in distribution.values())
        top_action, top_count = max(distribution.items(), key=lambda item: int(item[1]))
        share = int(top_count) / total
        output[name] = {
            "dominant_action": top_action,
            "dominant_share": share,
            "exceeds_80_percent": share > 0.80,
        }
    return output


def _existing_workflow_metrics(workflows: dict[str, Any]) -> dict[str, Any]:
    if not workflows:
        return {
            "semantics": "existing Phase 2 multi-action workflows; not headline-equivalent",
            "strategy_metrics": {},
        }
    names = ("fixed_retry", "reminder_then_retry")
    output: dict[str, Any] = {}
    for name in names:
        metrics = [payload[name]["metrics"] for payload in workflows.values()]
        failed = sum(int(item["failed_payment_count"]) for item in metrics)
        recovered = sum(int(item["recovered_payment_count"]) for item in metrics)
        action_counts: Counter[str] = Counter()
        for item in metrics:
            action_counts.update(
                {str(key): int(value) for key, value in item["action_counts"].items()}
            )
        output[name] = {
            "failed_payments_evaluated": failed,
            "recovered_payments": recovered,
            "recovery_rate": recovered / failed,
            "simulated_gross_recovered_minor": sum(
                int(item["gross_recovered_amount_minor"]) for item in metrics
            ),
            "simulated_net_recovery_value_minor": sum(
                int(item["net_recovered_value_minor"]) for item in metrics
            ),
            "retry_count": sum(int(item["retry_count"]) for item in metrics),
            "customer_contacts": sum(int(item["customer_contact_count"]) for item in metrics),
            "payment_links": sum(int(item["payment_link_count"]) for item in metrics),
            "human_reviews": sum(int(item["human_review_count"]) for item in metrics),
            "intervention_cost_minor": sum(
                int(item["intervention_cost_minor"]) for item in metrics
            ),
            "friction_cost_minor": sum(int(item["friction_cost_minor"]) for item in metrics),
            "average_actions_per_failure": sum(
                int(item["retry_count"])
                + int(item["nudge_count"])
                + int(item["payment_link_count"])
                + int(item["human_review_count"])
                for item in metrics
            )
            / failed,
            "selected_action_distribution": dict(action_counts),
        }
    return {
        "semantics": (
            "existing Phase 2 multi-action workflows under original semantics; secondary only"
        ),
        "strategy_metrics": output,
        "per_seed_metrics": {
            seed: {name: payload[name]["metrics"] for name in names}
            for seed, payload in workflows.items()
        },
    }


def render_validation_report(report: dict[str, Any]) -> str:
    first = report["first_intervention_view"]
    metrics = first["strategy_metrics"]
    primary = metrics[PRIMARY_STRATEGY]
    gates = report["validation_gates"]
    lines = [
        "# RecoverIQ Policy V1 Validation",
        "",
        f"Policy config hash: `{report['policy_config_hash']}`",
        f"Registered seeds: `{report['validation_seeds'][0]}`-`{report['validation_seeds'][-1]}`",
        f"Overall frozen validation gate: **{'PASS' if gates['overall']['pass'] else 'FAIL'}**",
        "",
        "## RecoverIQ first-intervention result",
        "",
        f"- Decisions: {primary['failed_payments_evaluated']}",
        f"- Recovered: {primary['recovered_payments']} ({primary['recovery_rate']:.6f})",
        f"- Simulated gross recovered minor: {primary['simulated_gross_recovered_minor']}",
        f"- Simulated net recovery value minor: {primary['simulated_net_recovery_value_minor']}",
        f"- Human review: {primary['human_review_decisions']}",
        f"- STOP: {primary['stop_decisions']}",
        f"- Deterministic policy violations: {primary['deterministic_policy_violations']}",
        f"- Mean oracle ERV regret minor: {primary['oracle_erv_regret_minor']['mean']:.3f}",
        "",
        "## Frozen gates",
        "",
    ]
    for name in (
        "deterministic_safety",
        "fixed_retry_value",
        "personalization_value",
        "abstention_transparency",
    ):
        lines.append(f"- {name}: {'PASS' if gates[name]['pass'] else 'FAIL'}")
    lines.extend(("", "## Strategy summary", ""))
    for name in STRATEGIES:
        item = metrics[name]
        lines.append(
            f"- `{name}`: recovered={item['recovered_payments']}, "
            f"rate={item['recovery_rate']:.6f}, net_minor="
            f"{item['simulated_net_recovery_value_minor']}, reviews="
            f"{item['human_review_decisions']}, STOP={item['stop_decisions']}"
        )
    lines.extend(
        (
            "",
            "All values are synthetic simulator evidence. Existing Phase 2 multi-action workflows "
            "are retained only in the separate secondary view.",
        )
    )
    return "\n".join(lines)
