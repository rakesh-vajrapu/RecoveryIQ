from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from recoveriq_detector import DETECTOR_VERSION
from recoveriq_detector.config import ELIGIBILITY_RULE, DetectorConfig


def detector_artifact_root() -> Path:
    return Path(__file__).resolve().parents[2] / "artifacts" / "detector"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_frozen_config(path: Path, config: DetectorConfig) -> None:
    write_json(
        path,
        {
            "artifact_type": "frozen_degradation_detector_configuration",
            "detector_version": DETECTOR_VERSION,
            "configuration_hash": config.configuration_hash,
            "eligibility_rule_evaluation_only": ELIGIBILITY_RULE.model_dump(mode="json"),
            "detector_config": config.model_dump(mode="json"),
            "validation_must_load_this_artifact": True,
        },
    )


def load_frozen_config(path: Path) -> DetectorConfig:
    value = json.loads(path.read_text(encoding="utf-8"))
    config = DetectorConfig.model_validate(value["detector_config"])
    if value["configuration_hash"] != config.configuration_hash:
        raise ValueError("frozen detector configuration hash mismatch")
    return config


def render_evaluation_markdown(title: str, report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    delays = metrics["detection_delay_minutes"]
    lines = [
        f"# {title}",
        "",
        f"Detector version: `{DETECTOR_VERSION}`",
        f"Configuration hash: `{report['configuration_hash']}`",
        "",
        "## Episode metrics",
        "",
        f"- Hidden incidents: {metrics['all_incident_count']}",
        f"- Eligible incidents: {metrics['eligible_incident_count']}",
        f"- All incident recall: {_percent(metrics['all_incident_recall'])}",
        f"- Eligible incident recall: {_percent(metrics['eligible_incident_recall'])}",
        f"- Predicted incident precision: {_percent(metrics['predicted_incident_precision'])}",
        f"- False issuer incidents: {metrics['false_positive_incident_count']}",
        f"- False incidents per scope-day: {metrics['false_incidents_per_scope_day']:.6f}",
        f"- Mean detection delay: {_number(delays['mean'])} minutes",
        f"- Median detection delay: {_number(delays['median'])} minutes",
        f"- P90 detection delay: {_number(delays['p90'])} minutes",
        "",
        "## Baseline comparison",
        "",
    ]
    for name, baseline in sorted(report["baseline_detector_comparison"].items()):
        lines.append(
            f"- {name}: eligible recall {_percent(baseline['eligible_incident_recall'])}; "
            f"precision {_percent(baseline['predicted_incident_precision'])}; false incidents "
            f"per scope-day {baseline['false_incidents_per_scope_day']:.6f}."
        )
    lines.extend(
        (
            "",
            "## Diagnostics and performance",
            "",
            f"- False-positive causes: {metrics['false_positive_causes']}",
            f"- Recall by hidden severity: {metrics['recall_by_hidden_severity']}",
            f"- Recall by traffic volume: {metrics['recall_by_traffic_volume']}",
            f"- Dominant failure shift: {metrics['dominant_failure_shift']}",
            f"- Throughput: {report['throughput_events_per_second']:.2f} events/second",
            f"- Mean update latency: {report['mean_update_latency_ms']:.4f} ms",
            "",
            "All values are simulator evaluation evidence. Hidden incident truth was joined "
            "only after observable replay completed.",
        )
    )
    return "\n".join(lines)


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.2f}%"


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")
