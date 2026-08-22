from __future__ import annotations

import hashlib
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from recoveriq_detector.config import DetectorConfig
from recoveriq_detector.models import (
    DetectorScope,
    HealthStatus,
    IncidentTransition,
    PredictedIncident,
    PredictedSeverity,
    ScopeLevel,
)
from recoveriq_detector.replay import observable_detector_event
from recoveriq_simulator.ground_truth import GeneratedScenario


class BaselineKind(StrEnum):
    STATIC_THRESHOLD = "STATIC_THRESHOLD"
    RELATIVE_DROP = "RELATIVE_DROP"


@dataclass(slots=True)
class _History:
    timestamps: list[datetime] = field(default_factory=list)
    prefix: list[int] = field(default_factory=lambda: [0])

    def append(self, timestamp: datetime, success: bool) -> None:
        self.timestamps.append(timestamp)
        self.prefix.append(self.prefix[-1] + int(success))

    def counts(self, start: datetime, end: datetime) -> tuple[int, int]:
        left = bisect_left(self.timestamps, start)
        right = bisect_right(self.timestamps, end)
        return right - left, self.prefix[right] - self.prefix[left]


@dataclass(slots=True)
class _OpenEpisode:
    detected_at: datetime
    baseline_rate: float
    current_rate: float
    recovery_count: int = 0


def replay_baseline(
    scenario: GeneratedScenario,
    config: DetectorConfig,
    kind: BaselineKind,
) -> tuple[PredictedIncident, ...]:
    histories: dict[str, _History] = {}
    active: dict[str, _OpenEpisode] = {}
    completed: list[PredictedIncident] = []
    scopes: dict[str, DetectorScope] = {}
    events = sorted(
        scenario.public.observable_events,
        key=lambda event: (event.observed_at, event.event_id),
    )
    for source in events:
        event = observable_detector_event(source)
        if event.issuer is None:
            continue
        scope = DetectorScope(
            level=ScopeLevel.ISSUER,
            payment_method=event.payment_method,
            issuer=event.issuer,
        )
        scopes[scope.key] = scope
        history = histories.setdefault(scope.key, _History())
        history.append(event.timestamp, event.success)
        current_attempts, current_successes = history.counts(
            event.timestamp - timedelta(minutes=max(config.windows_minutes)),
            event.timestamp,
        )
        baseline_attempts, baseline_successes = history.counts(
            event.timestamp - timedelta(days=config.baseline_lookback_days),
            event.timestamp - timedelta(minutes=config.baseline_exclusion_minutes),
        )
        if current_attempts < config.min_current_attempts:
            continue
        current_rate = current_successes / current_attempts
        baseline_rate = baseline_successes / baseline_attempts if baseline_attempts else 0.88
        degraded = (
            current_rate < config.static_success_threshold
            if kind is BaselineKind.STATIC_THRESHOLD
            else (
                baseline_attempts >= config.min_baseline_attempts
                and baseline_rate - current_rate >= config.relative_drop_threshold
            )
        )
        episode = active.get(scope.key)
        if degraded:
            if episode is None:
                active[scope.key] = _OpenEpisode(
                    detected_at=event.timestamp,
                    baseline_rate=baseline_rate,
                    current_rate=current_rate,
                )
            else:
                episode.current_rate = current_rate
                episode.recovery_count = 0
        elif episode is not None:
            episode.recovery_count += 1
            if episode.recovery_count >= config.recovery_persistence:
                completed.append(_freeze_baseline_episode(kind, scope, episode, event.timestamp))
                active.pop(scope.key)
    for key, episode in active.items():
        completed.append(_freeze_baseline_episode(kind, scopes[key], episode, None))
    return tuple(sorted(completed, key=lambda item: item.detected_at))


def _freeze_baseline_episode(
    kind: BaselineKind,
    scope: DetectorScope,
    episode: _OpenEpisode,
    resolved_at: datetime | None,
) -> PredictedIncident:
    digest = hashlib.sha256(
        f"{kind.value}|{scope.key}|{episode.detected_at.isoformat()}".encode()
    ).hexdigest()[:12]
    transitions = [
        IncidentTransition(
            timestamp=episode.detected_at,
            status=HealthStatus.OPEN,
            severity=PredictedSeverity.MODERATE,
        )
    ]
    if resolved_at is not None:
        transitions.append(
            IncidentTransition(
                timestamp=resolved_at,
                status=HealthStatus.RESOLVED,
                severity=PredictedSeverity.MODERATE,
            )
        )
    return PredictedIncident(
        incident_id=f"{kind.value}-{digest}",
        scope=scope,
        opened_at=episode.detected_at,
        detected_at=episode.detected_at,
        current_severity=PredictedSeverity.MODERATE,
        baseline_attempts=0,
        current_attempts=0,
        baseline_success_rate=episode.baseline_rate,
        current_success_rate=episode.current_rate,
        posterior_degradation_probability=0.0,
        evidence_window_minutes=360,
        transitions=tuple(transitions),
        resolved_at=resolved_at,
    )
