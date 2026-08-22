from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from recoveriq_ml.artifacts import sha256_file, software_versions, write_json
from recoveriq_ml_v2.features import build_feature_snapshot_v2
from recoveriq_ml_v2.models import LoggedSequentialDecision, SequentialDatasetManifest
from recoveriq_sequential.episodes import (
    advance_episode_state,
    build_episode_templates,
    generate_sequential_candidates,
    initial_episode_state,
)
from recoveriq_sequential.models import EpisodeTermination, SequentialCandidate
from recoveriq_sequential.oracle import SequentialScenarioOracle
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.randomness import keyed_uniform
from recoveriq_simulator.scenario import ScenarioGenerator


@dataclass(frozen=True, slots=True)
class SequentialGenerationResult:
    logged_rows: tuple[dict[str, Any], ...]
    candidate_truth_rows: tuple[dict[str, Any], ...]
    episode_count: int


class UniformObservableSequentialBehavior:
    """Uniform selection over an already observable/feasible candidate tuple."""

    def select(
        self,
        *,
        seed: int,
        episode_id: str,
        decision_index: int,
        candidates: tuple[SequentialCandidate, ...],
    ) -> tuple[SequentialCandidate, float]:
        if not candidates:
            raise ValueError("behaviour policy requires at least one feasible candidate")
        draw = keyed_uniform(
            seed,
            "sequential-uniform-behaviour-v2",
            episode_id,
            decision_index,
        )
        index = min(int(draw * len(candidates)), len(candidates) - 1)
        return candidates[index], 1.0 / len(candidates)


def generate_sequential_trajectories(
    scenario: GeneratedScenario,
    config: SimulatorConfig,
    *,
    include_candidate_truth: bool,
) -> SequentialGenerationResult:
    behavior = UniformObservableSequentialBehavior()
    oracle = SequentialScenarioOracle(scenario, config)
    logged_rows: list[dict[str, Any]] = []
    truth_rows: list[dict[str, Any]] = []
    templates = build_episode_templates(scenario, config.seed)
    for template in templates:
        state = initial_episode_state(template)
        while state.termination is EpisodeTermination.ACTIVE:
            candidates = generate_sequential_candidates(template, state, config.resolved_costs)
            if not candidates:
                state = state.model_copy(
                    update={"termination": EpisodeTermination.NO_FEASIBLE_ACTION}
                )
                break
            selected, propensity = behavior.select(
                seed=config.seed,
                episode_id=state.episode_id,
                decision_index=state.decision_index,
                candidates=candidates,
            )
            decision_key = f"{state.episode_id}:{state.decision_index}"
            if include_candidate_truth:
                hidden_family = oracle.hidden_failure_family(template)
                for candidate in candidates:
                    candidate_features = build_feature_snapshot_v2(template, state, candidate)
                    truth_rows.append(
                        {
                            "decision_key": decision_key,
                            "episode_id": state.episode_id,
                            "decision_index": state.decision_index,
                            "candidate_label": candidate.label,
                            "candidate_rank": _candidate_rank(candidate.label),
                            "oracle_probability": oracle.probability(template, state, candidate),
                            "hidden_failure_family": hidden_family,
                            **candidate_features.model_features(),
                        }
                    )
            features = build_feature_snapshot_v2(template, state, selected)
            outcome = oracle.execute(template, state, selected)
            next_state = advance_episode_state(template, state, selected, outcome)
            record = LoggedSequentialDecision(
                episode_id=state.episode_id,
                decision_key=decision_key,
                decision_index=state.decision_index,
                decision_at=state.decision_at,
                selected_action_label=selected.label,
                selected_action_type=selected.recovery_action.action_type.value,
                selection_propensity=propensity,
                feasible_candidate_count=len(candidates),
                action_recovered_before_next_decision=outcome.recovered,
                episode_termination_after_action=next_state.termination.value,
                features=features,
            )
            logged_rows.append(_flatten_record(record))
            state = next_state
    return SequentialGenerationResult(
        logged_rows=tuple(logged_rows),
        candidate_truth_rows=tuple(truth_rows),
        episode_count=len(templates),
    )


def generate_and_write_logged_group(
    *,
    group: str,
    seeds: tuple[int, ...],
    logged_root: Path,
    include_candidate_truth: bool = False,
) -> dict[str, Any]:
    parquet_path = logged_root / f"sequential-{group}-v2.parquet"
    manifest_path = logged_root / f"sequential-{group}-manifest-v2.json"
    truth_path = logged_root / f"sequential-{group}-candidate-truth-v2.parquet"
    if parquet_path.exists() or manifest_path.exists() or truth_path.exists():
        raise FileExistsError(f"sequential logged group already exists: {group}")
    started = perf_counter()
    rows: list[dict[str, Any]] = []
    truth_rows: list[dict[str, Any]] = []
    episode_count = 0
    seed_counts: dict[str, dict[str, int]] = {}
    for seed in seeds:
        config = SimulatorConfig(seed=seed)
        scenario = ScenarioGenerator(config).generate()
        result = generate_sequential_trajectories(
            scenario,
            config,
            include_candidate_truth=include_candidate_truth,
        )
        rows.extend(result.logged_rows)
        truth_rows.extend(result.candidate_truth_rows)
        episode_count += result.episode_count
        seed_counts[str(seed)] = {
            "episodes": result.episode_count,
            "decisions": len(result.logged_rows),
        }
    logged_root.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_parquet(parquet_path, index=False)
    if include_candidate_truth:
        pd.DataFrame(truth_rows).to_parquet(truth_path, index=False)
    decisions_by_index = {
        str(key): int(value)
        for key, value in frame["decision_index"].value_counts().sort_index().items()
    }
    actions = {
        str(key): int(value)
        for key, value in frame["selected_action_label"].value_counts().sort_index().items()
    }
    positives = int(frame["action_recovered_before_next_decision"].sum())
    propensities = {
        str(key): int(value)
        for key, value in frame["selection_propensity"].value_counts().sort_index().items()
    }
    manifest = SequentialDatasetManifest(
        group=group,
        seeds=seeds,
        episode_count=episode_count,
        decision_count=len(frame),
        decisions_by_index=decisions_by_index,
        action_counts=actions,
        positive_count=positives,
        positive_rate=positives / len(frame) if len(frame) else None,
        propensity_distribution=propensities,
        dataset_sha256=sha256_file(parquet_path),
        software_versions=software_versions(),
    )
    payload = manifest.model_dump(mode="json")
    payload["seed_counts"] = seed_counts
    payload["candidate_truth_row_count"] = len(truth_rows)
    payload["runtime_seconds"] = perf_counter() - started
    write_json(manifest_path, payload)
    return payload


def read_logged_group(logged_root: Path, group: str) -> pd.DataFrame:
    path = logged_root / f"sequential-{group}-v2.parquet"
    frame = pd.read_parquet(path)
    validate_logged_frame(frame)
    return frame


def validate_logged_frame(frame: pd.DataFrame) -> None:
    required = {
        "episode_id",
        "decision_key",
        "decision_index",
        "selection_propensity",
        "action_recovered_before_next_decision",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"sequential logged frame is missing metadata: {sorted(missing)}")
    if not frame["selection_propensity"].between(1 / 9, 1).all():
        raise ValueError("sequential behaviour propensities are outside registered bounds")
    if frame.groupby("decision_key").size().max() != 1:
        raise ValueError("each sequential decision must log exactly one selected action")
    positives = frame[frame["action_recovered_before_next_decision"]]
    if positives.groupby("episode_id").size().max() > 1:
        raise ValueError("recovery attribution appears more than once in an episode")
    if int(frame["decision_index"].max()) > 3:
        raise ValueError("logged episode exceeded three autonomous interventions")


def _flatten_record(record: LoggedSequentialDecision) -> dict[str, Any]:
    payload = record.model_dump(mode="python", exclude={"features"})
    payload.update(record.features.model_features())
    return payload


def _candidate_rank(label: str) -> int:
    from recoveriq_sequential.config import SEQUENTIAL_CANDIDATE_INDEX

    return SEQUENTIAL_CANDIDATE_INDEX[label]
