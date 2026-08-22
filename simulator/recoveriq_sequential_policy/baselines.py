from __future__ import annotations

from typing import Any, cast

import pandas as pd

from recoveriq_ml_v2.training import TARGET_COLUMN
from recoveriq_sequential.config import SEQUENTIAL_CANDIDATE_INDEX
from recoveriq_sequential_policy.models import FrozenSequentialBaselines

SIMPLE_MIN_SUPPORT = 300
GLOBAL_MIN_SUPPORT = 500


def fit_sequential_baselines(
    frame: pd.DataFrame,
    development_seeds: tuple[int, ...],
) -> FrozenSequentialBaselines:
    enriched = frame.copy()
    enriched["target_int"] = enriched[TARGET_COLUMN].astype(int)
    simple_mapping: dict[str, str] = {}
    diagnostics: dict[str, Any] = {"simple_cells": {}, "stage_actions": {}}
    simple_group = enriched.groupby(
        ["failure_reason", "decision_index", "selected_action_label"],
        sort=True,
    )["target_int"].agg(["count", "mean"])
    cell_candidates: dict[str, list[tuple[str, int, float]]] = {}
    for group_key, values in simple_group.iterrows():
        reason, index, action = cast(tuple[str, int, str], group_key)
        key = f"{reason}|{index}"
        cell_candidates.setdefault(key, []).append(
            (action, int(values["count"]), float(values["mean"]))
        )
    for key, rows in cell_candidates.items():
        supported = [row for row in rows if row[1] >= SIMPLE_MIN_SUPPORT]
        ordered = sorted(
            supported,
            key=lambda row: (-row[2], SEQUENTIAL_CANDIDATE_INDEX[row[0]]),
        )
        if ordered:
            simple_mapping[key] = ordered[0][0]
        diagnostics["simple_cells"][key] = [
            {"action": action, "support": support, "recovery_rate": rate}
            for action, support, rate in sorted(
                rows, key=lambda row: SEQUENTIAL_CANDIDATE_INDEX[row[0]]
            )
        ]

    stage_rankings: dict[str, tuple[str, ...]] = {}
    stage_group = enriched.groupby(["decision_index", "selected_action_label"], sort=True)[
        "target_int"
    ].agg(["count", "mean"])
    for index in (1, 2, 3):
        stage_rows: list[tuple[str, int, float]] = []
        for group_key, values in stage_group.iterrows():
            stage, action = cast(tuple[int, str], group_key)
            if stage == index:
                stage_rows.append((action, int(values["count"]), float(values["mean"])))
        supported = [row for row in stage_rows if row[1] >= GLOBAL_MIN_SUPPORT]
        ordered = sorted(
            supported,
            key=lambda row: (-row[2], SEQUENTIAL_CANDIDATE_INDEX[row[0]]),
        )
        stage_rankings[str(index)] = tuple(row[0] for row in ordered)
        diagnostics["stage_actions"][str(index)] = [
            {"action": action, "support": support, "recovery_rate": rate}
            for action, support, rate in ordered
        ]
    return FrozenSequentialBaselines(
        development_seeds=development_seeds,
        target=TARGET_COLUMN,
        simple_min_support=SIMPLE_MIN_SUPPORT,
        global_min_support=GLOBAL_MIN_SUPPORT,
        simple_mapping=simple_mapping,
        stage_rankings=stage_rankings,
        cell_diagnostics=diagnostics,
    )
