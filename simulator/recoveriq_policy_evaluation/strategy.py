from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from recoveriq_policy.config import CANDIDATE_INDEX, CANDIDATE_LABELS
from recoveriq_policy.engine import RecoverIQPolicyEngine
from recoveriq_policy.models import (
    CandidateAction,
    CandidatePrediction,
    DecisionKind,
    DecisionPolicyFacts,
    FrozenBaselineArtifact,
    PolicyOperationalProfile,
    RecoveryDecision,
    RuleResult,
    SupportDiagnostic,
)
from recoveriq_policy.rules import hard_feasibility_checks
from recoveriq_simulator.config import costs_for_regime
from recoveriq_simulator.enums import ActionType, CostRegime
from recoveriq_simulator.observation import RecoveryAction

STRATEGIES = (
    "fixed_retry_first",
    "generic_reminder_first",
    "best_global_action",
    "failure_reason_rule",
    "failure_reason_method_rule",
    "model_probability_policy",
    "recoveriq_erv_policy_v1",
    "recoveriq_no_health_research",
    "oracle_erv_upper_bound",
)
CONTACT_TYPES = {
    ActionType.SEND_NUDGE.value,
    ActionType.CREATE_PAYMENT_LINK.value,
    ActionType.REQUEST_PAYMENT_METHOD_UPDATE.value,
    ActionType.OFFER_ALTERNATE_METHOD.value,
}


def execute_strategies(
    frame: pd.DataFrame,
    *,
    baselines: FrozenBaselineArtifact,
    policy_config_hash: str,
    normalized_margin_threshold: Decimal,
    strategy_names: tuple[str, ...] = STRATEGIES,
    capture_trace: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any] | None, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    example_trace: dict[str, Any] | None = None
    block_rows: list[dict[str, Any]] = []
    primary_engine = RecoverIQPolicyEngine(
        policy_config_hash=policy_config_hash,
        normalized_margin_threshold=normalized_margin_threshold,
    )
    no_health_engine = RecoverIQPolicyEngine(
        policy_config_hash=policy_config_hash,
        normalized_margin_threshold=normalized_margin_threshold,
    )
    for _, subset in frame.groupby("decision_key", sort=False):
        subset = subset.sort_values("candidate_rank", kind="stable")
        facts = _facts(subset.iloc[0])
        primary = _predictions(subset, "primary")
        no_health = _predictions(subset, "no_health")
        primary_by_label = {item.candidate.label: item for item in primary}
        hard_allowed = {
            label: not any(
                check.result is RuleResult.BLOCK
                for check in hard_feasibility_checks(prediction, facts)
            )
            for label, prediction in primary_by_label.items()
        }
        oracle_order = tuple(
            str(value)
            for value in subset[subset["candidate_label"].map(hard_allowed)].sort_values(
                ["oracle_erv_minor", "candidate_rank"],
                ascending=[False, True],
                kind="stable",
            )["candidate_label"]
        )
        if not oracle_order:
            oracle_order = CANDIDATE_LABELS
        oracle_probability_order = tuple(
            str(value)
            for value in subset[subset["candidate_label"].map(hard_allowed)].sort_values(
                ["oracle_probability", "candidate_rank"],
                ascending=[False, True],
                kind="stable",
            )["candidate_label"]
        )
        if not oracle_probability_order:
            oracle_probability_order = CANDIDATE_LABELS
        for strategy in strategy_names:
            decision: RecoveryDecision | None = None
            kind: DecisionKind
            selected_label: str | None
            reason: str
            if strategy == "fixed_retry_first":
                kind, selected_label, reason = _named_action("RETRY_LATER_6H", hard_allowed)
            elif strategy == "generic_reminder_first":
                kind, selected_label, reason = _named_action("SEND_NUDGE", hard_allowed)
            elif strategy == "best_global_action":
                kind, selected_label, reason = _fallback_action(
                    baselines.global_action_order,
                    hard_allowed,
                )
            elif strategy == "failure_reason_rule":
                reason_key = str(subset.iloc[0]["failure_reason"])
                intended = baselines.failure_reason_mapping.get(
                    reason_key,
                    baselines.global_best_action,
                )
                kind, selected_label, reason = _mapped_action(
                    intended,
                    baselines.global_action_order,
                    hard_allowed,
                )
            elif strategy == "failure_reason_method_rule":
                lookup = f"{subset.iloc[0]['failure_reason']}|{subset.iloc[0]['payment_method']}"
                intended = baselines.failure_reason_method_mapping.get(
                    lookup,
                    baselines.global_best_action,
                )
                kind, selected_label, reason = _mapped_action(
                    intended,
                    baselines.global_action_order,
                    hard_allowed,
                )
            elif strategy == "model_probability_policy":
                kind, selected_label, reason = _probability_action(primary, hard_allowed)
            elif strategy == "recoveriq_erv_policy_v1":
                decision = primary_engine.decide(facts, primary)
                kind = decision.decision_kind
                selected_label = (
                    decision.selected_candidate.prediction.candidate.label
                    if decision.selected_candidate
                    else None
                )
                reason = decision.reason
                if capture_trace and example_trace is None and kind is DecisionKind.ACTION:
                    example_trace = _trace(subset.iloc[0], facts, decision)
                block_rows.extend(_blocked_rows(subset, decision))
            elif strategy == "recoveriq_no_health_research":
                decision = no_health_engine.decide(facts, no_health)
                kind = decision.decision_kind
                selected_label = (
                    decision.selected_candidate.prediction.candidate.label
                    if decision.selected_candidate
                    else None
                )
                reason = decision.reason
            elif strategy == "oracle_erv_upper_bound":
                selected_label = oracle_order[0]
                selected_row = subset[subset["candidate_label"] == selected_label].iloc[0]
                if int(selected_row["oracle_erv_minor"]) <= 0:
                    kind, selected_label, reason = (
                        DecisionKind.STOP,
                        None,
                        "oracle upper bound has no positive feasible ERV",
                    )
                else:
                    kind, reason = DecisionKind.ACTION, "evaluation-only maximum oracle ERV"
            else:
                raise ValueError(f"unknown strategy: {strategy}")
            records.append(
                _decision_record(
                    subset,
                    strategy=strategy,
                    kind=kind,
                    selected_label=selected_label,
                    reason=reason,
                    decision=decision,
                    oracle_order=oracle_order,
                    oracle_probability_order=oracle_probability_order,
                )
            )
    return pd.DataFrame(records), example_trace, block_rows


def _facts(row: pd.Series) -> DecisionPolicyFacts:
    decision_at = row["decision_at"]
    if isinstance(decision_at, pd.Timestamp):
        decision_at = decision_at.to_pydatetime()
    if not isinstance(decision_at, datetime):
        raise TypeError("decision timestamp is invalid")
    return DecisionPolicyFacts(
        decision_key=str(row["decision_key"]),
        decision_at=decision_at,
        payment_amount_minor=int(row["payment_amount_minor"]),
        failure_to_decision_hours=float(row.get("failure_to_decision_hours", 0.0)),
        current_retry_count=int(row["current_retry_count"]),
        current_contact_count=int(row["current_contact_count"]),
        operational=PolicyOperationalProfile(
            customer_contact_allowed=bool(row["customer_contact_allowed"]),
            existing_active_payment_link=bool(row["existing_active_payment_link"]),
            alternate_method_available=bool(row["alternate_method_available"]),
            quiet_hours=bool(row["quiet_hours"]),
        ),
    )


def _predictions(
    subset: pd.DataFrame,
    model_prefix: str,
) -> tuple[CandidatePrediction, ...]:
    predictions: list[CandidatePrediction] = []
    for _, row in subset.iterrows():
        decision_at = row["decision_at"]
        if isinstance(decision_at, pd.Timestamp):
            decision_at = decision_at.to_pydatetime()
        if not isinstance(decision_at, datetime):
            raise TypeError("decision timestamp is invalid")
        label = str(row["candidate_label"])
        action = RecoveryAction(
            action_id=str(row.get("action_id", f"rehydrated-{row['decision_key']}-{label}")),
            action_type=ActionType(str(row["action_type"])),
            execute_at=decision_at + pd.Timedelta(hours=float(row["delay_hours"])).to_pytimedelta(),
            scheduled_delay_hours=float(row["delay_hours"]),
            attempt_number=(
                int(row["current_retry_count"]) + 1
                if str(row["action_type"]).startswith("RETRY")
                else 0
            ),
            intervention_cost_minor=int(row["intervention_cost_minor"]),
            friction_cost_minor=int(row["friction_cost_minor"]),
        )
        support_prefix = "primary" if model_prefix == "primary" else "no_health"
        bin_count_key = f"{support_prefix}_calibration_bin_count"
        bin_key = f"{support_prefix}_calibration_bin"
        low_key = f"{support_prefix}_low_support"
        reasons_key = f"{support_prefix}_support_reasons"
        if bin_count_key not in row:
            bin_count_key = "calibration_bin_count"
            bin_key = "calibration_bin"
            low_key = "low_support"
            reasons_key = "support_reasons"
        probability_key = f"{model_prefix}_probability"
        raw_key = f"{model_prefix}_raw_probability"
        probability = float(row[probability_key])
        reasons = tuple(json.loads(str(row.get(reasons_key, "[]"))))
        predictions.append(
            CandidatePrediction(
                candidate=CandidateAction(
                    label=label,
                    recovery_action=action,
                    is_customer_contact=str(row["action_type"]) in CONTACT_TYPES,
                    requests_method_change=str(row["action_type"])
                    in {
                        ActionType.REQUEST_PAYMENT_METHOD_UPDATE.value,
                        ActionType.OFFER_ALTERNATE_METHOD.value,
                    },
                ),
                raw_probability=Decimal(str(float(row.get(raw_key, probability)))),
                calibrated_probability=Decimal(str(probability)),
                support=SupportDiagnostic(
                    action_training_count=int(row["action_training_count"]),
                    calibration_bin=int(row.get(bin_key, min(int(probability * 10), 9))),
                    calibration_bin_count=int(row.get(bin_count_key, 1_000)),
                    unknown_categories=(),
                    low_support=bool(row.get(low_key, False)),
                    reasons=reasons,
                ),
                model_name=("lightgbm" if model_prefix == "primary" else "lightgbm_without_health"),
            )
        )
    return tuple(predictions)


def _named_action(
    label: str,
    hard_allowed: dict[str, bool],
) -> tuple[DecisionKind, str | None, str]:
    if hard_allowed[label]:
        return DecisionKind.ACTION, label, "fixed first-intervention baseline"
    return DecisionKind.STOP, None, f"baseline action {label} is infeasible"


def _fallback_action(
    order: tuple[str, ...],
    hard_allowed: dict[str, bool],
) -> tuple[DecisionKind, str | None, str]:
    selected = next((label for label in order if hard_allowed[label]), None)
    if selected is None:
        return DecisionKind.STOP, None, "no baseline action is feasible"
    return DecisionKind.ACTION, selected, "development-frozen global action order"


def _mapped_action(
    intended: str,
    order: tuple[str, ...],
    hard_allowed: dict[str, bool],
) -> tuple[DecisionKind, str | None, str]:
    if hard_allowed[intended]:
        return DecisionKind.ACTION, intended, "development-frozen observable lookup"
    kind, fallback, _ = _fallback_action(order, hard_allowed)
    return kind, fallback, f"mapped action {intended} infeasible; used frozen global fallback"


def _probability_action(
    predictions: tuple[CandidatePrediction, ...],
    hard_allowed: dict[str, bool],
) -> tuple[DecisionKind, str | None, str]:
    ordered = sorted(
        (item for item in predictions if hard_allowed[item.candidate.label]),
        key=lambda item: (
            -item.calibrated_probability,
            CANDIDATE_INDEX[item.candidate.label],
        ),
    )
    if not ordered:
        return DecisionKind.STOP, None, "no feasible probability-scored action"
    if ordered[0].support.low_support:
        return DecisionKind.HUMAN_REVIEW, None, "top-probability candidate has low support"
    return DecisionKind.ACTION, ordered[0].candidate.label, "maximum calibrated probability"


def _decision_record(
    subset: pd.DataFrame,
    *,
    strategy: str,
    kind: DecisionKind,
    selected_label: str | None,
    reason: str,
    decision: RecoveryDecision | None,
    oracle_order: tuple[str, ...],
    oracle_probability_order: tuple[str, ...],
) -> dict[str, Any]:
    first = subset.iloc[0]
    selected = (
        subset[subset["candidate_label"] == selected_label].iloc[0]
        if selected_label is not None
        else None
    )
    costs = costs_for_regime(CostRegime.BALANCED)
    recovered = bool(selected["realized_recovery"]) if selected is not None else False
    gross = int(first["payment_amount_minor"]) if recovered else 0
    intervention = (
        int(selected["intervention_cost_minor"])
        if selected is not None
        else costs.human_review_minor
        if kind is DecisionKind.HUMAN_REVIEW
        else 0
    )
    friction = int(selected["friction_cost_minor"]) if selected is not None else 0
    selected_oracle_erv = int(selected["oracle_erv_minor"]) if selected is not None else 0
    oracle_best_row = subset[subset["candidate_label"] == oracle_order[0]].iloc[0]
    oracle_second_label = oracle_order[1] if len(oracle_order) > 1 else oracle_order[0]
    oracle_second_row = subset[subset["candidate_label"] == oracle_second_label].iloc[0]
    oracle_best_erv = max(0, int(oracle_best_row["oracle_erv_minor"]))
    oracle_second_erv = max(0, int(oracle_second_row["oracle_erv_minor"]))
    oracle_regret = oracle_best_erv - selected_oracle_erv
    oracle_probability_best_row = subset[
        subset["candidate_label"] == oracle_probability_order[0]
    ].iloc[0]
    selected_oracle_probability = (
        float(selected["oracle_probability"]) if selected is not None else 0.0
    )
    selected_type = str(selected["action_type"]) if selected is not None else None
    violation_count = 0
    if selected_label is not None and decision is not None:
        chosen = next(
            item
            for item in decision.candidates
            if item.prediction.candidate.label == selected_label
        )
        violation_count = int(chosen.final_policy_result is not RuleResult.PASS)
    review_reasons = (
        [
            check.policy_id
            for check in (decision.decision_rules if decision else ())
            if check.result is RuleResult.REVIEW
        ]
        if kind is DecisionKind.HUMAN_REVIEW
        else []
    )
    if kind is DecisionKind.HUMAN_REVIEW and not review_reasons:
        review_reasons = ["LOW_SUPPORT"]
    return {
        "seed": int(first["seed"]),
        "decision_key": str(first["decision_key"]),
        "strategy": strategy,
        "decision_kind": kind.value,
        "selected_action": (
            selected_label
            if selected_label is not None
            else "HUMAN_REVIEW"
            if kind is DecisionKind.HUMAN_REVIEW
            else "STOP"
        ),
        "reason": reason,
        "review_reasons": json.dumps(review_reasons),
        "recovered": recovered,
        "gross_recovered_minor": gross,
        "net_recovery_value_minor": gross - intervention - friction,
        "intervention_cost_minor": intervention,
        "friction_cost_minor": friction,
        "retry_count": int(selected_type in {"RETRY_NOW", "RETRY_LATER"}),
        "customer_contacts": int(selected_type in CONTACT_TYPES),
        "payment_links": int(selected_type == "CREATE_PAYMENT_LINK"),
        "method_updates": int(selected_type == "REQUEST_PAYMENT_METHOD_UPDATE"),
        "alternate_methods": int(selected_type == "OFFER_ALTERNATE_METHOD"),
        "human_reviews": int(kind is DecisionKind.HUMAN_REVIEW),
        "stop_count": int(kind is DecisionKind.STOP),
        "autonomous_decisions": int(kind is DecisionKind.ACTION),
        "action_count": int(kind is DecisionKind.ACTION),
        "recovery_time_hours": (
            float(selected["delay_hours"]) if recovered and selected is not None else None
        ),
        "policy_violations": violation_count,
        "absolute_erv_margin_minor": (
            decision.absolute_erv_margin_minor if decision is not None else None
        ),
        "normalized_erv_margin": (
            float(decision.normalized_erv_margin)
            if decision is not None and decision.normalized_erv_margin is not None
            else None
        ),
        "oracle_best_action": oracle_order[0],
        "oracle_second_action": oracle_order[1] if len(oracle_order) > 1 else oracle_order[0],
        "oracle_best_erv_minor": oracle_best_erv,
        "oracle_second_erv_minor": oracle_second_erv,
        "selected_oracle_erv_minor": selected_oracle_erv,
        "oracle_erv_regret_minor": oracle_regret,
        "oracle_best_probability": float(oracle_probability_best_row["oracle_probability"]),
        "selected_oracle_probability": selected_oracle_probability,
        "oracle_probability_regret": (
            float(oracle_probability_best_row["oracle_probability"]) - selected_oracle_probability
        ),
        "top_1_oracle_agreement": int(selected_label == oracle_order[0]),
        "top_2_oracle_coverage": int(selected_label in oracle_order[:2]),
        "payment_amount_minor": int(first["payment_amount_minor"]),
        "amount_bucket": str(first["amount_bucket"]),
        "failure_reason": str(first["failure_reason"]),
        "payment_method": str(first["payment_method"]),
        "hidden_failure_family": str(first["hidden_failure_family"]),
        "during_hidden_incident": bool(first["during_hidden_incident"]),
    }


def _trace(
    row: pd.Series,
    facts: DecisionPolicyFacts,
    decision: RecoveryDecision,
) -> dict[str, Any]:
    return {
        "artifact_type": "structured_policy_decision_trace",
        "policy_authority": "DETERMINISTIC_RULES_ONLY",
        "observable_context": {
            "decision_key": facts.decision_key,
            "decision_at": facts.decision_at,
            "payment_amount_minor": facts.payment_amount_minor,
            "failure_reason": str(row["failure_reason"]),
            "payment_method": str(row["payment_method"]),
            "current_retry_count": facts.current_retry_count,
            "current_contact_count": facts.current_contact_count,
            "operational": facts.operational.model_dump(mode="json"),
        },
        "decision": decision.model_dump(mode="json"),
        "outcome": None,
    }


def _blocked_rows(subset: pd.DataFrame, decision: RecoveryDecision) -> list[dict[str, Any]]:
    by_label = {str(row["candidate_label"]): row for _, row in subset.iterrows()}
    rows: list[dict[str, Any]] = []
    for candidate in decision.candidates:
        label = candidate.prediction.candidate.label
        truth = by_label[label]
        for check in candidate.policy_checks:
            if check.result is RuleResult.BLOCK:
                rows.append(
                    {
                        "decision_key": decision.decision_key,
                        "policy_id": check.policy_id,
                        "candidate_label": label,
                        "oracle_erv_minor": int(truth["oracle_erv_minor"]),
                        "predicted_erv_minor": candidate.economic.erv_minor,
                        "friction_cost_minor": int(truth["friction_cost_minor"]),
                        "is_customer_contact": candidate.prediction.candidate.is_customer_contact,
                    }
                )
    return rows


def action_distribution(records: pd.DataFrame) -> dict[str, int]:
    return {str(label): int(count) for label, count in Counter(records["selected_action"]).items()}
