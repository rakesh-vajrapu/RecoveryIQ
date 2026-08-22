from __future__ import annotations

import inspect
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from recoveriq_detector_v2.config import DetectorV2Config
from recoveriq_detector_v2.detector import OperationalDegradationDetectorV2
from recoveriq_detector_v2.models import (
    EvidenceLevel,
    HealthSnapshotV2,
    PaymentHealthContextV2,
    PaymentResultEvent,
    PolicyEvidenceRole,
    ScopeLevel,
)


def _event(
    event_id: str,
    timestamp: datetime,
    success: bool,
    *,
    issuer: str = "ISSUER_A",
    reason: str = "ISSUER_UNAVAILABLE",
) -> PaymentResultEvent:
    return PaymentResultEvent(
        event_id=event_id,
        timestamp=timestamp,
        merchant_id="MERCHANT",
        payment_method="UPI",
        issuer=issuer,
        success=success,
        failure_reason=None if success else reason,
        failure_source=None if success else "ISSUER",
    )


def _baseline(start: datetime, *, issuer: str = "ISSUER_A") -> list[PaymentResultEvent]:
    return [
        _event(
            f"BASE-{issuer}-{index}",
            start + timedelta(minutes=5 * index),
            index % 10 != 0,
            issuer=issuer,
            reason="TEMPORARY_NETWORK_ERROR",
        )
        for index in range(120)
    ]


def _issuer_snapshot(snapshots: Iterable[HealthSnapshotV2]) -> HealthSnapshotV2:
    return next(item for item in snapshots if item.scope.level is ScopeLevel.ISSUER)


def test_update_contract_contains_no_ground_truth() -> None:
    signature = inspect.signature(OperationalDegradationDetectorV2.update)
    assert set(signature.parameters) == {"self", "event"}
    assert "ground_truth" not in str(signature)


def test_watch_is_explicitly_advisory_and_cannot_be_hard_authority() -> None:
    config = DetectorV2Config(
        watch_llr_threshold=1.0,
        confirmed_strong_llr=20.0,
        confirmed_parent_llr=20.0,
        confirmed_llr_threshold=30.0,
        confirmed_min_events=20,
    )
    detector = OperationalDegradationDetectorV2(config)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for event in _baseline(start):
        detector.update(event)
    snapshot = None
    anomaly = start + timedelta(days=2)
    for index in range(3):
        snapshot = _issuer_snapshot(
            detector.update(_event(f"FAIL-{index}", anomaly + timedelta(minutes=index), False))
        )
    assert snapshot is not None
    assert snapshot.evidence_level is EvidenceLevel.WATCH
    assert snapshot.policy_evidence_role is PolicyEvidenceRole.WATCH_ADVISORY
    context = detector.get_health_context(snapshot.timestamp, "UPI", "ISSUER_A")
    assert context.confirmed_hard_policy_gate_passed is False


def test_confirmed_requires_more_evidence_than_watch() -> None:
    detector = OperationalDegradationDetectorV2(DetectorV2Config())
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for event in _baseline(start):
        detector.update(event)
    anomaly = start + timedelta(days=2)
    watch_index = None
    confirmed_index = None
    for index in range(20):
        snapshot = _issuer_snapshot(
            detector.update(_event(f"DROP-{index}", anomaly + timedelta(minutes=index), False))
        )
        if snapshot.evidence_level is EvidenceLevel.WATCH and watch_index is None:
            watch_index = index
        if snapshot.evidence_level is EvidenceLevel.CONFIRMED:
            confirmed_index = index
            break
    assert watch_index is not None
    assert confirmed_index is not None
    assert confirmed_index > watch_index


def test_single_low_volume_burst_does_not_confirm() -> None:
    detector = OperationalDegradationDetectorV2(DetectorV2Config())
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for event in _baseline(start):
        detector.update(event)
    snapshot = _issuer_snapshot(
        detector.update(_event("ONE-FAIL", start + timedelta(days=2), False))
    )
    assert snapshot.evidence_level is not EvidenceLevel.CONFIRMED


def test_sequential_evidence_accumulates_deterministically_and_success_reduces_it() -> None:
    detectors = [OperationalDegradationDetectorV2(DetectorV2Config()) for _ in range(2)]
    start = datetime(2026, 1, 1, tzinfo=UTC)
    stream = _baseline(start)
    anomaly = start + timedelta(days=2)
    stream.extend(
        _event(f"SEQ-{index}", anomaly + timedelta(minutes=index), False) for index in range(3)
    )
    before_success = None
    after_success = None
    for detector in detectors:
        for event in stream:
            before_success = _issuer_snapshot(detector.update(event))
        after_success = _issuer_snapshot(
            detector.update(_event("SEQ-SUCCESS", anomaly + timedelta(minutes=4), True))
        )
    assert before_success is not None and after_success is not None
    assert (
        after_success.sequential_evidence.maximum_log_likelihood_ratio
        < before_success.sequential_evidence.maximum_log_likelihood_ratio
    )
    assert detectors[0].episodes == detectors[1].episodes


def test_baseline_freezes_after_watch() -> None:
    detector = OperationalDegradationDetectorV2(DetectorV2Config(watch_llr_threshold=1.0))
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for event in _baseline(start):
        detector.update(event)
    anomaly = start + timedelta(days=2)
    watch_snapshot = None
    for index in range(3):
        watch_snapshot = _issuer_snapshot(
            detector.update(_event(f"FREEZE-{index}", anomaly + timedelta(minutes=index), False))
        )
    assert watch_snapshot is not None
    frozen = watch_snapshot.baseline_success_probability
    later = watch_snapshot
    for index in range(3, 12):
        later = _issuer_snapshot(
            detector.update(_event(f"FREEZE-{index}", anomaly + timedelta(minutes=index), False))
        )
    assert later.baseline_success_probability == frozen


def test_failure_shift_requires_support() -> None:
    detector = OperationalDegradationDetectorV2(
        DetectorV2Config(watch_llr_threshold=1.0, failure_min_current=5)
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for event in _baseline(start):
        detector.update(event)
    anomaly = start + timedelta(days=2)
    snapshot = None
    for index in range(3):
        snapshot = _issuer_snapshot(
            detector.update(_event(f"SHIFT-{index}", anomaly + timedelta(minutes=index), False))
        )
    assert snapshot is not None
    assert snapshot.failure_distribution.supported is False
    assert not snapshot.failure_distribution.dominant_shifts


def test_parent_corroboration_cannot_fabricate_local_confirmation() -> None:
    config = DetectorV2Config(
        watch_llr_threshold=0.5,
        confirmed_parent_llr=2.0,
        confirmed_strong_llr=6.0,
        confirmed_llr_threshold=8.0,
        confirmed_min_events=2,
    )
    detector = OperationalDegradationDetectorV2(config)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    baseline_events = sorted(
        (*_baseline(start, issuer="ISSUER_A"), *_baseline(start, issuer="ISSUER_B")),
        key=lambda event: (event.timestamp, event.event_id),
    )
    for event in baseline_events:
        detector.update(event)
    anomaly = start + timedelta(days=2)
    for index in range(8):
        detector.update(
            _event(f"PARENT-{index}", anomaly + timedelta(minutes=index), False, issuer="ISSUER_B")
        )
    local = _issuer_snapshot(
        detector.update(_event("LOCAL-ONE", anomaly + timedelta(minutes=9), False))
    )
    assert local.scope.issuer == "ISSUER_A"
    assert local.evidence_level is not EvidenceLevel.CONFIRMED


def test_strong_local_evidence_confirms_independently() -> None:
    detector = OperationalDegradationDetectorV2(DetectorV2Config())
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for event in _baseline(start):
        detector.update(event)
    anomaly = start + timedelta(days=2)
    for index in range(20):
        detector.update(_event(f"LOCAL-{index}", anomaly + timedelta(minutes=index), False))
    issuer_episode = next(
        episode for episode in detector.episodes if episode.scope.level is ScopeLevel.ISSUER
    )
    assert issuer_episode.confirmed_at is not None
    assert issuer_episode.confirmation_rule == "EXTREME_LOCAL_SEQUENTIAL_EVIDENCE"


def test_prefix_snapshot_cannot_use_future_events() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    events = _baseline(start)
    first = OperationalDegradationDetectorV2(DetectorV2Config())
    second = OperationalDegradationDetectorV2(DetectorV2Config())
    prefix_first = None
    prefix_second = None
    for event in events[:80]:
        prefix_first = first.update(event)
        prefix_second = second.update(event)
    assert prefix_first == prefix_second
    for event in events[80:]:
        second.update(event)
    assert prefix_first == prefix_second


def test_phase4_context_exposes_no_hidden_fields() -> None:
    assert set(PaymentHealthContextV2.model_fields).isdisjoint(
        {
            "hidden_incident_id",
            "hidden_severity",
            "incident_end_time",
            "true_failure_cause",
            "future_clearance_time",
        }
    )
