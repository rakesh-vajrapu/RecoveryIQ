from __future__ import annotations

import hashlib
import math
from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from recoveriq_detector_v2.config import DetectorV2Config
from recoveriq_detector_v2.models import (
    DegradationEpisodeV2,
    DetectorScope,
    EvidenceLevel,
    EvidenceTransition,
    FailureDistributionEvidence,
    HealthSnapshotV2,
    ObservableSeverity,
    ParentCorroboration,
    PaymentHealthContextV2,
    PaymentResultEvent,
    PolicyEvidenceRole,
    ReasonShift,
    ScopeLevel,
    SequentialEvidence,
    SequentialHypothesis,
    WindowHealth,
)


@dataclass(slots=True)
class _History:
    timestamps: list[datetime] = field(default_factory=list)
    prefix_successes: list[int] = field(default_factory=lambda: [0])
    events: list[PaymentResultEvent] = field(default_factory=list)

    def append(self, event: PaymentResultEvent) -> None:
        self.timestamps.append(event.timestamp)
        self.prefix_successes.append(self.prefix_successes[-1] + int(event.success))
        self.events.append(event)

    def counts(self, start: datetime, end: datetime) -> tuple[int, int]:
        left = bisect_left(self.timestamps, start)
        right = bisect_right(self.timestamps, end)
        return right - left, self.prefix_successes[right] - self.prefix_successes[left]

    def events_between(self, start: datetime, end: datetime) -> list[PaymentResultEvent]:
        left = bisect_left(self.timestamps, start)
        right = bisect_right(self.timestamps, end)
        return self.events[left:right]


@dataclass(frozen=True, slots=True)
class _Baseline:
    probability: float
    attempts: int
    source: ScopeLevel


@dataclass(slots=True)
class _MutableEpisode:
    incident_id: str
    scope: DetectorScope
    watch_at: datetime
    baseline_probability: float
    baseline_attempts: int
    transitions: list[EvidenceTransition]
    confirmed_at: datetime | None = None
    resolved_at: datetime | None = None
    dissipated: bool = False
    maximum_llr: float = 0.0
    current_attempts: int = 0
    current_failures: int = 0
    severity: ObservableSeverity = ObservableSeverity.MILD
    failure_evidence: FailureDistributionEvidence = field(
        default_factory=lambda: _empty_failure_evidence()
    )
    parent: ParentCorroboration = field(default_factory=ParentCorroboration)
    confirmation_rule: str | None = None

    def frozen(self) -> DegradationEpisodeV2:
        return DegradationEpisodeV2(
            incident_id=self.incident_id,
            scope=self.scope,
            watch_at=self.watch_at,
            confirmed_at=self.confirmed_at,
            resolved_at=self.resolved_at,
            dissipated_without_confirmation=self.dissipated,
            baseline_success_probability=self.baseline_probability,
            baseline_attempts=self.baseline_attempts,
            maximum_llr=self.maximum_llr,
            current_attempts=self.current_attempts,
            current_failures=self.current_failures,
            current_severity=self.severity,
            failure_distribution=self.failure_evidence,
            parent_corroboration=self.parent,
            confirmation_rule=self.confirmation_rule,
            transitions=tuple(self.transitions),
        )


@dataclass(slots=True)
class _State:
    level: EvidenceLevel = EvidenceLevel.HEALTHY
    llrs: list[float] = field(default_factory=list)
    monitoring_events: int = 0
    frozen_baseline: _Baseline | None = None
    frozen_reason_counts: Counter[str] = field(default_factory=Counter)
    current_reason_counts: Counter[str] = field(default_factory=Counter)
    current_failures: int = 0
    events_since_watch: int = 0
    watch_release_successes: int = 0
    recovery_llr: float = 0.0
    recovery_events: int = 0
    active: _MutableEpisode | None = None
    last_confirmed_at: datetime | None = None


class OperationalDegradationDetectorV2:
    """Observable-only event-driven detector with advisory and confirmed evidence tiers."""

    def __init__(self, config: DetectorV2Config) -> None:
        self.config = config
        self._histories: dict[str, _History] = {}
        self._scopes: dict[str, DetectorScope] = {}
        self._states: dict[str, _State] = {}
        self._latest: dict[str, HealthSnapshotV2] = {}
        self._completed: list[DegradationEpisodeV2] = []
        self._seen_ids: set[str] = set()
        self._last_timestamp: datetime | None = None

    def update(self, event: PaymentResultEvent) -> tuple[HealthSnapshotV2, ...]:
        if event.event_id in self._seen_ids:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        if self._last_timestamp is not None and event.timestamp < self._last_timestamp:
            raise ValueError("events must be processed in nondecreasing timestamp order")
        self._seen_ids.add(event.event_id)
        self._last_timestamp = event.timestamp

        scopes = self._event_scopes(event)
        baselines = {scope.key: self._estimate_baseline(scope, event.timestamp) for scope in scopes}
        for scope in scopes:
            self._history(scope).append(event)

        snapshots: list[HealthSnapshotV2] = []
        for scope in scopes:
            snapshot = self._process(scope, event, baselines[scope.key])
            self._latest[scope.key] = snapshot
            snapshots.append(snapshot)
        return tuple(snapshots)

    @property
    def episodes(self) -> tuple[DegradationEpisodeV2, ...]:
        active = [
            state.active.frozen() for state in self._states.values() if state.active is not None
        ]
        return tuple(sorted((*self._completed, *active), key=lambda item: item.watch_at))

    @property
    def latest_snapshots(self) -> tuple[HealthSnapshotV2, ...]:
        return tuple(sorted(self._latest.values(), key=lambda item: item.scope.key))

    def get_health_context(
        self,
        timestamp: datetime,
        payment_method: str,
        issuer: str | None,
    ) -> PaymentHealthContextV2:
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("historical context requires a persisted replay checkpoint")
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
        return PaymentHealthContextV2(
            timestamp=timestamp,
            requested_payment_method=payment_method,
            requested_issuer=issuer,
            issuer_health=self._latest.get(issuer_scope.key) if issuer_scope else None,
            method_health=self._latest.get(method_scope.key),
            global_health=self._latest.get(global_scope.key),
            confirmed_hard_policy_gate_passed=False,
        )

    def _event_scopes(self, event: PaymentResultEvent) -> tuple[DetectorScope, ...]:
        scopes = [
            self._scope(ScopeLevel.GLOBAL),
            self._scope(ScopeLevel.PAYMENT_METHOD, event.payment_method),
        ]
        if event.issuer is not None:
            scopes.append(self._scope(ScopeLevel.ISSUER, event.payment_method, event.issuer))
        return tuple(scopes)

    def _scope(
        self,
        level: ScopeLevel,
        payment_method: str | None = None,
        issuer: str | None = None,
    ) -> DetectorScope:
        if level is ScopeLevel.GLOBAL:
            key = "GLOBAL"
        elif level is ScopeLevel.PAYMENT_METHOD:
            key = f"METHOD:{payment_method}"
        else:
            key = f"ISSUER:{payment_method}:{issuer}"
        existing = self._scopes.get(key)
        if existing is not None:
            return existing
        scope = DetectorScope(level=level, payment_method=payment_method, issuer=issuer)
        self._scopes[key] = scope
        return scope

    def _history(self, scope: DetectorScope) -> _History:
        return self._histories.setdefault(scope.key, _History())

    def _state(self, scope: DetectorScope) -> _State:
        state = self._states.setdefault(scope.key, _State())
        if not state.llrs:
            state.llrs = [0.0] * len(self.config.drop_hypotheses)
        return state

    def _estimate_baseline(self, scope: DetectorScope, timestamp: datetime) -> _Baseline | None:
        start = timestamp - timedelta(days=self.config.baseline_lookback_days)
        own_attempts, own_successes = self._history(scope).counts(start, timestamp)
        parent = self._parent_baseline(scope, start, timestamp)
        if own_attempts >= self.config.min_baseline_attempts:
            prior_mean = (
                parent.probability
                if parent is not None
                else self.config.default_success_probability
            )
            probability = (own_successes + self.config.baseline_prior_strength * prior_mean) / (
                own_attempts + self.config.baseline_prior_strength
            )
            return _Baseline(
                probability=self._bound_probability(probability),
                attempts=own_attempts,
                source=scope.level,
            )
        return parent

    def _parent_baseline(
        self,
        scope: DetectorScope,
        start: datetime,
        timestamp: datetime,
    ) -> _Baseline | None:
        parents: list[DetectorScope] = []
        if scope.level is ScopeLevel.ISSUER:
            parents.append(self._scope(ScopeLevel.PAYMENT_METHOD, scope.payment_method))
        if scope.level is not ScopeLevel.GLOBAL:
            parents.append(self._scope(ScopeLevel.GLOBAL))
        for parent in parents:
            attempts, successes = self._history(parent).counts(start, timestamp)
            if attempts >= self.config.min_baseline_attempts:
                probability = (
                    successes
                    + self.config.baseline_prior_strength * self.config.default_success_probability
                ) / (attempts + self.config.baseline_prior_strength)
                return _Baseline(
                    probability=self._bound_probability(probability),
                    attempts=attempts,
                    source=parent.level,
                )
        return None

    def _process(
        self,
        scope: DetectorScope,
        event: PaymentResultEvent,
        adaptive_baseline: _Baseline | None,
    ) -> HealthSnapshotV2:
        state = self._state(scope)
        if state.level is EvidenceLevel.RESOLVED:
            self._reset_after_episode(state)
        baseline = state.frozen_baseline or adaptive_baseline
        if baseline is None:
            return self._snapshot(scope, event.timestamp, state, None)

        state.monitoring_events += 1
        self._update_degradation_llrs(state, event.success, baseline.probability)
        if state.level is EvidenceLevel.HEALTHY:
            if (
                max(state.llrs) >= self.config.watch_llr_threshold
                and state.monitoring_events >= self.config.watch_min_events
            ):
                self._open_watch(scope, event, state, baseline)
        elif state.level is EvidenceLevel.WATCH:
            self._update_watch_evidence(scope, event, state)
            confirmation_rule = self._confirmation_rule(scope, event.timestamp, state)
            if confirmation_rule is not None:
                self._confirm(event.timestamp, state, confirmation_rule)
            elif (
                max(state.llrs) <= self.config.watch_release_llr
                and state.watch_release_successes >= self.config.watch_release_successes
            ):
                self._dissipate(event.timestamp, state)
        elif state.level in {EvidenceLevel.CONFIRMED, EvidenceLevel.RECOVERING}:
            self._update_watch_evidence(scope, event, state)
            self._update_recovery(event, state)

        self._refresh_active(scope, event.timestamp, state)
        return self._snapshot(scope, event.timestamp, state, baseline)

    def _update_degradation_llrs(
        self,
        state: _State,
        success: bool,
        baseline_probability: float,
    ) -> None:
        for index, drop in enumerate(self.config.drop_hypotheses):
            alternative = max(
                self.config.minimum_alternative_probability,
                baseline_probability - drop,
            )
            increment = _bernoulli_llr(success, baseline_probability, alternative)
            state.llrs[index] = max(0.0, state.llrs[index] + increment)

    def _open_watch(
        self,
        scope: DetectorScope,
        event: PaymentResultEvent,
        state: _State,
        baseline: _Baseline,
    ) -> None:
        digest = hashlib.sha256(f"{scope.key}|{event.timestamp.isoformat()}".encode()).hexdigest()[
            :12
        ]
        state.level = EvidenceLevel.WATCH
        state.frozen_baseline = baseline
        start = event.timestamp - timedelta(days=self.config.baseline_lookback_days)
        historical = self._history(scope).events_between(start, event.timestamp)
        state.frozen_reason_counts = Counter(
            item.failure_reason
            for item in historical[:-1]
            if not item.success and item.failure_reason is not None
        )
        state.current_reason_counts = Counter()
        state.current_failures = 0
        state.events_since_watch = 1
        state.watch_release_successes = int(event.success)
        if not event.success and event.failure_reason is not None:
            state.current_reason_counts[event.failure_reason] += 1
            state.current_failures = 1
        severity = self._severity(state)
        state.active = _MutableEpisode(
            incident_id=f"DEG2-{digest}",
            scope=scope,
            watch_at=event.timestamp,
            baseline_probability=baseline.probability,
            baseline_attempts=baseline.attempts,
            maximum_llr=max(state.llrs),
            current_attempts=1,
            current_failures=state.current_failures,
            severity=severity,
            transitions=[
                EvidenceTransition(
                    timestamp=event.timestamp,
                    evidence_level=EvidenceLevel.WATCH,
                    severity=severity,
                    maximum_llr=max(state.llrs),
                )
            ],
        )

    def _update_watch_evidence(
        self,
        scope: DetectorScope,
        event: PaymentResultEvent,
        state: _State,
    ) -> None:
        state.events_since_watch += 1
        state.watch_release_successes = state.watch_release_successes + 1 if event.success else 0
        if not event.success:
            state.current_failures += 1
            if event.failure_reason is not None:
                state.current_reason_counts[event.failure_reason] += 1
        failure = self._failure_evidence(state)
        parent = self._parent_corroboration(scope)
        if state.active is not None:
            state.active.current_attempts = state.events_since_watch
            state.active.current_failures = state.current_failures
            state.active.failure_evidence = failure
            state.active.parent = parent

    def _confirmation_rule(
        self,
        scope: DetectorScope,
        timestamp: datetime,
        state: _State,
    ) -> str | None:
        if state.events_since_watch < self.config.confirmed_min_events:
            return None
        if state.last_confirmed_at is not None and timestamp < state.last_confirmed_at + timedelta(
            days=self.config.confirmation_cooldown_days
        ):
            return None
        maximum = max(state.llrs)
        if maximum >= self.config.confirmed_llr_threshold:
            return "EXTREME_LOCAL_SEQUENTIAL_EVIDENCE"
        failure = self._failure_evidence(state)
        if (
            maximum >= self.config.confirmed_strong_llr
            and failure.supported
            and failure.jensen_shannon_divergence is not None
            and failure.jensen_shannon_divergence >= self.config.failure_js_threshold
        ):
            return "STRONG_LOCAL_PLUS_FAILURE_SHIFT"
        parent = self._parent_corroboration(scope)
        if (
            scope.level is ScopeLevel.ISSUER
            and maximum >= self.config.confirmed_parent_llr
            and parent.corroborated
        ):
            return "STRONG_LOCAL_PLUS_PARENT_CORROBORATION"
        return None

    def _confirm(self, timestamp: datetime, state: _State, rule: str) -> None:
        state.level = EvidenceLevel.CONFIRMED
        state.last_confirmed_at = timestamp
        state.recovery_llr = 0.0
        state.recovery_events = 0
        severity = self._severity(state)
        if state.active is not None:
            state.active.confirmed_at = timestamp
            state.active.confirmation_rule = rule
            state.active.severity = severity
            state.active.transitions.append(
                EvidenceTransition(
                    timestamp=timestamp,
                    evidence_level=EvidenceLevel.CONFIRMED,
                    severity=severity,
                    maximum_llr=max(state.llrs),
                )
            )

    def _update_recovery(self, event: PaymentResultEvent, state: _State) -> None:
        baseline = state.frozen_baseline
        if baseline is None:
            return
        reference_drop = self.config.drop_hypotheses[min(1, len(self.config.drop_hypotheses) - 1)]
        alternative = max(
            self.config.minimum_alternative_probability,
            baseline.probability - reference_drop,
        )
        recovery_increment = -_bernoulli_llr(event.success, baseline.probability, alternative)
        state.recovery_llr = max(0.0, state.recovery_llr + recovery_increment)
        state.recovery_events += 1
        severity = self._severity(state)
        if (
            state.level is EvidenceLevel.CONFIRMED
            and state.recovery_llr >= self.config.recovery_start_llr
        ):
            state.level = EvidenceLevel.RECOVERING
            self._append_transition(state, event.timestamp, EvidenceLevel.RECOVERING, severity)
        elif (
            state.level is EvidenceLevel.RECOVERING
            and not event.success
            and max(state.llrs) >= self.config.confirmed_strong_llr
            and state.recovery_llr < self.config.recovery_start_llr * 0.5
        ):
            state.level = EvidenceLevel.CONFIRMED
            self._append_transition(state, event.timestamp, EvidenceLevel.CONFIRMED, severity)
        if (
            state.level is EvidenceLevel.RECOVERING
            and state.recovery_llr >= self.config.recovery_resolve_llr
            and state.recovery_events >= self.config.recovery_min_events
        ):
            self._resolve(event.timestamp, state)

    def _dissipate(self, timestamp: datetime, state: _State) -> None:
        if state.active is None:
            return
        state.active.resolved_at = timestamp
        state.active.dissipated = True
        state.active.transitions.append(
            EvidenceTransition(
                timestamp=timestamp,
                evidence_level=EvidenceLevel.HEALTHY,
                severity=ObservableSeverity.MILD,
                maximum_llr=max(state.llrs),
            )
        )
        self._completed.append(state.active.frozen())
        last_confirmed = state.last_confirmed_at
        self._clear_state(state)
        state.last_confirmed_at = last_confirmed

    def _resolve(self, timestamp: datetime, state: _State) -> None:
        if state.active is None:
            return
        state.active.resolved_at = timestamp
        state.active.transitions.append(
            EvidenceTransition(
                timestamp=timestamp,
                evidence_level=EvidenceLevel.RESOLVED,
                severity=state.active.severity,
                maximum_llr=max(state.llrs),
            )
        )
        self._completed.append(state.active.frozen())
        state.active = None
        state.level = EvidenceLevel.RESOLVED

    def _reset_after_episode(self, state: _State) -> None:
        last_confirmed = state.last_confirmed_at
        self._clear_state(state)
        state.last_confirmed_at = last_confirmed

    def _clear_state(self, state: _State) -> None:
        state.level = EvidenceLevel.HEALTHY
        state.llrs = [0.0] * len(self.config.drop_hypotheses)
        state.monitoring_events = 0
        state.frozen_baseline = None
        state.frozen_reason_counts = Counter()
        state.current_reason_counts = Counter()
        state.current_failures = 0
        state.events_since_watch = 0
        state.watch_release_successes = 0
        state.recovery_llr = 0.0
        state.recovery_events = 0
        state.active = None

    def _refresh_active(self, scope: DetectorScope, timestamp: datetime, state: _State) -> None:
        if state.active is None:
            return
        severity = self._severity(state)
        if severity != state.active.severity:
            state.active.transitions.append(
                EvidenceTransition(
                    timestamp=timestamp,
                    evidence_level=state.level,
                    severity=severity,
                    maximum_llr=max(state.llrs),
                )
            )
        state.active.severity = severity
        state.active.maximum_llr = max(state.active.maximum_llr, max(state.llrs))
        state.active.failure_evidence = self._failure_evidence(state)
        state.active.parent = self._parent_corroboration(scope)

    def _append_transition(
        self,
        state: _State,
        timestamp: datetime,
        level: EvidenceLevel,
        severity: ObservableSeverity,
    ) -> None:
        if state.active is not None:
            state.active.transitions.append(
                EvidenceTransition(
                    timestamp=timestamp,
                    evidence_level=level,
                    severity=severity,
                    maximum_llr=max(state.llrs),
                )
            )

    def _failure_evidence(self, state: _State) -> FailureDistributionEvidence:
        baseline_total = sum(state.frozen_reason_counts.values())
        current_total = sum(state.current_reason_counts.values())
        supported = (
            baseline_total >= self.config.failure_min_baseline
            and current_total >= self.config.failure_min_current
        )
        if not supported:
            return FailureDistributionEvidence(
                supported=False,
                current_failure_count=current_total,
                baseline_failure_count=baseline_total,
            )
        reasons = sorted(set(state.frozen_reason_counts) | set(state.current_reason_counts))
        baseline_distribution = _smoothed_distribution(state.frozen_reason_counts, reasons)
        current_distribution = _smoothed_distribution(state.current_reason_counts, reasons)
        divergence = _jensen_shannon(current_distribution, baseline_distribution)
        shifts: list[ReasonShift] = []
        for reason, current_share, baseline_share in zip(
            reasons,
            current_distribution,
            baseline_distribution,
            strict=True,
        ):
            support = state.current_reason_counts[reason]
            increase = current_share - baseline_share
            if support < self.config.failure_reason_min_support or increase <= 0:
                continue
            shifts.append(
                ReasonShift(
                    reason=reason,
                    current_share=current_share,
                    baseline_share=baseline_share,
                    absolute_increase=increase,
                    relative_lift=current_share / baseline_share if baseline_share > 0 else None,
                    support_count=support,
                )
            )
        shifts.sort(key=lambda item: (item.absolute_increase, item.support_count), reverse=True)
        return FailureDistributionEvidence(
            supported=True,
            current_failure_count=current_total,
            baseline_failure_count=baseline_total,
            jensen_shannon_divergence=divergence,
            dominant_shifts=tuple(shifts[:3]),
        )

    def _parent_corroboration(self, scope: DetectorScope) -> ParentCorroboration:
        if scope.level is not ScopeLevel.ISSUER:
            return ParentCorroboration()
        method_scope = self._scope(ScopeLevel.PAYMENT_METHOD, scope.payment_method)
        global_scope = self._scope(ScopeLevel.GLOBAL)
        method = self._latest.get(method_scope.key)
        global_snapshot = self._latest.get(global_scope.key)
        levels = {EvidenceLevel.WATCH, EvidenceLevel.CONFIRMED}
        return ParentCorroboration(
            method_level=method.evidence_level if method else None,
            method_maximum_llr=(
                method.sequential_evidence.maximum_log_likelihood_ratio if method else None
            ),
            global_level=global_snapshot.evidence_level if global_snapshot else None,
            global_maximum_llr=(
                global_snapshot.sequential_evidence.maximum_log_likelihood_ratio
                if global_snapshot
                else None
            ),
            corroborated=bool(
                (method and method.evidence_level in levels)
                or (global_snapshot and global_snapshot.evidence_level in levels)
            ),
        )

    def _severity(self, state: _State) -> ObservableSeverity:
        maximum = max(state.llrs) if state.llrs else 0.0
        strongest_index = state.llrs.index(maximum) if state.llrs else 0
        strongest_drop = self.config.drop_hypotheses[strongest_index]
        if maximum >= 1.5 * self.config.confirmed_llr_threshold and strongest_drop >= 0.35:
            return ObservableSeverity.CRITICAL
        if maximum >= self.config.confirmed_llr_threshold and strongest_drop >= 0.20:
            return ObservableSeverity.SEVERE
        if maximum >= self.config.confirmed_strong_llr:
            return ObservableSeverity.MODERATE
        return ObservableSeverity.MILD

    def _snapshot(
        self,
        scope: DetectorScope,
        timestamp: datetime,
        state: _State,
        baseline: _Baseline | None,
    ) -> HealthSnapshotV2:
        active_baseline = state.frozen_baseline or baseline
        level = (
            EvidenceLevel.INSUFFICIENT_EVIDENCE
            if active_baseline is None and state.level is EvidenceLevel.HEALTHY
            else state.level
        )
        llrs = state.llrs or [0.0] * len(self.config.drop_hypotheses)
        baseline_probability = (
            active_baseline.probability
            if active_baseline is not None
            else self.config.default_success_probability
        )
        hypotheses = tuple(
            SequentialHypothesis(
                drop=drop,
                alternative_success_probability=max(
                    self.config.minimum_alternative_probability,
                    baseline_probability - drop,
                ),
                log_likelihood_ratio=llr,
            )
            for drop, llr in zip(self.config.drop_hypotheses, llrs, strict=True)
        )
        maximum = max(llrs)
        strongest_drop = self.config.drop_hypotheses[llrs.index(maximum)] if maximum > 0 else None
        active = state.active
        role = PolicyEvidenceRole.NONE
        if level is EvidenceLevel.WATCH:
            role = PolicyEvidenceRole.WATCH_ADVISORY
        elif level in {EvidenceLevel.CONFIRMED, EvidenceLevel.RECOVERING}:
            role = PolicyEvidenceRole.CONFIRMED_CANDIDATE
        return HealthSnapshotV2(
            scope=scope,
            timestamp=timestamp,
            evidence_level=level,
            observable_severity=(
                self._severity(state)
                if level in {EvidenceLevel.WATCH, EvidenceLevel.CONFIRMED, EvidenceLevel.RECOVERING}
                else None
            ),
            baseline_success_probability=(
                active_baseline.probability if active_baseline is not None else None
            ),
            baseline_attempts=active_baseline.attempts if active_baseline is not None else 0,
            baseline_source=active_baseline.source if active_baseline is not None else None,
            recent_windows=self._recent_windows(scope, timestamp),
            sequential_evidence=SequentialEvidence(
                hypotheses=hypotheses,
                maximum_log_likelihood_ratio=maximum,
                strongest_drop=strongest_drop,
                recovery_log_likelihood_ratio=state.recovery_llr,
            ),
            failure_distribution=self._failure_evidence(state),
            parent_corroboration=self._parent_corroboration(scope),
            active_incident_id=active.incident_id if active is not None else None,
            time_since_watch_seconds=(
                (timestamp - active.watch_at).total_seconds() if active is not None else None
            ),
            time_since_confirmed_seconds=(
                (timestamp - active.confirmed_at).total_seconds()
                if active is not None and active.confirmed_at is not None
                else None
            ),
            policy_evidence_role=role,
        )

    def _recent_windows(
        self,
        scope: DetectorScope,
        timestamp: datetime,
    ) -> tuple[WindowHealth, ...]:
        history = self._history(scope)
        windows: list[WindowHealth] = []
        for minutes in self.config.windows_minutes:
            attempts, successes = history.counts(
                timestamp - timedelta(minutes=minutes),
                timestamp,
            )
            windows.append(
                WindowHealth(
                    minutes=minutes,
                    attempts=attempts,
                    successes=successes,
                    success_rate=successes / attempts if attempts else None,
                )
            )
        return tuple(windows)

    def _bound_probability(self, value: float) -> float:
        return max(
            self.config.minimum_baseline_probability,
            min(self.config.maximum_baseline_probability, value),
        )


def _bernoulli_llr(success: bool, p0: float, p1: float) -> float:
    if success:
        return math.log(p1 / p0)
    return math.log((1 - p1) / (1 - p0))


def _smoothed_distribution(counts: Counter[str], reasons: list[str]) -> list[float]:
    smoothing = 0.5
    total = sum(counts.values()) + smoothing * len(reasons)
    return [(counts[reason] + smoothing) / total for reason in reasons]


def _jensen_shannon(left: list[float], right: list[float]) -> float:
    midpoint = [(a + b) / 2 for a, b in zip(left, right, strict=True)]

    def divergence(values: list[float]) -> float:
        return sum(
            value * math.log2(value / middle)
            for value, middle in zip(values, midpoint, strict=True)
        )

    return 0.5 * divergence(left) + 0.5 * divergence(right)


def _empty_failure_evidence() -> FailureDistributionEvidence:
    return FailureDistributionEvidence(
        supported=False,
        current_failure_count=0,
        baseline_failure_count=0,
    )
