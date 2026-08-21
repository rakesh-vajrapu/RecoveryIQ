"""Small one-factor configuration sweep for simulator robustness checks."""

from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import fmean

from pydantic import BaseModel, ConfigDict

from recoveriq_simulator.artifacts import default_artifact_root
from recoveriq_simulator.benchmark import run_benchmark
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.enums import CostRegime, IncidentSeverityProfile
from recoveriq_simulator.seeds import DEVELOPMENT_SEEDS


class FrozenSensitivityModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SensitivityCaseResult(FrozenSensitivityModel):
    name: str
    changed_assumption: str
    policy_means: dict[str, dict[str, float]]
    ranking: dict[str, str]


class SensitivityReport(FrozenSensitivityModel):
    report_id: str
    simulator_version: str
    seeds: tuple[int, ...]
    attempts_per_environment: int
    cases: tuple[SensitivityCaseResult, ...]
    ranking_changes_from_control: tuple[str, ...]
    total_runtime_seconds: float


def _case_configs(base: SimulatorConfig) -> tuple[tuple[str, str, SimulatorConfig], ...]:
    return (
        ("CONTROL", "balanced defaults", base),
        (
            "SUBTLE_INCIDENTS",
            "incident severity profile",
            base.model_copy(update={"incident_severity_profile": IncidentSeverityProfile.SUBTLE}),
        ),
        (
            "HARSH_INCIDENTS",
            "incident severity profile",
            base.model_copy(update={"incident_severity_profile": IncidentSeverityProfile.HARSH}),
        ),
        ("SPARSE_INCIDENTS", "incident frequency", base.model_copy(update={"incident_count": 8})),
        (
            "FREQUENT_INCIDENTS",
            "incident frequency",
            base.model_copy(update={"incident_count": 30}),
        ),
        (
            "WEAK_NUDGE",
            "nudge responsiveness strength",
            base.model_copy(update={"nudge_effect_strength": 0.35}),
        ),
        (
            "STRONG_NUDGE",
            "nudge responsiveness strength",
            base.model_copy(update={"nudge_effect_strength": 1.45}),
        ),
        (
            "LOW_FRICTION",
            "synthetic cost regime",
            base.model_copy(update={"cost_regime": CostRegime.LOW_FRICTION}),
        ),
        (
            "HIGH_FRICTION",
            "synthetic cost regime",
            base.model_copy(update={"cost_regime": CostRegime.HIGH_FRICTION}),
        ),
    )


def run_sensitivity_sweep(
    *,
    attempts: int = 5_000,
    seeds: tuple[int, ...] = DEVELOPMENT_SEEDS[:3],
) -> SensitivityReport:
    started = time.perf_counter()
    base = SimulatorConfig(num_payment_attempts=attempts)
    case_results: list[SensitivityCaseResult] = []
    for name, assumption, template in _case_configs(base):
        metrics_by_policy: dict[str, list[dict[str, float]]] = {}
        for seed in seeds:
            config = template.model_copy(update={"seed": seed})
            _, benchmark = run_benchmark(config)
            for evaluation in benchmark.policies:
                metrics_by_policy.setdefault(evaluation.policy_name, []).append(
                    {
                        "recovery_rate": evaluation.metrics.recovery_rate,
                        "gross_recovered_amount_minor": float(
                            evaluation.metrics.gross_recovered_amount_minor
                        ),
                        "net_recovered_value_minor": float(
                            evaluation.metrics.net_recovered_value_minor
                        ),
                    }
                )
        policy_means = {
            policy: {metric: fmean(run[metric] for run in runs) for metric in runs[0]}
            for policy, runs in metrics_by_policy.items()
        }
        ranking = {
            metric: max(policy_means, key=lambda policy: policy_means[policy][metric])
            for metric in (
                "recovery_rate",
                "gross_recovered_amount_minor",
                "net_recovered_value_minor",
            )
        }
        case_results.append(
            SensitivityCaseResult(
                name=name,
                changed_assumption=assumption,
                policy_means=policy_means,
                ranking=ranking,
            )
        )
    control = case_results[0].ranking
    changes = tuple(
        f"{case.name}:{metric}:{control[metric]}->{winner}"
        for case in case_results[1:]
        for metric, winner in case.ranking.items()
        if winner != control[metric]
    )
    return SensitivityReport(
        report_id=f"sensitivity-v{base.simulator_version.replace('.', '')}-{attempts}",
        simulator_version=base.simulator_version,
        seeds=seeds,
        attempts_per_environment=attempts,
        cases=tuple(case_results),
        ranking_changes_from_control=changes,
        total_runtime_seconds=time.perf_counter() - started,
    )


def write_sensitivity_report(report: SensitivityReport, artifact_root: Path | None = None) -> Path:
    root = artifact_root or default_artifact_root().parent / "sensitivity"
    output = root / report.report_id
    output.mkdir(parents=True, exist_ok=True)
    (output / "sensitivity_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "sensitivity_report.md").write_text(
        render_sensitivity_markdown(report), encoding="utf-8", newline="\n"
    )
    return output


def render_sensitivity_markdown(report: SensitivityReport) -> str:
    lines = [
        "# RecoverIQ Simulator Sensitivity Sweep",
        "",
        f"Seeds: `{', '.join(str(seed) for seed in report.seeds)}`  ",
        f"Attempts/environment: {report.attempts_per_environment:,}  ",
        f"Runtime: {report.total_runtime_seconds:.3f}s",
        "",
        "| Case | Policy | Recovery rate | Gross recovered (minor) | Net value (minor) |",
        "|---|---|---:|---:|---:|",
    ]
    for case in report.cases:
        for policy, metrics in case.policy_means.items():
            lines.append(
                f"| {case.name} | {policy} | {metrics['recovery_rate']:.2%} | "
                f"{metrics['gross_recovered_amount_minor']:.0f} | "
                f"{metrics['net_recovered_value_minor']:.0f} |"
            )
    lines.extend(
        [
            "",
            "Ranking changes from control:",
            "",
            *(f"- {change}" for change in report.ranking_changes_from_control),
        ]
    )
    if not report.ranking_changes_from_control:
        lines.append("- None in this bounded sweep.")
    lines.append("")
    return "\n".join(lines)
