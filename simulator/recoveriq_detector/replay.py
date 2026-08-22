from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from recoveriq_detector.config import DetectorConfig
from recoveriq_detector.detector import PaymentDegradationDetector
from recoveriq_detector.models import (
    PaymentHealthSnapshot,
    PaymentResultEvent,
    PredictedIncident,
    ScopeLevel,
)
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.observation import ObservedPaymentEvent


@dataclass(frozen=True, slots=True)
class ReplayResult:
    incidents: tuple[PredictedIncident, ...]
    snapshot_sample: tuple[PaymentHealthSnapshot, ...]
    events_processed: int
    runtime_seconds: float

    @property
    def throughput_events_per_second(self) -> float:
        return (
            self.events_processed / self.runtime_seconds if self.runtime_seconds else float("inf")
        )

    @property
    def mean_update_latency_ms(self) -> float:
        return 1000 * self.runtime_seconds / self.events_processed if self.events_processed else 0.0


def observable_detector_event(event: ObservedPaymentEvent) -> PaymentResultEvent:
    """Convert by observable attributes without accepting an environment truth object."""

    return PaymentResultEvent(
        event_id=event.event_id,
        timestamp=event.observed_at,
        merchant_id=event.merchant_id,
        payment_method=event.payment_method.value,
        issuer=event.issuer,
        success=event.success,
        failure_reason=(event.failure_reason.value if event.failure_reason is not None else None),
        failure_source=(event.failure_source.value if event.failure_source is not None else None),
    )


def replay_scenario(
    scenario: GeneratedScenario,
    config: DetectorConfig,
    *,
    sample_every: int = 500,
) -> ReplayResult:
    detector = PaymentDegradationDetector(config)
    events = sorted(
        scenario.public.observable_events,
        key=lambda event: (event.observed_at, event.event_id),
    )
    samples: list[PaymentHealthSnapshot] = []
    started = perf_counter()
    for index, source_event in enumerate(events, start=1):
        snapshots = detector.update(observable_detector_event(source_event))
        if sample_every > 0 and index % sample_every == 0:
            samples.extend(
                snapshot for snapshot in snapshots if snapshot.scope.level is ScopeLevel.ISSUER
            )
    runtime = perf_counter() - started
    samples.extend(detector.latest_snapshots)
    return ReplayResult(
        incidents=detector.predicted_incidents,
        snapshot_sample=tuple(samples),
        events_processed=len(events),
        runtime_seconds=runtime,
    )
