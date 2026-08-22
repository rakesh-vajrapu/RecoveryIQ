from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from recoveriq_detector_v2 import DETECTOR_V2_VERSION
from recoveriq_detector_v2.config import (
    HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY,
    HARD_POLICY_MIN_CONFIRMED_EPISODES,
    HARD_POLICY_MIN_PRECISION,
    HIGH_EVIDENCE_RULE,
    DetectorV2Config,
)


def artifact_root_v2() -> Path:
    return Path(__file__).resolve().parents[2] / "artifacts" / "detector_v2"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=_default) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_frozen_v2_config(path: Path, config: DetectorV2Config) -> None:
    write_json(
        path,
        {
            "artifact_type": "frozen_operational_degradation_detector_v2",
            "detector_version": DETECTOR_V2_VERSION,
            "configuration_hash": config.configuration_hash,
            "config": config.model_dump(mode="json"),
            "high_evidence_rule_evaluation_only": HIGH_EVIDENCE_RULE.model_dump(mode="json"),
            "hard_policy_safety_gate": {
                "minimum_precision": HARD_POLICY_MIN_PRECISION,
                "maximum_false_confirmed_per_scope_day": HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY,
                "minimum_confirmed_episodes": HARD_POLICY_MIN_CONFIRMED_EPISODES,
            },
        },
    )


def load_frozen_v2_config(path: Path) -> DetectorV2Config:
    value = json.loads(path.read_text(encoding="utf-8"))
    config = DetectorV2Config.model_validate(value["config"])
    if value["configuration_hash"] != config.configuration_hash:
        raise ValueError("detector v2 frozen configuration hash mismatch")
    return config


def safety_gate(metrics: dict[str, Any]) -> dict[str, Any]:
    confirmed = metrics["confirmed"]
    precision = confirmed["episode_precision"]
    false_rate = confirmed["false_episodes_per_scope_day"]
    count = int(confirmed["episode_count"])
    passed = bool(
        precision is not None
        and precision >= HARD_POLICY_MIN_PRECISION
        and false_rate is not None
        and false_rate <= HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY
        and count >= HARD_POLICY_MIN_CONFIRMED_EPISODES
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "future_hard_policy_eligible": passed,
        "actual_precision": precision,
        "actual_false_confirmed_per_scope_day": false_rate,
        "actual_confirmed_episode_count": count,
        "required_precision": HARD_POLICY_MIN_PRECISION,
        "maximum_false_confirmed_per_scope_day": HARD_POLICY_MAX_FALSE_PER_SCOPE_DAY,
        "minimum_confirmed_episode_count": HARD_POLICY_MIN_CONFIRMED_EPISODES,
        "failure_behavior": "ADVISORY_ONLY",
    }


def render_report(title: str, report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        f"# {title}",
        "",
        f"Detector version: `{DETECTOR_V2_VERSION}`",
        f"Configuration hash: `{report['configuration_hash']}`",
        "",
    ]
    for tier in ("watch", "confirmed"):
        value = metrics[tier]
        delay = value["detection_delay_minutes"]
        lines.extend(
            (
                f"## {tier.upper()}",
                "",
                f"- Episodes: {value['episode_count']}",
                f"- All recall: {_percent(value['all_incident_recall'])}",
                f"- Eligible recall: {_percent(value['eligible_incident_recall'])}",
                f"- High-evidence recall: {_percent(value['high_evidence_incident_recall'])}",
                f"- Precision: {_percent(value['episode_precision'])}",
                f"- False episodes/scope-day: {_number(value['false_episodes_per_scope_day'])}",
                f"- Median delay: {_number(delay['median'])} minutes",
                f"- P90 delay: {_number(delay['p90'])} minutes",
                "",
            )
        )
    if "hard_policy_safety_gate" in report:
        lines.extend(
            (
                "## Hard-policy safety gate",
                "",
                f"**{report['hard_policy_safety_gate']['status']}**",
                "",
            )
        )
    lines.extend(
        (
            f"Throughput: {report['throughput_events_per_second']:.2f} events/second.",
            "",
            "WATCH and CONFIRMED are reported separately. Hidden truth was joined only "
            "after replay.",
        )
    )
    return "\n".join(lines)


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.2f}%"


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


def _default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")
