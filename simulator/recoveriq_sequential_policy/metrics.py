from __future__ import annotations

import math
from statistics import fmean, median
from typing import Any, cast

import pandas as pd


def strategy_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    episodes = len(frame)
    recovered = int(frame["recovered"].sum())
    actions = frame["action_count"].astype(float).tolist()
    recovery_hours = frame.loc[frame["recovered"], "recovery_time_hours"].dropna().tolist()
    gross = int(frame["gross_recovered_minor"].sum())
    net = int(frame["net_recovery_value_minor"].sum())
    interventions = int(frame["action_count"].sum())
    contacts = int(frame["contact_count"].sum())
    retries = int(frame["retry_count"].sum())
    return {
        "episodes": episodes,
        "recovered_episodes": recovered,
        "recovery_rate": recovered / episodes if episodes else None,
        "simulated_gross_recovered_amount_minor": gross,
        "simulated_net_recovery_value_minor": net,
        "intervention_cost_minor": int(frame["intervention_cost_minor"].sum()),
        "friction_cost_minor": int(frame["friction_cost_minor"].sum()),
        "retry_count": retries,
        "customer_contacts": contacts,
        "payment_links": int(frame["payment_link_count"].sum()),
        "method_updates": int(frame["method_update_count"].sum()),
        "alternate_methods": int(frame["alternate_method_count"].sum()),
        "human_reviews": int(frame["human_review"].sum()),
        "stop_outcomes": int(frame["stop_outcome"].sum()),
        "mean_actions_per_episode": fmean(actions) if actions else None,
        "median_actions_per_episode": median(actions) if actions else None,
        "p90_actions_per_episode": _percentile(actions, 0.9),
        "mean_recovery_time_hours": fmean(recovery_hours) if recovery_hours else None,
        "median_recovery_time_hours": median(recovery_hours) if recovery_hours else None,
        "policy_violations": int(frame["policy_violations"].sum()),
        "autonomous_decision_coverage": _safe_ratio(
            interventions,
            interventions + int(frame["human_review"].sum()),
        ),
        "friction_efficiency": {
            "net_value_per_intervention_minor": _safe_ratio(net, interventions),
            "net_value_per_customer_contact_minor": _safe_ratio(net, contacts),
            "recoveries_per_retry": _safe_ratio(recovered, retries),
            "recoveries_per_contact": _safe_ratio(recovered, contacts),
            "contacts_per_recovered_payment": _safe_ratio(contacts, recovered),
            "interventions_per_recovered_payment": _safe_ratio(interventions, recovered),
        },
    }


def paired_lift(
    records: pd.DataFrame,
    primary: str,
    comparator: str,
) -> dict[str, Any]:
    columns = {
        "recovery_rate_difference": "recovery_rate",
        "recovered_payment_difference": "recovered",
        "gross_value_difference_minor": "gross_recovered_minor",
        "net_value_difference_minor": "net_recovery_value_minor",
        "retry_difference": "retry_count",
        "contact_difference": "contact_count",
    }
    primary_seed = _seed_aggregates(records[records["strategy"] == primary])
    comparator_seed = _seed_aggregates(records[records["strategy"] == comparator])
    per_seed: list[dict[str, Any]] = []
    values: dict[str, list[float]] = {name: [] for name in columns}
    for seed in sorted(set(primary_seed) & set(comparator_seed)):
        row: dict[str, Any] = {"seed": seed}
        for output_name, metric_name in columns.items():
            difference = primary_seed[seed][metric_name] - comparator_seed[seed][metric_name]
            row[output_name] = difference
            values[output_name].append(float(difference))
        per_seed.append(row)
    return {
        "primary": primary,
        "comparator": comparator,
        "per_seed": per_seed,
        "aggregate": {name: _interval(rows) for name, rows in values.items()},
    }


def _seed_aggregates(frame: pd.DataFrame) -> dict[int, dict[str, float]]:
    results: dict[int, dict[str, float]] = {}
    for seed, group in frame.groupby("seed", sort=True):
        results[cast(int, seed)] = {
            "recovery_rate": float(group["recovered"].mean()),
            "recovered": float(group["recovered"].sum()),
            "gross_recovered_minor": float(group["gross_recovered_minor"].sum()),
            "net_recovery_value_minor": float(group["net_recovery_value_minor"].sum()),
            "retry_count": float(group["retry_count"].sum()),
            "contact_count": float(group["contact_count"].sum()),
        }
    return results


def _interval(values: list[float]) -> dict[str, float | int | str | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "ci95_low": None, "ci95_high": None}
    mean_value = fmean(values)
    if len(values) < 2:
        return {
            "count": len(values),
            "mean": mean_value,
            "median": median(values),
            "ci95_low": None,
            "ci95_high": None,
        }
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    standard_error = math.sqrt(variance / len(values))
    critical = 2.262 if len(values) == 10 else 1.96
    return {
        "count": len(values),
        "mean": mean_value,
        "median": median(values),
        "ci95_low": mean_value - critical * standard_error,
        "ci95_high": mean_value + critical * standard_error,
        "method": "paired_seed_t_interval",
    }


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)]


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator / denominator) if denominator else None
