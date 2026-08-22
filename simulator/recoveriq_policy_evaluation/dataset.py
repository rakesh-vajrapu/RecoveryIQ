from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from recoveriq_policy.candidates import generate_candidate_actions
from recoveriq_policy.config import CANDIDATE_INDEX, CANDIDATE_LABELS, PRIMARY_COST_REGIME
from recoveriq_policy.economics import economic_score, expected_recovered_minor
from recoveriq_policy.scoring import FrozenRecoveryModelScorer
from recoveriq_policy_evaluation.contexts import generate_observable_policy_cases
from recoveriq_policy_evaluation.oracle import ScenarioOracle
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.environment import RecoveryEnvironment
from recoveriq_simulator.policies import FixedRetryPolicy, ReminderThenRetryPolicy
from recoveriq_simulator.scenario import ScenarioGenerator


def generate_candidate_evaluation_frame(
    *,
    seeds: tuple[int, ...],
    model_root: Path,
    calibration_root: Path,
    frozen_detector_path: Path,
    include_existing_workflows: bool,
) -> tuple[pd.DataFrame, dict[str, int], dict[str, Any], float]:
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
    workflows: dict[str, Any] = {}
    for seed in seeds:
        config = SimulatorConfig(seed=seed, cost_regime=PRIMARY_COST_REGIME)
        scenario = ScenarioGenerator(config).generate()
        if include_existing_workflows:
            environment = RecoveryEnvironment(scenario, config)
            workflows[str(seed)] = {
                "fixed_retry": environment.evaluate(FixedRetryPolicy()).model_dump(mode="json"),
                "reminder_then_retry": environment.evaluate(ReminderThenRetryPolicy()).model_dump(
                    mode="json"
                ),
            }
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
                economics = economic_score(prediction, case.observation.amount_minor)
                no_health_economics = economic_score(
                    no_health_prediction,
                    case.observation.amount_minor,
                )
                oracle_expected = expected_recovered_minor(
                    Decimal(str(probability)),
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
                        "failure_to_decision_hours": (
                            case.context.base_features.failure_to_decision_hours
                        ),
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
                        "action_id": action.action_id,
                        "action_type": action.action_type.value,
                        "delay_hours": action.scheduled_delay_hours,
                        "intervention_cost_minor": action.intervention_cost_minor,
                        "friction_cost_minor": action.friction_cost_minor,
                        "primary_raw_probability": float(prediction.raw_probability),
                        "primary_probability": float(prediction.calibrated_probability),
                        "primary_erv_minor": economics.erv_minor,
                        "no_health_raw_probability": float(no_health_prediction.raw_probability),
                        "no_health_probability": float(no_health_prediction.calibrated_probability),
                        "no_health_erv_minor": no_health_economics.erv_minor,
                        "oracle_probability": probability,
                        "oracle_erv_minor": oracle_expected
                        - action.intervention_cost_minor
                        - action.friction_cost_minor,
                        "realized_recovery": realized,
                        "action_training_count": prediction.support.action_training_count,
                        "primary_calibration_bin": prediction.support.calibration_bin,
                        "primary_calibration_bin_count": (prediction.support.calibration_bin_count),
                        "primary_low_support": prediction.support.low_support,
                        "primary_support_reasons": json.dumps(prediction.support.reasons),
                        "no_health_calibration_bin": (no_health_prediction.support.calibration_bin),
                        "no_health_calibration_bin_count": (
                            no_health_prediction.support.calibration_bin_count
                        ),
                        "no_health_low_support": no_health_prediction.support.low_support,
                        "no_health_support_reasons": json.dumps(
                            no_health_prediction.support.reasons
                        ),
                    }
                )
    return pd.DataFrame(rows), seed_counts, workflows, perf_counter() - started
