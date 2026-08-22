from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from recoveriq_detector.baselines import BaselineKind, replay_baseline
from recoveriq_detector.config import DEVELOPMENT_CANDIDATES, DetectorConfig
from recoveriq_detector.evaluation import aggregate_evaluations, evaluate_scenario
from recoveriq_detector.replay import ReplayResult, replay_scenario
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.scenario import ScenarioGenerator

MAX_FALSE_INCIDENTS_PER_SCOPE_DAY = 0.02
SELECTION_OBJECTIVE = (
    "Among candidates with <= 0.02 false issuer incidents per scope-day, maximize "
    "eligible-incident recall; break ties by precision, then lower median delay after the "
    "fifth observable attempt. If none satisfy the constraint, minimize false incidents "
    "per scope-day before applying the same tie-breakers."
)


@dataclass(frozen=True, slots=True)
class SelectionRun:
    chosen_config: DetectorConfig
    report: dict[str, Any]
    chosen_replays: tuple[ReplayResult, ...]


def generate_scenarios(
    seeds: tuple[int, ...],
    base_config: SimulatorConfig | None = None,
) -> tuple[GeneratedScenario, ...]:
    config = base_config or SimulatorConfig()
    return tuple(
        ScenarioGenerator(config.model_copy(update={"seed": seed})).generate() for seed in seeds
    )


def select_development_config(
    seeds: tuple[int, ...],
    candidates: tuple[DetectorConfig, ...] = DEVELOPMENT_CANDIDATES,
    base_config: SimulatorConfig | None = None,
) -> SelectionRun:
    simulator_config = base_config or SimulatorConfig()
    candidate_evaluations: list[list[dict[str, Any]]] = [[] for _candidate in candidates]
    candidate_replay_lists: list[list[ReplayResult]] = [[] for _candidate in candidates]
    for seed in seeds:
        scenario = ScenarioGenerator(simulator_config.model_copy(update={"seed": seed})).generate()
        for index, config in enumerate(candidates):
            replay = replay_scenario(scenario, config, sample_every=0)
            candidate_replay_lists[index].append(replay)
            candidate_evaluations[index].append(evaluate_scenario(scenario, replay.incidents))

    candidate_rows: list[dict[str, Any]] = []
    candidate_replays: list[tuple[ReplayResult, ...]] = []
    for index, config in enumerate(candidates):
        replays = tuple(candidate_replay_lists[index])
        metrics = aggregate_evaluations(candidate_evaluations[index])
        candidate_replays.append(replays)
        candidate_rows.append(
            {
                "candidate_index": index,
                "configuration_hash": config.configuration_hash,
                "config": config.model_dump(mode="json"),
                "metrics": metrics,
                "throughput_events_per_second": _combined_throughput(replays),
            }
        )

    constrained = [
        row
        for row in candidate_rows
        if float(row["metrics"]["false_incidents_per_scope_day"] or 0.0)
        <= MAX_FALSE_INCIDENTS_PER_SCOPE_DAY
    ]
    if constrained:
        chosen = max(constrained, key=_selection_key)
    else:
        chosen = min(candidate_rows, key=_fallback_selection_key)
    chosen_index = int(chosen["candidate_index"])
    chosen_config = candidates[chosen_index]
    chosen_replays = candidate_replays[chosen_index]
    baseline_evaluations: dict[BaselineKind, list[dict[str, Any]]] = {
        kind: [] for kind in BaselineKind
    }
    for seed in seeds:
        scenario = ScenarioGenerator(simulator_config.model_copy(update={"seed": seed})).generate()
        for kind in BaselineKind:
            baseline_evaluations[kind].append(
                evaluate_scenario(
                    scenario,
                    replay_baseline(scenario, chosen_config, kind),
                )
            )
    baseline_metrics = {
        kind.value: aggregate_evaluations(rows) for kind, rows in baseline_evaluations.items()
    }
    report = {
        "phase": "development_selection",
        "selection_objective": SELECTION_OBJECTIVE,
        "false_incident_constraint_per_scope_day": MAX_FALSE_INCIDENTS_PER_SCOPE_DAY,
        "candidate_count": len(candidates),
        "candidates": candidate_rows,
        "chosen_candidate_index": chosen_index,
        "chosen_configuration_hash": chosen_config.configuration_hash,
        "chosen_config": chosen_config.model_dump(mode="json"),
        "metrics": chosen["metrics"],
        "baseline_detector_comparison": baseline_metrics,
        "throughput_events_per_second": _combined_throughput(chosen_replays),
        "mean_update_latency_ms": _mean_latency(chosen_replays),
    }
    return SelectionRun(
        chosen_config=chosen_config,
        report=report,
        chosen_replays=chosen_replays,
    )


def evaluate_frozen_config(
    seeds: tuple[int, ...],
    config: DetectorConfig,
    base_config: SimulatorConfig | None = None,
) -> tuple[dict[str, Any], tuple[ReplayResult, ...]]:
    simulator_config = base_config or SimulatorConfig()
    replay_list: list[ReplayResult] = []
    evaluations: list[dict[str, Any]] = []
    baseline_evaluations: dict[BaselineKind, list[dict[str, Any]]] = {
        kind: [] for kind in BaselineKind
    }
    for seed in seeds:
        scenario = ScenarioGenerator(simulator_config.model_copy(update={"seed": seed})).generate()
        replay = replay_scenario(scenario, config)
        replay_list.append(replay)
        evaluations.append(evaluate_scenario(scenario, replay.incidents))
        for kind in BaselineKind:
            baseline_evaluations[kind].append(
                evaluate_scenario(
                    scenario,
                    replay_baseline(scenario, config, kind),
                )
            )
    replays = tuple(replay_list)
    metrics = aggregate_evaluations(evaluations)
    baselines = {
        kind.value: aggregate_evaluations(rows) for kind, rows in baseline_evaluations.items()
    }
    return (
        {
            "phase": "validation_frozen_configuration",
            "configuration_hash": config.configuration_hash,
            "config": config.model_dump(mode="json"),
            "metrics": metrics,
            "baseline_detector_comparison": baselines,
            "throughput_events_per_second": _combined_throughput(replays),
            "mean_update_latency_ms": _mean_latency(replays),
        },
        replays,
    )


def _selection_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    metrics = row["metrics"]
    delay = metrics["delay_after_sufficient_evidence_minutes"]["median"]
    return (
        float(metrics["eligible_incident_recall"] or 0.0),
        float(metrics["predicted_incident_precision"] or 0.0),
        -float(delay if delay is not None else 1e12),
        -float(metrics["false_incidents_per_scope_day"] or 0.0),
    )


def _fallback_selection_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    metrics = row["metrics"]
    delay = metrics["delay_after_sufficient_evidence_minutes"]["median"]
    return (
        float(metrics["false_incidents_per_scope_day"] or 0.0),
        -float(metrics["eligible_incident_recall"] or 0.0),
        -float(metrics["predicted_incident_precision"] or 0.0),
        float(delay if delay is not None else 1e12),
    )


def _combined_throughput(replays: tuple[ReplayResult, ...]) -> float:
    elapsed = sum(replay.runtime_seconds for replay in replays)
    return sum(replay.events_processed for replay in replays) / elapsed if elapsed else 0.0


def _mean_latency(replays: tuple[ReplayResult, ...]) -> float:
    events = sum(replay.events_processed for replay in replays)
    elapsed = sum(replay.runtime_seconds for replay in replays)
    return 1000 * elapsed / events if events else 0.0
