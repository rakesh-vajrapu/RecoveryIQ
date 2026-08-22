from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from recoveriq_detector_v2.config import DetectorV2Config
from recoveriq_detector_v2.detector import OperationalDegradationDetectorV2
from recoveriq_detector_v2.models import PaymentResultEvent

DEMO_LABEL = "DEMO SCENARIO — NOT BENCHMARK DATA"


def run_v2_demo(config: DetectorV2Config) -> dict[str, Any]:
    detector = OperationalDegradationDetectorV2(config)
    started = datetime(2026, 8, 1, tzinfo=UTC)
    events: list[PaymentResultEvent] = []
    baseline_count = 576
    degraded_count = 80
    recovery_count = 160
    degraded_at = started + timedelta(days=2)
    recovery_at = degraded_at + timedelta(minutes=160)
    timestamps = [
        *(started + timedelta(minutes=5 * index) for index in range(baseline_count)),
        *(degraded_at + timedelta(minutes=2 * index) for index in range(degraded_count)),
        *(recovery_at + timedelta(minutes=3 * index) for index in range(recovery_count)),
    ]
    for index, timestamp in enumerate(timestamps):
        if index < baseline_count:
            success = index % 10 != 0
            reason = "TEMPORARY_NETWORK_ERROR"
        elif index < baseline_count + degraded_count:
            success = index % 8 == 0
            reason = "ISSUER_UNAVAILABLE"
        else:
            success = index % 20 != 0
            reason = "TEMPORARY_NETWORK_ERROR"
        events.append(
            PaymentResultEvent(
                event_id=f"DEMO-V2-{index:04d}",
                timestamp=timestamp,
                merchant_id="DEMO_MERCHANT",
                payment_method="UPI",
                issuer="ISSUER_DEMO",
                success=success,
                failure_reason=None if success else reason,
                failure_source=None if success else "ISSUER",
            )
        )
    for event in events:
        detector.update(event)
    issuer_episodes = [
        episode.model_dump(mode="json")
        for episode in detector.episodes
        if episode.scope.issuer == "ISSUER_DEMO"
    ]
    return {
        "label": DEMO_LABEL,
        "benchmark_data": False,
        "events": len(events),
        "degradation_started_at": degraded_at.isoformat(),
        "recovery_started_at": recovery_at.isoformat(),
        "episodes": issuer_episodes,
        "final_context": detector.get_health_context(
            events[-1].timestamp,
            "UPI",
            "ISSUER_DEMO",
        ).model_dump(mode="json"),
    }
