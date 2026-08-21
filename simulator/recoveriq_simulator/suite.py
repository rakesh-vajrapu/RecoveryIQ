"""Multi-seed robustness benchmarking and aggregate confidence intervals."""

from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, median, stdev
from typing import Any

from pydantic import BaseModel, ConfigDict

from recoveriq_simulator.analysis import build_analysis
from recoveriq_simulator.artifacts import default_artifact_root
from recoveriq_simulator.benchmark import run_benchmark
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.seeds import seeds_for_group


class FrozenSuiteModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MetricSummary(FrozenSuiteModel):
    mean: float
    median: float
    standard_deviation: float
    minimum: float
    maximum: float
    confidence_interval_95_low: float
    confidence_interval_95_high: float


class SeedRunSummary(FrozenSuiteModel):
    seed: int
    experiment_id: str
    runtime_seconds: float
    failure_rate: float
    incident_attempt_proportion: float
    incident_failure_proportion: float
    success_rate_inside_incidents: float | None
    success_rate_outside_incidents: float | None
    incident_severity_counts: dict[str, int]
    incident_durations_hours: tuple[float, ...]
    policy_metrics: dict[str, dict[str, float | int | None]]
    quality_analysis: dict[str, Any]


class MultiSeedReport(FrozenSuiteModel):
    suite_id: str
    simulator_version: str
    seed_group: str
    seeds: tuple[int, ...]
    configuration_without_seed: dict[str, Any]
    runs: tuple[SeedRunSummary, ...]
    environment_metrics: dict[str, MetricSummary | None]
    policy_metrics: dict[str, dict[str, MetricSummary]]
    incident_severity_counts: dict[str, int]
    incident_duration_hours: MetricSummary
    quality_aggregate: dict[str, Any]
    total_runtime_seconds: float
    mean_runtime_per_environment_seconds: float
    report_artifact_bytes: int


AGGREGATE_POLICY_FIELDS = (
    "recovered_payment_count",
    "recovery_rate",
    "gross_recovered_amount_minor",
    "net_recovered_value_minor",
    "retry_count",
    "customer_contact_count",
    "average_time_to_recovery_hours",
)


def summarize_metric(values: list[float]) -> MetricSummary:
    if not values:
        raise ValueError("cannot summarize an empty metric")
    sample_deviation = stdev(values) if len(values) > 1 else 0.0
    margin = 1.96 * sample_deviation / math.sqrt(len(values))
    mean = fmean(values)
    return MetricSummary(
        mean=mean,
        median=median(values),
        standard_deviation=sample_deviation,
        minimum=min(values),
        maximum=max(values),
        confidence_interval_95_low=mean - margin,
        confidence_interval_95_high=mean + margin,
    )


def run_seed_suite(
    *,
    group: str,
    base_config: SimulatorConfig,
    seeds: tuple[int, ...] | None = None,
) -> MultiSeedReport:
    selected_seeds = seeds if seeds is not None else seeds_for_group(group)
    if not selected_seeds:
        raise ValueError("seed suite cannot be empty")
    started = time.perf_counter()
    runs: list[SeedRunSummary] = []
    severity_counts: Counter[str] = Counter()
    all_durations: list[float] = []
    for seed in selected_seeds:
        run_started = time.perf_counter()
        config = base_config.model_copy(update={"seed": seed})
        scenario, benchmark = run_benchmark(config)
        analysis = build_analysis(scenario, config, benchmark)
        incident = analysis["incident_coverage"]
        durations = tuple(
            (item.end_at - item.start_at).total_seconds() / 3600.0
            for item in scenario.ground_truth.incidents
        )
        severity_counts.update(incident["count_by_severity"])
        all_durations.extend(durations)
        runs.append(
            SeedRunSummary(
                seed=seed,
                experiment_id=config.experiment_id,
                runtime_seconds=time.perf_counter() - run_started,
                failure_rate=analysis["failure_rate"],
                incident_attempt_proportion=incident["attempt_proportion"],
                incident_failure_proportion=incident["failure_proportion"],
                success_rate_inside_incidents=incident["success_rate_inside"],
                success_rate_outside_incidents=incident["success_rate_outside"],
                incident_severity_counts=incident["count_by_severity"],
                incident_durations_hours=durations,
                policy_metrics={
                    policy.policy_name: {
                        field: getattr(policy.metrics, field) for field in AGGREGATE_POLICY_FIELDS
                    }
                    for policy in benchmark.policies
                },
                quality_analysis=analysis,
            )
        )

    environment_values: dict[str, list[float | None]] = {
        "failure_rate": [run.failure_rate for run in runs],
        "incident_attempt_proportion": [run.incident_attempt_proportion for run in runs],
        "incident_failure_proportion": [run.incident_failure_proportion for run in runs],
        "success_rate_inside_incidents": [run.success_rate_inside_incidents for run in runs],
        "success_rate_outside_incidents": [run.success_rate_outside_incidents for run in runs],
    }
    environment_metrics: dict[str, MetricSummary | None] = {}
    for name, values in environment_values.items():
        numeric_values = [float(value) for value in values if value is not None]
        environment_metrics[name] = summarize_metric(numeric_values) if numeric_values else None
    policy_names = tuple(runs[0].policy_metrics)
    policy_metrics: dict[str, dict[str, MetricSummary]] = {}
    for policy_name in policy_names:
        policy_metrics[policy_name] = {}
        for field in AGGREGATE_POLICY_FIELDS:
            values = [run.policy_metrics[policy_name][field] for run in runs]
            numeric_values = [float(value) for value in values if value is not None]
            policy_metrics[policy_name][field] = summarize_metric(numeric_values)

    config_without_seed = base_config.model_copy(update={"seed": 0})
    suite_id = (
        f"suite-v{base_config.simulator_version.replace('.', '')}-{group}-"
        f"{config_without_seed.configuration_hash[:12]}"
    )
    total_runtime = time.perf_counter() - started
    report = MultiSeedReport(
        suite_id=suite_id,
        simulator_version=base_config.simulator_version,
        seed_group=group,
        seeds=selected_seeds,
        configuration_without_seed=config_without_seed.model_dump(mode="json"),
        runs=tuple(runs),
        environment_metrics=environment_metrics,
        policy_metrics=policy_metrics,
        incident_severity_counts=dict(sorted(severity_counts.items())),
        incident_duration_hours=summarize_metric(all_durations),
        quality_aggregate=_aggregate_quality([run.quality_analysis for run in runs]),
        total_runtime_seconds=total_runtime,
        mean_runtime_per_environment_seconds=fmean(run.runtime_seconds for run in runs),
        report_artifact_bytes=0,
    )
    artifact_bytes = 0
    for _ in range(3):
        report = report.model_copy(update={"report_artifact_bytes": artifact_bytes})
        encoded = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        measured = len(encoded.encode("utf-8"))
        if measured == artifact_bytes:
            break
        artifact_bytes = measured
    return report.model_copy(update={"report_artifact_bytes": artifact_bytes})


def _aggregate_quality(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    def summed_counts(field: str) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for analysis in analyses:
            counter.update(analysis[field])
        return dict(sorted(counter.items()))

    def combined_rates(field: str) -> dict[str, dict[str, float | int]]:
        combined: dict[str, Counter[str]] = defaultdict(Counter)
        for analysis in analyses:
            for group, values in analysis[field].items():
                combined[group].update(
                    attempts=int(values["attempts"]), failures=int(values["failures"])
                )
        return {
            group: {
                "attempts": values["attempts"],
                "failures": values["failures"],
                "failure_rate": values["failures"] / values["attempts"],
            }
            for group, values in sorted(combined.items())
        }

    recovery: dict[str, dict[str, Any]] = {}
    for policy in analyses[0]["recovery_by_hidden_failure_family"]:
        recovery[policy] = {}
        for cause in analyses[0]["recovery_by_hidden_failure_family"][policy]:
            failed = sum(
                analysis["recovery_by_hidden_failure_family"][policy][cause]["failed"]
                for analysis in analyses
            )
            recovered = sum(
                analysis["recovery_by_hidden_failure_family"][policy][cause]["recovered"]
                for analysis in analyses
            )
            recovery[policy][cause] = {
                "failed": failed,
                "recovered": recovered,
                "recovery_rate": recovered / failed if failed else None,
            }

    action_effectiveness: dict[str, dict[str, Any]] = {}
    for policy in analyses[0]["action_effectiveness"]:
        action_effectiveness[policy] = {}
        actions = {
            action for analysis in analyses for action in analysis["action_effectiveness"][policy]
        }
        for action in sorted(actions):
            executed = sum(
                analysis["action_effectiveness"][policy].get(action, {}).get("executed", 0)
                for analysis in analyses
            )
            recoveries = sum(
                analysis["action_effectiveness"][policy].get(action, {}).get("recoveries", 0)
                for analysis in analyses
            )
            action_effectiveness[policy][action] = {
                "executed": executed,
                "recoveries": recoveries,
                "success_rate": recoveries / executed if executed else None,
            }

    nudge_by_cause: dict[str, Any] = {}
    for cause in analyses[0]["nudge_effect_analysis"]["by_hidden_failure_family"]:
        summaries = [
            analysis["nudge_effect_analysis"]["by_hidden_failure_family"][cause]
            for analysis in analyses
        ]
        exposed = sum(summary["exposed"] for summary in summaries)
        direct = sum(summary["direct_nudge_recoveries"] for summary in summaries)
        fixed_recovered = sum(summary["fixed_final_recovered"] for summary in summaries)
        reminder_recovered = sum(summary["reminder_final_recovered"] for summary in summaries)
        nudge_by_cause[cause] = {
            "exposed": exposed,
            "direct_nudge_recoveries": direct,
            "direct_nudge_recovery_rate": direct / exposed if exposed else None,
            "fixed_final_recovery_rate": fixed_recovered / exposed if exposed else None,
            "reminder_final_recovery_rate": reminder_recovered / exposed if exposed else None,
            "final_recovery_lift": (
                (reminder_recovered - fixed_recovered) / exposed if exposed else None
            ),
        }

    missing_keys = tuple(analyses[0]["missing_data_rates"])
    return {
        "payments_per_merchant_total": summed_counts("payments_per_merchant"),
        "payment_method_counts_total": summed_counts("payment_method_counts"),
        "issuer_counts_total": summed_counts("issuer_counts"),
        "observable_failure_reason_counts_total": summed_counts("observable_failure_reason_counts"),
        "hidden_failure_family_counts_total": summed_counts("hidden_failure_family_counts"),
        "failure_rates_by_method": combined_rates("failure_rates_by_method"),
        "failure_rates_by_issuer": combined_rates("failure_rates_by_issuer"),
        "subscription_value_seed_medians": summarize_metric(
            [analysis["subscription_value_minor"]["median"] for analysis in analyses]
        ).model_dump(mode="json"),
        "customer_history_seed_means": summarize_metric(
            [analysis["customer_prior_attempt_distribution"]["mean"] for analysis in analyses]
        ).model_dump(mode="json"),
        "missing_data_rate_means": {
            key: fmean(analysis["missing_data_rates"][key] for analysis in analyses)
            for key in missing_keys
        },
        "incidents_by_method_issuer_total": dict(
            sorted(
                sum(
                    (
                        Counter(analysis["incident_coverage"]["incidents_by_method_issuer"])
                        for analysis in analyses
                    ),
                    Counter(),
                ).items()
            )
        ),
        "recovery_by_hidden_failure_family": recovery,
        "action_effectiveness": action_effectiveness,
        "nudge_effect_by_hidden_failure_family": nudge_by_cause,
        "failure_reason_normalized_mutual_information": summarize_metric(
            [
                analysis["failure_reason_predictive_triviality"]["normalized_mutual_information"]
                for analysis in analyses
            ]
        ).model_dump(mode="json"),
    }


def write_seed_suite(report: MultiSeedReport, artifact_root: Path | None = None) -> Path:
    root = artifact_root or default_artifact_root().parent / "benchmark_suites"
    output = root / report.suite_id
    output.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    (output / "multi_seed_report.json").write_text(payload, encoding="utf-8", newline="\n")
    (output / "multi_seed_report.md").write_text(
        render_seed_suite_markdown(report), encoding="utf-8", newline="\n"
    )
    return output


def render_seed_suite_markdown(report: MultiSeedReport) -> str:
    attempt_coverage = report.environment_metrics["incident_attempt_proportion"]
    failure_coverage = report.environment_metrics["incident_failure_proportion"]
    if attempt_coverage is None or failure_coverage is None:
        raise ValueError("incident coverage is unavailable for this suite")
    quality = report.quality_aggregate
    lines = [
        "# RecoverIQ Multi-Seed Benchmark",
        "",
        f"Suite: `{report.suite_id}`  ",
        f"Group: `{report.seed_group}`  ",
        f"Seeds: `{', '.join(str(seed) for seed in report.seeds)}`  ",
        f"Total runtime: {report.total_runtime_seconds:.3f}s  ",
        f"Mean runtime/environment: {report.mean_runtime_per_environment_seconds:.3f}s",
        "",
        "## Aggregate baselines",
        "",
        "| Policy | Metric | Mean | 95% CI | Min | Max |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for policy, metrics in report.policy_metrics.items():
        for metric, summary in metrics.items():
            lines.append(
                f"| {policy} | {metric} | {summary.mean:.6g} | "
                f"[{summary.confidence_interval_95_low:.6g}, "
                f"{summary.confidence_interval_95_high:.6g}] | "
                f"{summary.minimum:.6g} | {summary.maximum:.6g} |"
            )
    lines.extend(
        [
            "",
            "## Incident coverage",
            "",
            f"Severity counts: `{report.incident_severity_counts}`  ",
            f"Duration mean: {report.incident_duration_hours.mean:.3f}h  ",
            f"Attempt coverage mean: {attempt_coverage.mean:.2%}  ",
            f"Failure coverage mean: {failure_coverage.mean:.2%}",
            "",
            "## Data quality",
            "",
            f"Payment methods: `{quality['payment_method_counts_total']}`  ",
            f"Issuers: `{quality['issuer_counts_total']}`  ",
            f"Hidden failure families: `{quality['hidden_failure_family_counts_total']}`  ",
            f"Missing-data rates: `{quality['missing_data_rate_means']}`",
            "",
            "## Nudge effect by hidden failure family",
            "",
            "| Cause | Exposed | Direct rate | Final recovery lift |",
            "|---|---:|---:|---:|",
            *(
                f"| {cause} | {summary['exposed']} | "
                f"{summary['direct_nudge_recovery_rate']:.2%} | "
                f"{summary['final_recovery_lift']:.2%} |"
                for cause, summary in quality["nudge_effect_by_hidden_failure_family"].items()
            ),
            "",
            "Confidence intervals use the normal 1.96 x sample standard error interval.",
            "All financial values are synthetic minor INR units.",
        ]
    )
    return "\n".join(lines) + "\n"
