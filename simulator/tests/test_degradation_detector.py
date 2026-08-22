from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

import pytest

from recoveriq_detector.config import DetectorConfig
from recoveriq_detector.detector import PaymentDegradationDetector
from recoveriq_detector.models import (
    HealthStatus,
    PaymentHealthContext,
    PaymentResultEvent,
    ScopeLevel,
)


def _event(
    index: int,
    timestamp: datetime,
    success: bool,
    *,
    reason: str = "ISSUER_UNAVAILABLE",
) -> PaymentResultEvent:
    return PaymentResultEvent(
        event_id=f"EVENT-{index:05d}",
        timestamp=timestamp,
        merchant_id="MERCHANT",
        payment_method="UPI",
        issuer="ISSUER_A",
        success=success,
        failure_reason=None if success else reason,
        failure_source=None if success else "ISSUER",
    )


def _stream(*, degraded_failures: int, recovery_successes: int = 0) -> list[PaymentResultEvent]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    events = [
        _event(index, start + timedelta(minutes=5 * index), index % 10 != 0, reason="OTHER")
        for index in range(120)
    ]
    degraded_at = start + timedelta(days=2)
    events.extend(
        _event(1_000 + index, degraded_at + timedelta(minutes=index), False)
        for index in range(degraded_failures)
    )
    recovery_at = degraded_at + timedelta(hours=7)
    events.extend(
        _event(2_000 + index, recovery_at + timedelta(minutes=index), True)
        for index in range(recovery_successes)
    )
    return events


def _config(**updates: object) -> DetectorConfig:
    values: dict[str, object] = {
        "windows_minutes": (5, 15, 60, 360),
        "baseline_exclusion_minutes": 360,
        "min_baseline_attempts": 50,
        "min_current_attempts": 5,
        "meaningful_drop": 0.14,
        "posterior_open_probability": 0.95,
        "ewma_drop_threshold": 0.08,
        "open_persistence": 2,
        "recovery_persistence": 4,
    }
    values.update(updates)
    return DetectorConfig.model_validate(values)


def test_detector_public_update_receives_no_ground_truth_object() -> None:
    signature = inspect.signature(PaymentDegradationDetector.update)
    assert set(signature.parameters) == {"self", "event"}
    assert "ground_truth" not in str(signature)


def test_sparse_sample_does_not_open_incident() -> None:
    detector = PaymentDegradationDetector(_config())
    for event in _stream(degraded_failures=2):
        detector.update(event)
    assert not detector.predicted_incidents
    context = detector.get_health_context(datetime(2026, 1, 4, tzinfo=UTC), "UPI", "ISSUER_A")
    assert context.issuer_health is not None
    assert context.issuer_health.status in {
        HealthStatus.HEALTHY,
        HealthStatus.INSUFFICIENT_EVIDENCE,
    }


def test_severe_high_volume_drop_opens_one_incident_with_supported_shift() -> None:
    detector = PaymentDegradationDetector(_config())
    for event in _stream(degraded_failures=20):
        detector.update(event)
    issuer_incidents = [
        incident
        for incident in detector.predicted_incidents
        if incident.scope.level is ScopeLevel.ISSUER
    ]
    assert len(issuer_incidents) == 1
    assert issuer_incidents[0].dominant_failure_shifts
    assert issuer_incidents[0].dominant_failure_shifts[0].reason == "ISSUER_UNAVAILABLE"


def test_normal_variation_usually_remains_without_incident() -> None:
    detector = PaymentDegradationDetector(_config())
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(500):
        detector.update(_event(index, start + timedelta(minutes=10 * index), index % 10 != 0))
    assert not detector.predicted_incidents


def test_future_events_do_not_change_prior_snapshot() -> None:
    events = _stream(degraded_failures=12)
    prefix = events[:125]
    first = PaymentDegradationDetector(_config())
    second = PaymentDegradationDetector(_config())
    first_snapshot = None
    second_snapshot = None
    for event in prefix:
        first_snapshot = first.update(event)
        second_snapshot = second.update(event)
    assert first_snapshot == second_snapshot
    frozen_prefix_snapshot = first_snapshot
    for event in events[125:]:
        second.update(event)
    assert first_snapshot == frozen_prefix_snapshot


def test_baseline_excludes_current_and_future_events() -> None:
    detector = PaymentDegradationDetector(_config())
    events = _stream(degraded_failures=8)
    snapshot = None
    for event in events:
        result = detector.update(event)
        snapshot = next(item for item in result if item.scope.level is ScopeLevel.ISSUER)
    assert snapshot is not None
    assert snapshot.historical_attempts == 120
    assert snapshot.historical_success_rate == pytest.approx(0.9)


def test_active_incident_updates_without_duplication_and_hysteresis_resolves() -> None:
    detector = PaymentDegradationDetector(_config())
    events = _stream(degraded_failures=20, recovery_successes=50)
    for event in events[:140]:
        detector.update(event)
    assert (
        len(
            [item for item in detector.predicted_incidents if item.scope.level is ScopeLevel.ISSUER]
        )
        == 1
    )
    incident_id = next(
        item.incident_id
        for item in detector.predicted_incidents
        if item.scope.level is ScopeLevel.ISSUER
    )
    detector.update(events[140])
    active = [item for item in detector.predicted_incidents if item.incident_id == incident_id]
    assert len(active) == 1
    assert active[0].resolved_at is None
    for event in events[141:]:
        detector.update(event)
    resolved = next(
        item for item in detector.predicted_incidents if item.incident_id == incident_id
    )
    assert resolved.resolved_at is not None
    statuses = [transition.status for transition in resolved.transitions]
    assert HealthStatus.RECOVERING in statuses
    assert statuses[-1] is HealthStatus.RESOLVED


def test_dominant_shift_requires_support() -> None:
    detector = PaymentDegradationDetector(
        _config(dominant_reason_min_failures=10, dominant_reason_min_support=10)
    )
    for event in _stream(degraded_failures=8):
        detector.update(event)
    incidents = [
        item for item in detector.predicted_incidents if item.scope.level is ScopeLevel.ISSUER
    ]
    assert incidents
    assert not incidents[0].dominant_failure_shifts


def test_event_order_and_replay_are_deterministic() -> None:
    events = _stream(degraded_failures=12)
    detectors = [PaymentDegradationDetector(_config()) for _ in range(2)]
    for detector in detectors:
        for event in events:
            detector.update(event)
    assert detectors[0].predicted_incidents == detectors[1].predicted_incidents
    with pytest.raises(ValueError, match="nondecreasing"):
        detectors[0].update(_event(99_999, datetime(2025, 1, 1, tzinfo=UTC), True))


def test_payment_health_context_has_no_hidden_fields() -> None:
    assert set(PaymentHealthContext.model_fields).isdisjoint(
        {
            "incident_id",
            "hidden_severity",
            "incident_end",
            "hidden_probability",
            "true_failure_cause",
        }
    )
