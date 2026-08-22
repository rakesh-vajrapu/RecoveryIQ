from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)


def binary_probability_metrics(
    targets: Iterable[int | bool],
    probabilities: Iterable[float],
    *,
    bins: int = 10,
) -> dict[str, Any]:
    y = np.asarray(list(targets), dtype=int)
    probability = np.clip(np.asarray(list(probabilities), dtype=float), 1e-9, 1 - 1e-9)
    reliability = reliability_bins(y, probability, bins=bins)
    return {
        "sample_count": len(y),
        "positive_count": int(y.sum()),
        "positive_rate": float(y.mean()) if len(y) else None,
        "brier_score": float(brier_score_loss(y, probability)) if len(y) else None,
        "log_loss": float(log_loss(y, probability, labels=[0, 1])) if len(y) else None,
        "expected_calibration_error": _ece(reliability, len(y)),
        "roc_auc": (float(roc_auc_score(y, probability)) if len(np.unique(y)) == 2 else None),
        "pr_auc": (
            float(average_precision_score(y, probability)) if len(np.unique(y)) == 2 else None
        ),
        "reliability_bins": reliability,
    }


def per_action_metrics(
    targets: Iterable[int | bool],
    probabilities: Iterable[float],
    actions: Iterable[str],
) -> dict[str, dict[str, Any]]:
    grouped: defaultdict[str, list[tuple[int | bool, float]]] = defaultdict(list)
    for target, probability, action in zip(targets, probabilities, actions, strict=True):
        grouped[action].append((target, probability))
    return {
        action: binary_probability_metrics(
            (row[0] for row in rows),
            (row[1] for row in rows),
        )
        for action, rows in sorted(grouped.items())
    }


def reliability_bins(
    targets: np.ndarray,
    probabilities: np.ndarray,
    *,
    bins: int = 10,
) -> list[dict[str, int | float]]:
    if not len(targets):
        return []
    indexes = np.minimum((probabilities * bins).astype(int), bins - 1)
    rows: list[dict[str, int | float]] = []
    for index in range(bins):
        mask = indexes == index
        count = int(mask.sum())
        if not count:
            continue
        mean_prediction = float(probabilities[mask].mean())
        outcome_rate = float(targets[mask].mean())
        rows.append(
            {
                "bin": index,
                "lower": index / bins,
                "upper": (index + 1) / bins,
                "count": count,
                "mean_prediction": mean_prediction,
                "outcome_rate": outcome_rate,
                "absolute_gap": abs(mean_prediction - outcome_rate),
            }
        )
    return rows


def _ece(rows: list[dict[str, int | float]], total: int) -> float | None:
    if not total:
        return None
    return sum(
        int(row["count"]) / total * abs(float(row["mean_prediction"]) - float(row["outcome_rate"]))
        for row in rows
    )
