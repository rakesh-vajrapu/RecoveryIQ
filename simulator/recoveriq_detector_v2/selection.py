from __future__ import annotations

from pathlib import Path
from typing import Any

from recoveriq_detector.artifacts import load_frozen_config
from recoveriq_detector.baselines import BaselineKind, replay_baseline
from recoveriq_detector.evaluation import aggregate_evaluations, evaluate_scenario
from recoveriq_detector.replay import replay_scenario
from recoveriq_detector_v2.config import (
    DEVELOPMENT_CANDIDATES,
    HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY,
    HARD_POLICY_MIN_CONFIRMED_EPISODES,
    DetectorV2Config,
)
from recoveriq_detector_v2.evaluation import aggregate_v2_evaluations, evaluate_v2_scenario
from recoveriq_detector_v2.replay import ReplayV2Result, replay_v2_scenario
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator

SELECTION_OBJECTIVE = (
    "Prefer >=5 confirmed episodes and <=0.005 false confirmed episodes per issuer-scope-day; "
    "then maximize confirmed precision, high-evidence confirmed recall, lower WATCH-to-CONFIRMED "
    "delay, WATCH eligible recall, and lower WATCH delay. If no candidate meets the alert-rate "
    "constraint, minimize false confirmed rate before the same precision/recall ordering."
)


def select_v2_on_development(
    seeds: tuple[int, ...],
    candidates: tuple[DetectorV2Config, ...] = DEVELOPMENT_CANDIDATES,
    base_config: SimulatorConfig | None = None,
) -> tuple[DetectorV2Config, dict[str, Any], tuple[ReplayV2Result, ...]]:
    simulator_config = base_config or SimulatorConfig()
    evaluation_lists: list[list[dict[str, Any]]] = [[] for _candidate in candidates]
    replay_lists: list[list[ReplayV2Result]] = [[] for _candidate in candidates]
    for seed in seeds:
        scenario = ScenarioGenerator(simulator_config.model_copy(update={"seed": seed})).generate()
        for index, candidate in enumerate(candidates):
            replay = replay_v2_scenario(scenario, candidate, sample_every=0)
            replay_lists[index].append(replay)
            evaluation_lists[index].append(
                evaluate_v2_scenario(scenario, replay.episodes, candidate)
            )
    rows: list[dict[str, Any]] = []
    aggregate_metrics: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        metrics = aggregate_v2_evaluations(evaluation_lists[index])
        aggregate_metrics.append(metrics)
        rows.append(
            {
                "candidate_index": index,
                "configuration_hash": candidate.configuration_hash,
                "config": candidate.model_dump(mode="json"),
                "metrics": _compact_metrics(metrics),
                "throughput_events_per_second": _throughput(tuple(replay_lists[index])),
            }
        )
    constrained = [
        row
        for row in rows
        if int(row["metrics"]["confirmed"]["episode_count"]) >= HARD_POLICY_MIN_CONFIRMED_EPISODES
        and float(row["metrics"]["confirmed"]["false_episodes_per_scope_day"] or 0.0)
        <= HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY
    ]
    chosen_row = (
        max(constrained, key=_selection_key) if constrained else min(rows, key=_fallback_key)
    )
    chosen_index = int(chosen_row["candidate_index"])
    chosen = candidates[chosen_index]
    chosen_replays = tuple(replay_lists[chosen_index])
    comparators = _development_comparators(seeds, simulator_config)
    report = {
        "phase": "detector_v2_development_selection",
        "selection_objective": SELECTION_OBJECTIVE,
        "seeds": list(seeds),
        "candidate_count": len(candidates),
        "candidates": rows,
        "chosen_candidate_index": chosen_index,
        "configuration_hash": chosen.configuration_hash,
        "config": chosen.model_dump(mode="json"),
        "metrics": aggregate_metrics[chosen_index],
        "comparators": comparators,
        "throughput_events_per_second": _throughput(chosen_replays),
        "mean_update_latency_ms": _latency(chosen_replays),
    }
    return chosen, report, chosen_replays


def evaluate_v2_frozen(
    seeds: tuple[int, ...],
    config: DetectorV2Config,
    base_config: SimulatorConfig | None = None,
) -> tuple[dict[str, Any], tuple[ReplayV2Result, ...]]:
    simulator_config = base_config or SimulatorConfig()
    evaluations: list[dict[str, Any]] = []
    replays: list[ReplayV2Result] = []
    comparator_v1: list[dict[str, Any]] = []
    comparator_baselines: dict[BaselineKind, list[dict[str, Any]]] = {
        kind: [] for kind in BaselineKind
    }
    v1_config = _v1_config()
    for seed in seeds:
        scenario = ScenarioGenerator(simulator_config.model_copy(update={"seed": seed})).generate()
        replay = replay_v2_scenario(scenario, config)
        replays.append(replay)
        evaluations.append(evaluate_v2_scenario(scenario, replay.episodes, config))
        v1_replay = replay_scenario(scenario, v1_config, sample_every=0)
        comparator_v1.append(evaluate_scenario(scenario, v1_replay.incidents))
        for kind in BaselineKind:
            comparator_baselines[kind].append(
                evaluate_scenario(scenario, replay_baseline(scenario, v1_config, kind))
            )
    replay_tuple = tuple(replays)
    return (
        {
            "phase": "detector_v2_one_time_validation",
            "seeds": list(seeds),
            "configuration_hash": config.configuration_hash,
            "config": config.model_dump(mode="json"),
            "metrics": aggregate_v2_evaluations(evaluations),
            "comparators": {
                "DETECTOR_V1": aggregate_evaluations(comparator_v1),
                **{
                    kind.value: aggregate_evaluations(rows)
                    for kind, rows in comparator_baselines.items()
                },
            },
            "throughput_events_per_second": _throughput(replay_tuple),
            "mean_update_latency_ms": _latency(replay_tuple),
        },
        replay_tuple,
    )


def _development_comparators(
    seeds: tuple[int, ...],
    simulator_config: SimulatorConfig,
) -> dict[str, Any]:
    v1_config = _v1_config()
    v1_rows: list[dict[str, Any]] = []
    baseline_rows: dict[BaselineKind, list[dict[str, Any]]] = {kind: [] for kind in BaselineKind}
    for seed in seeds:
        scenario = ScenarioGenerator(simulator_config.model_copy(update={"seed": seed})).generate()
        v1_rows.append(
            evaluate_scenario(
                scenario,
                replay_scenario(scenario, v1_config, sample_every=0).incidents,
            )
        )
        for kind in BaselineKind:
            baseline_rows[kind].append(
                evaluate_scenario(scenario, replay_baseline(scenario, v1_config, kind))
            )
    return {
        "DETECTOR_V1": aggregate_evaluations(v1_rows),
        **{kind.value: aggregate_evaluations(rows) for kind, rows in baseline_rows.items()},
    }


def _v1_config() -> Any:
    path = (
        Path(__file__).resolve().parents[2]
        / "artifacts"
        / "detector"
        / "degradation-detector-v1.json"
    )
    return load_frozen_config(path)


def _compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in metrics.items() if key not in {"per_seed", "false_confirmed"}
    }


def _selection_key(row: dict[str, Any]) -> tuple[float, float, float, float, float]:
    metrics = row["metrics"]
    confirmed = metrics["confirmed"]
    watch = metrics["watch"]
    watch_to_confirm = confirmed["watch_to_confirmed_delay_minutes"]["median"]
    watch_delay = watch["detection_delay_minutes"]["median"]
    return (
        float(confirmed["episode_precision"] or 0.0),
        float(confirmed["high_evidence_incident_recall"] or 0.0),
        -float(watch_to_confirm if watch_to_confirm is not None else 1e12),
        float(watch["eligible_incident_recall"] or 0.0),
        -float(watch_delay if watch_delay is not None else 1e12),
    )


def _fallback_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    metrics = row["metrics"]
    confirmed = metrics["confirmed"]
    return (
        float(confirmed["false_episodes_per_scope_day"] or 0.0),
        -float(confirmed["episode_precision"] or 0.0),
        -float(confirmed["high_evidence_incident_recall"] or 0.0),
        -float(metrics["watch"]["eligible_incident_recall"] or 0.0),
    )


def _throughput(replays: tuple[ReplayV2Result, ...]) -> float:
    elapsed = sum(replay.runtime_seconds for replay in replays)
    return sum(replay.events_processed for replay in replays) / elapsed if elapsed else 0.0


def _latency(replays: tuple[ReplayV2Result, ...]) -> float:
    events = sum(replay.events_processed for replay in replays)
    elapsed = sum(replay.runtime_seconds for replay in replays)
    return 1000 * elapsed / events if events else 0.0
