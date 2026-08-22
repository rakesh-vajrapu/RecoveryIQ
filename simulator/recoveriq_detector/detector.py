from __future__ import annotations

import hashlib
import math
from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from recoveriq_detector.config import DetectorConfig
from recoveriq_detector.models import (
    DetectorScope,
    FailureShift,
    HealthStatus,
    IncidentTransition,
    PaymentHealthContext,
    PaymentHealthSnapshot,
    PaymentResultEvent,
    PredictedIncident,
    PredictedSeverity,
    ScopeLevel,
    WindowEvidence,
)


@dataclass(slots=True)
class _ScopeHistory:
    timestamps: list[datetime] = field(default_factory=list)
    successes: list[int] = field(default_factory=list)
    success_prefix: list[int] = field(default_factory=lambda: [0])
    events: list[PaymentResultEvent] = field(default_factory=list)
    ewma: float | None = None

    def append(self, event: PaymentResultEvent, alpha: float) -> None:
        value = int(event.success)
        self.timestamps.append(event.timestamp)
        self.successes.append(value)
        self.success_prefix.append(self.success_prefix[-1] + value)
        self.events.append(event)
        self.ewma = float(value) if self.ewma is None else alpha * value + (1 - alpha) * self.ewma

    def counts(
        self, start: datetime, end: datetime, *, inclusive_end: bool = True
    ) -> tuple[int, int]:
        left = bisect_left(self.timestamps, start)
        right = (
            bisect_right(self.timestamps, end)
            if inclusive_end
            else bisect_left(self.timestamps, end)
        )
        return right - left, self.success_prefix[right] - self.success_prefix[left]

    def slice_events(self, start: datetime, end: datetime) -> list[PaymentResultEvent]:
        left = bisect_left(self.timestamps, start)
        right = bisect_right(self.timestamps, end)
        return self.events[left:right]


@dataclass(frozen=True, slots=True)
class _Signal:
    window: WindowEvidence
    baseline_attempts: int
    baseline_success_rate: float
    baseline_posterior_mean: float
    baseline_source: ScopeLevel
    posterior_probability: float
    rate_delta: float
    ewma_drop: float
    strong: bool
    weak: bool


@dataclass(slots=True)
class _MutableIncident:
    incident_id: str
    scope: DetectorScope
    opened_at: datetime
    detected_at: datetime
    current_severity: PredictedSeverity
    baseline_attempts: int
    current_attempts: int
    baseline_success_rate: float
    current_success_rate: float
    posterior_probability: float
    evidence_window_minutes: int
    shifts: tuple[FailureShift, ...]
    transitions: list[IncidentTransition]
    resolved_at: datetime | None = None

    def frozen(self) -> PredictedIncident:
        return PredictedIncident(
            incident_id=self.incident_id,
            scope=self.scope,
            opened_at=self.opened_at,
            detected_at=self.detected_at,
            current_severity=self.current_severity,
            baseline_attempts=self.baseline_attempts,
            current_attempts=self.current_attempts,
            baseline_success_rate=self.baseline_success_rate,
            current_success_rate=self.current_success_rate,
            posterior_degradation_probability=self.posterior_probability,
            evidence_window_minutes=self.evidence_window_minutes,
            dominant_failure_shifts=self.shifts,
            transitions=tuple(self.transitions),
            resolved_at=self.resolved_at,
        )


@dataclass(slots=True)
class _Lifecycle:
    phase: HealthStatus = HealthStatus.HEALTHY
    suspected_at: datetime | None = None
    strong_count: int = 0
    recovery_count: int = 0
    sequence: int = 0
    active: _MutableIncident | None = None


class PaymentDegradationDetector:
    """Deterministic online detector whose public update accepts observable events only."""

    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self._histories: dict[str, _ScopeHistory] = {}
        self._scopes: dict[str, DetectorScope] = {}
        self._lifecycles: dict[str, _Lifecycle] = {}
        self._latest: dict[str, PaymentHealthSnapshot] = {}
        self._completed: list[PredictedIncident] = []
        self._last_timestamp: datetime | None = None
        self._seen_event_ids: set[str] = set()

    def update(self, event: PaymentResultEvent) -> tuple[PaymentHealthSnapshot, ...]:
        if event.event_id in self._seen_event_ids:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        if self._last_timestamp is not None and event.timestamp < self._last_timestamp:
            raise ValueError("events must be processed in nondecreasing timestamp order")
        self._seen_event_ids.add(event.event_id)
        self._last_timestamp = event.timestamp

        scopes = self._event_scopes(event)
        for scope in scopes:
            history = self._history(scope)
            history.append(event, self.config.ewma_alpha)

        snapshots: list[PaymentHealthSnapshot] = []
        for scope in scopes:
            snapshot = self._evaluate(scope, event.timestamp)
            self._latest[scope.key] = snapshot
            snapshots.append(snapshot)
        return tuple(snapshots)

    def get_health_context(
        self,
        timestamp: datetime,
        payment_method: str,
        issuer: str | None,
    ) -> PaymentHealthContext:
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("historical context queries require a replay/checkpoint store")
        issuer_scope = (
            DetectorScope(
                level=ScopeLevel.ISSUER,
                payment_method=payment_method,
                issuer=issuer,
            )
            if issuer is not None
            else None
        )
        method_scope = DetectorScope(
            level=ScopeLevel.PAYMENT_METHOD,
            payment_method=payment_method,
        )
        global_scope = DetectorScope(level=ScopeLevel.GLOBAL)
        return PaymentHealthContext(
            timestamp=timestamp,
            requested_payment_method=payment_method,
            requested_issuer=issuer,
            issuer_health=self._latest.get(issuer_scope.key) if issuer_scope else None,
            method_health=self._latest.get(method_scope.key),
            global_health=self._latest.get(global_scope.key),
        )

    @property
    def predicted_incidents(self) -> tuple[PredictedIncident, ...]:
        active = [
            lifecycle.active.frozen()
            for lifecycle in self._lifecycles.values()
            if lifecycle.active is not None
        ]
        return tuple(sorted((*self._completed, *active), key=lambda item: item.detected_at))

    @property
    def latest_snapshots(self) -> tuple[PaymentHealthSnapshot, ...]:
        return tuple(sorted(self._latest.values(), key=lambda item: item.scope.key))

    def _event_scopes(self, event: PaymentResultEvent) -> tuple[DetectorScope, ...]:
        scopes = [
            DetectorScope(level=ScopeLevel.GLOBAL),
            DetectorScope(level=ScopeLevel.PAYMENT_METHOD, payment_method=event.payment_method),
        ]
        if event.issuer is not None:
            scopes.append(
                DetectorScope(
                    level=ScopeLevel.ISSUER,
                    payment_method=event.payment_method,
                    issuer=event.issuer,
                )
            )
        return tuple(scopes)

    def _history(self, scope: DetectorScope) -> _ScopeHistory:
        self._scopes[scope.key] = scope
        return self._histories.setdefault(scope.key, _ScopeHistory())

    def _evaluate(self, scope: DetectorScope, timestamp: datetime) -> PaymentHealthSnapshot:
        history = self._history(scope)
        windows = tuple(
            self._window_evidence(history, timestamp, minutes)
            for minutes in self.config.windows_minutes
        )
        signal = self._best_signal(scope, timestamp, windows)
        lifecycle = self._lifecycles.setdefault(scope.key, _Lifecycle())
        shifts: tuple[FailureShift, ...] = ()
        severity: PredictedSeverity | None = None
        if signal is not None:
            severity = self._severity(signal)
            opening_now = signal.strong and (
                (
                    lifecycle.phase is HealthStatus.SUSPECTED
                    and lifecycle.strong_count + 1 >= self.config.open_persistence
                )
                or (
                    lifecycle.phase in {HealthStatus.HEALTHY, HealthStatus.RESOLVED}
                    and self.config.open_persistence == 1
                )
            )
            if lifecycle.active is not None or opening_now:
                shifts = self._failure_shifts(
                    scope,
                    timestamp,
                    signal.window.window_minutes,
                )
        status = self._advance_lifecycle(scope, timestamp, lifecycle, signal, severity, shifts)

        selected = signal.window if signal is not None else None
        current_rate = selected.success_rate if selected is not None else None
        baseline_rate = signal.baseline_success_rate if signal is not None else None
        health_score = None
        if current_rate is not None and baseline_rate is not None:
            health_score = max(0.0, min(100.0, 100.0 * current_rate / max(baseline_rate, 0.01)))
        active_id = lifecycle.active.incident_id if lifecycle.active is not None else None
        return PaymentHealthSnapshot(
            scope=scope,
            timestamp=timestamp,
            windows=windows,
            historical_attempts=signal.baseline_attempts if signal else 0,
            historical_success_rate=baseline_rate,
            historical_posterior_mean=signal.baseline_posterior_mean if signal else None,
            baseline_source=signal.baseline_source if signal else None,
            rate_delta=signal.rate_delta if signal else None,
            posterior_degradation_probability=signal.posterior_probability if signal else None,
            ewma_success_rate=history.ewma,
            ewma_drop=signal.ewma_drop if signal else None,
            health_score=health_score,
            status=status,
            severity=severity
            if status in {HealthStatus.SUSPECTED, HealthStatus.OPEN, HealthStatus.RECOVERING}
            else None,
            dominant_failure_shifts=shifts
            if status in {HealthStatus.OPEN, HealthStatus.RECOVERING}
            else (),
            active_incident_id=active_id,
            selected_window_minutes=selected.window_minutes if selected else None,
        )

    def _window_evidence(
        self, history: _ScopeHistory, timestamp: datetime, minutes: int
    ) -> WindowEvidence:
        attempts, successes = history.counts(timestamp - timedelta(minutes=minutes), timestamp)
        rate = successes / attempts if attempts else None
        posterior = None
        if attempts:
            posterior = (successes + self.config.beta_prior_strength * 0.88) / (
                attempts + self.config.beta_prior_strength
            )
        return WindowEvidence(
            window_minutes=minutes,
            attempts=attempts,
            successes=successes,
            success_rate=rate,
            posterior_mean=posterior,
        )

    def _baseline_candidates(
        self, scope: DetectorScope
    ) -> tuple[tuple[ScopeLevel, _ScopeHistory], ...]:
        candidates = [(scope.level, self._history(scope))]
        if scope.level is ScopeLevel.ISSUER:
            method = DetectorScope(
                level=ScopeLevel.PAYMENT_METHOD,
                payment_method=scope.payment_method,
            )
            candidates.append((ScopeLevel.PAYMENT_METHOD, self._history(method)))
        if scope.level is not ScopeLevel.GLOBAL:
            candidates.append(
                (ScopeLevel.GLOBAL, self._history(DetectorScope(level=ScopeLevel.GLOBAL)))
            )
        return tuple(candidates)

    def _baseline(
        self, scope: DetectorScope, timestamp: datetime
    ) -> tuple[int, int, ScopeLevel] | None:
        start = timestamp - timedelta(days=self.config.baseline_lookback_days)
        end = timestamp - timedelta(minutes=self.config.baseline_exclusion_minutes)
        for level, history in self._baseline_candidates(scope):
            attempts, successes = history.counts(start, end, inclusive_end=False)
            if attempts >= self.config.min_baseline_attempts:
                return attempts, successes, level
        return None

    def _best_signal(
        self,
        scope: DetectorScope,
        timestamp: datetime,
        windows: tuple[WindowEvidence, ...],
    ) -> _Signal | None:
        baseline = self._baseline(scope, timestamp)
        if baseline is None:
            return None
        baseline_attempts, baseline_successes, baseline_source = baseline
        prior_mean = 0.88
        prior_strength = self.config.beta_prior_strength
        baseline_alpha = baseline_successes + prior_strength * prior_mean
        baseline_beta = baseline_attempts - baseline_successes + prior_strength * (1 - prior_mean)
        baseline_mean, baseline_var = _beta_mean_variance(baseline_alpha, baseline_beta)
        history = self._history(scope)
        if history.ewma is None:
            return None

        provisional: list[_Signal] = []
        minimum_current_attempts = self._minimum_current_attempts(scope)
        for window in windows:
            if window.attempts < minimum_current_attempts or window.success_rate is None:
                continue
            current_alpha = (
                window.successes + self.config.hierarchical_prior_strength * baseline_mean
            )
            current_beta = (
                window.attempts
                - window.successes
                + self.config.hierarchical_prior_strength * (1 - baseline_mean)
            )
            current_mean, current_var = _beta_mean_variance(current_alpha, current_beta)
            variance = max(current_var + baseline_var, 1e-12)
            z_score = (baseline_mean - self.config.meaningful_drop - current_mean) / math.sqrt(
                variance
            )
            probability = _normal_cdf(z_score)
            rate_delta = baseline_mean - current_mean
            ewma_drop = baseline_mean - history.ewma
            provisional.append(
                _Signal(
                    window=window.model_copy(update={"posterior_mean": current_mean}),
                    baseline_attempts=baseline_attempts,
                    baseline_success_rate=baseline_successes / baseline_attempts,
                    baseline_posterior_mean=baseline_mean,
                    baseline_source=baseline_source,
                    posterior_probability=probability,
                    rate_delta=rate_delta,
                    ewma_drop=ewma_drop,
                    strong=False,
                    weak=(
                        probability >= self.config.posterior_suspect_probability
                        and rate_delta >= self.config.meaningful_drop * 0.70
                        and ewma_drop >= self.config.ewma_drop_threshold * 0.50
                    ),
                )
            )
        if not provisional:
            return None

        qualifying = [
            item
            for item in provisional
            if item.posterior_probability >= self.config.posterior_open_probability
            and item.rate_delta >= self.config.meaningful_drop
            and item.ewma_drop >= self.config.ewma_drop_threshold
        ]
        selected = max(
            provisional,
            key=lambda item: (
                item.posterior_probability,
                item.rate_delta,
                -item.window.window_minutes,
            ),
        )
        corroborated = len(qualifying) >= 2
        high_volume = selected.window.attempts >= 2 * minimum_current_attempts
        overwhelming = (
            selected.posterior_probability >= 0.995
            and selected.rate_delta >= 1.5 * self.config.meaningful_drop
        )
        return _Signal(
            window=selected.window,
            baseline_attempts=selected.baseline_attempts,
            baseline_success_rate=selected.baseline_success_rate,
            baseline_posterior_mean=selected.baseline_posterior_mean,
            baseline_source=selected.baseline_source,
            posterior_probability=selected.posterior_probability,
            rate_delta=selected.rate_delta,
            ewma_drop=selected.ewma_drop,
            strong=bool(qualifying) and (corroborated or high_volume or overwhelming),
            weak=selected.weak or bool(qualifying),
        )

    def _advance_lifecycle(
        self,
        scope: DetectorScope,
        timestamp: datetime,
        lifecycle: _Lifecycle,
        signal: _Signal | None,
        severity: PredictedSeverity | None,
        shifts: tuple[FailureShift, ...],
    ) -> HealthStatus:
        if signal is None:
            return (
                lifecycle.phase
                if lifecycle.active is not None
                else HealthStatus.INSUFFICIENT_EVIDENCE
            )
        if signal.strong:
            lifecycle.recovery_count = 0
            if lifecycle.phase in {HealthStatus.HEALTHY, HealthStatus.RESOLVED}:
                lifecycle.phase = HealthStatus.SUSPECTED
                lifecycle.suspected_at = timestamp
                lifecycle.strong_count = 1
            elif lifecycle.phase is HealthStatus.SUSPECTED:
                lifecycle.strong_count += 1
            elif lifecycle.phase is HealthStatus.RECOVERING:
                lifecycle.phase = HealthStatus.OPEN
                self._transition(lifecycle, timestamp, HealthStatus.OPEN, severity)
            if (
                lifecycle.phase is HealthStatus.SUSPECTED
                and lifecycle.strong_count >= self.config.open_persistence
            ):
                self._open(scope, timestamp, lifecycle, signal, severity, shifts)
            elif lifecycle.active is not None:
                self._update_active(lifecycle.active, signal, severity, shifts, timestamp)
            return lifecycle.phase

        if signal.weak:
            lifecycle.strong_count = 0
            if lifecycle.phase in {HealthStatus.HEALTHY, HealthStatus.RESOLVED}:
                lifecycle.phase = HealthStatus.SUSPECTED
                lifecycle.suspected_at = timestamp
            elif lifecycle.phase is HealthStatus.RECOVERING:
                lifecycle.phase = HealthStatus.OPEN
                lifecycle.recovery_count = 0
                self._transition(lifecycle, timestamp, HealthStatus.OPEN, severity)
            if lifecycle.active is not None:
                self._update_active(lifecycle.active, signal, severity, shifts, timestamp)
            return lifecycle.phase

        recovered = (
            signal.rate_delta <= self.config.recovery_drop
            and signal.ewma_drop <= self.config.ewma_drop_threshold * 0.50
            and signal.posterior_probability < self.config.posterior_suspect_probability
        )
        if not recovered:
            return lifecycle.phase

        lifecycle.strong_count = 0
        if lifecycle.phase is HealthStatus.SUSPECTED:
            lifecycle.phase = HealthStatus.HEALTHY
            lifecycle.suspected_at = None
        elif lifecycle.phase is HealthStatus.OPEN:
            lifecycle.phase = HealthStatus.RECOVERING
            lifecycle.recovery_count = 1
            self._transition(lifecycle, timestamp, HealthStatus.RECOVERING, severity)
        elif lifecycle.phase is HealthStatus.RECOVERING:
            lifecycle.recovery_count += 1
            if lifecycle.recovery_count >= self.config.recovery_persistence:
                self._resolve(lifecycle, timestamp)
        elif lifecycle.phase is HealthStatus.RESOLVED:
            lifecycle.phase = HealthStatus.HEALTHY
        return lifecycle.phase

    def _open(
        self,
        scope: DetectorScope,
        timestamp: datetime,
        lifecycle: _Lifecycle,
        signal: _Signal,
        severity: PredictedSeverity | None,
        shifts: tuple[FailureShift, ...],
    ) -> None:
        lifecycle.sequence += 1
        predicted_severity = severity or PredictedSeverity.MILD
        opened_at = lifecycle.suspected_at or timestamp
        digest = hashlib.sha256(
            f"{scope.key}|{opened_at.isoformat()}|{lifecycle.sequence}".encode()
        ).hexdigest()[:12]
        lifecycle.active = _MutableIncident(
            incident_id=f"DEG-{digest}",
            scope=scope,
            opened_at=opened_at,
            detected_at=timestamp,
            current_severity=predicted_severity,
            baseline_attempts=signal.baseline_attempts,
            current_attempts=signal.window.attempts,
            baseline_success_rate=signal.baseline_success_rate,
            current_success_rate=signal.window.success_rate or 0.0,
            posterior_probability=signal.posterior_probability,
            evidence_window_minutes=signal.window.window_minutes,
            shifts=shifts,
            transitions=[
                IncidentTransition(
                    timestamp=opened_at, status=HealthStatus.SUSPECTED, severity=predicted_severity
                ),
                IncidentTransition(
                    timestamp=timestamp, status=HealthStatus.OPEN, severity=predicted_severity
                ),
            ],
        )
        lifecycle.phase = HealthStatus.OPEN
        lifecycle.strong_count = 0

    def _update_active(
        self,
        active: _MutableIncident,
        signal: _Signal,
        severity: PredictedSeverity | None,
        shifts: tuple[FailureShift, ...],
        timestamp: datetime,
    ) -> None:
        next_severity = severity or active.current_severity
        if next_severity != active.current_severity:
            active.transitions.append(
                IncidentTransition(
                    timestamp=timestamp, status=HealthStatus.OPEN, severity=next_severity
                )
            )
        active.current_severity = next_severity
        active.baseline_attempts = signal.baseline_attempts
        active.current_attempts = signal.window.attempts
        active.baseline_success_rate = signal.baseline_success_rate
        active.current_success_rate = signal.window.success_rate or 0.0
        active.posterior_probability = signal.posterior_probability
        active.evidence_window_minutes = signal.window.window_minutes
        if shifts:
            active.shifts = shifts

    def _transition(
        self,
        lifecycle: _Lifecycle,
        timestamp: datetime,
        status: HealthStatus,
        severity: PredictedSeverity | None,
    ) -> None:
        if lifecycle.active is not None:
            lifecycle.active.transitions.append(
                IncidentTransition(timestamp=timestamp, status=status, severity=severity)
            )

    def _resolve(self, lifecycle: _Lifecycle, timestamp: datetime) -> None:
        if lifecycle.active is None:
            return
        lifecycle.active.resolved_at = timestamp
        lifecycle.active.transitions.append(
            IncidentTransition(
                timestamp=timestamp,
                status=HealthStatus.RESOLVED,
                severity=lifecycle.active.current_severity,
            )
        )
        self._completed.append(lifecycle.active.frozen())
        lifecycle.active = None
        lifecycle.phase = HealthStatus.RESOLVED
        lifecycle.recovery_count = 0
        lifecycle.suspected_at = None

    def _severity(self, signal: _Signal) -> PredictedSeverity:
        attempts = signal.window.attempts
        drop = signal.rate_delta
        probability = signal.posterior_probability
        if drop >= 0.40 and attempts >= 20 and probability >= 0.95:
            return PredictedSeverity.CRITICAL
        if drop >= 0.25 and attempts >= 12 and probability >= 0.90:
            return PredictedSeverity.SEVERE
        if drop >= 0.12 and attempts >= 8 and probability >= 0.80:
            return PredictedSeverity.MODERATE
        return PredictedSeverity.MILD

    def _minimum_current_attempts(self, scope: DetectorScope) -> int:
        if scope.level is ScopeLevel.PAYMENT_METHOD:
            return max(20, 3 * self.config.min_current_attempts)
        if scope.level is ScopeLevel.GLOBAL:
            return max(50, 8 * self.config.min_current_attempts)
        return self.config.min_current_attempts

    def _failure_shifts(
        self, scope: DetectorScope, timestamp: datetime, window_minutes: int
    ) -> tuple[FailureShift, ...]:
        history = self._history(scope)
        current = history.slice_events(timestamp - timedelta(minutes=window_minutes), timestamp)
        baseline = history.slice_events(
            timestamp - timedelta(days=self.config.baseline_lookback_days),
            timestamp - timedelta(minutes=self.config.baseline_exclusion_minutes),
        )
        current_failures = [
            event for event in current if not event.success and event.failure_reason
        ]
        baseline_failures = [
            event for event in baseline if not event.success and event.failure_reason
        ]
        if (
            len(current_failures) < self.config.dominant_reason_min_failures
            or len(baseline_failures) < self.config.dominant_reason_min_failures
        ):
            return ()
        current_counts = Counter(event.failure_reason for event in current_failures)
        baseline_counts = Counter(event.failure_reason for event in baseline_failures)
        shifts: list[FailureShift] = []
        for reason, support in current_counts.items():
            if reason is None or support < self.config.dominant_reason_min_support:
                continue
            current_share = support / len(current_failures)
            baseline_share = baseline_counts[reason] / len(baseline_failures)
            absolute_change = current_share - baseline_share
            if absolute_change <= 0:
                continue
            shifts.append(
                FailureShift(
                    reason=reason,
                    current_share=current_share,
                    baseline_share=baseline_share,
                    absolute_change=absolute_change,
                    relative_lift=current_share / baseline_share if baseline_share else None,
                    support_count=support,
                )
            )
        shifts.sort(key=lambda item: (item.absolute_change, item.support_count), reverse=True)
        return tuple(shifts[:3])


def _beta_mean_variance(alpha: float, beta: float) -> tuple[float, float]:
    total = alpha + beta
    mean = alpha / total
    variance = alpha * beta / (total * total * (total + 1))
    return mean, variance


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))
