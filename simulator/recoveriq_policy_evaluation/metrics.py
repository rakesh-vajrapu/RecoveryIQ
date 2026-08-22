from __future__ import annotations

import math
from statistics import fmean, median, stdev
from typing import Any

import pandas as pd

from recoveriq_policy_evaluation.strategy import action_distribution


def strategy_metrics(records: pd.DataFrame) -> dict[str, Any]:
    evaluated = len(records)
    recovered = int(records["recovered"].sum())
    recovery_times = [float(value) for value in records["recovery_time_hours"].dropna().tolist()]
    regrets = [float(value) for value in records["oracle_erv_regret_minor"]]
    probability_regrets = [float(value) for value in records["oracle_probability_regret"]]
    return {
        "failed_payments_evaluated": evaluated,
        "autonomous_decisions": int(records["autonomous_decisions"].sum()),
        "human_review_decisions": int(records["human_reviews"].sum()),
        "stop_decisions": int(records["stop_count"].sum()),
        "recovered_payments": recovered,
        "recovery_rate": recovered / evaluated if evaluated else None,
        "simulated_gross_recovered_minor": int(records["gross_recovered_minor"].sum()),
        "simulated_net_recovery_value_minor": int(records["net_recovery_value_minor"].sum()),
        "retry_count": int(records["retry_count"].sum()),
        "customer_contacts": int(records["customer_contacts"].sum()),
        "payment_links": int(records["payment_links"].sum()),
        "method_update_actions": int(records["method_updates"].sum()),
        "alternate_method_actions": int(records["alternate_methods"].sum()),
        "intervention_cost_minor": int(records["intervention_cost_minor"].sum()),
        "friction_cost_minor": int(records["friction_cost_minor"].sum()),
        "average_actions_per_failure": float(records["action_count"].mean()),
        "mean_recovery_time_hours": fmean(recovery_times) if recovery_times else None,
        "median_recovery_time_hours": median(recovery_times) if recovery_times else None,
        "deterministic_policy_violations": int(records["policy_violations"].sum()),
        "top_1_oracle_agreement": float(records["top_1_oracle_agreement"].mean()),
        "top_2_oracle_coverage": float(records["top_2_oracle_coverage"].mean()),
        "oracle_erv_regret_minor": {
            "mean": fmean(regrets),
            "median": median(regrets),
            "p90": sorted(regrets)[round((len(regrets) - 1) * 0.9)],
        },
        "oracle_probability_regret": {
            "mean": fmean(probability_regrets),
            "median": median(probability_regrets),
            "p90": sorted(probability_regrets)[round((len(probability_regrets) - 1) * 0.9)],
        },
        "selected_action_distribution": action_distribution(records),
    }


def strategy_metrics_by_seed(records: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {
        str(seed): strategy_metrics(subset) for seed, subset in records.groupby("seed", sort=True)
    }


def paired_lift(
    records: pd.DataFrame,
    primary: str,
    comparator: str,
) -> dict[str, Any]:
    fields = {
        "recovered_payment_difference": "recovered_payments",
        "recovery_rate_difference": "recovery_rate",
        "gross_recovered_minor_difference": "simulated_gross_recovered_minor",
        "net_recovery_value_minor_difference": "simulated_net_recovery_value_minor",
        "retry_difference": "retry_count",
        "contact_difference": "customer_contacts",
        "human_review_difference": "human_review_decisions",
        "oracle_erv_regret_minor_difference": "oracle_regret_mean",
    }
    primary_seed = _paired_seed_values(records[records["strategy"] == primary])
    comparator_seed = _paired_seed_values(records[records["strategy"] == comparator])
    result: dict[str, Any] = {}
    for output_name, field in fields.items():
        differences = [
            float(primary_seed[seed][field]) - float(comparator_seed[seed][field])
            for seed in sorted(primary_seed)
        ]
        result[output_name] = _distribution(differences)
    return result


def diagnostic_slices(records: pd.DataFrame, column: str) -> dict[str, dict[str, Any]]:
    return {
        str(value): strategy_metrics(subset) for value, subset in records.groupby(column, sort=True)
    }


def _paired_seed_values(records: pd.DataFrame) -> dict[int, dict[str, float]]:
    output: dict[int, dict[str, float]] = {}
    for seed, subset in records.groupby("seed", sort=True):
        count = len(subset)
        output[int(str(seed))] = {
            "recovered_payments": float(subset["recovered"].sum()),
            "recovery_rate": float(subset["recovered"].mean()),
            "simulated_gross_recovered_minor": float(subset["gross_recovered_minor"].sum()),
            "simulated_net_recovery_value_minor": float(subset["net_recovery_value_minor"].sum()),
            "retry_count": float(subset["retry_count"].sum()),
            "customer_contacts": float(subset["customer_contacts"].sum()),
            "human_review_decisions": float(subset["human_reviews"].sum()),
            "oracle_regret_mean": float(subset["oracle_erv_regret_minor"].sum()) / count,
        }
    return output


def _distribution(values: list[float]) -> dict[str, Any]:
    mean = fmean(values)
    standard_deviation = stdev(values) if len(values) > 1 else 0.0
    half_width = 1.96 * standard_deviation / math.sqrt(len(values)) if values else 0.0
    return {
        "values_by_seed": values,
        "mean": mean,
        "median": median(values),
        "standard_deviation": standard_deviation,
        "ci95": [mean - half_width, mean + half_width],
    }
