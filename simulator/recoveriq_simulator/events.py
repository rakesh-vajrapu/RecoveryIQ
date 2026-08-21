from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from recoveriq_simulator.enums import EventType


@dataclass(order=True, slots=True, frozen=True)
class SimulationEvent:
    execute_at: datetime
    sequence: int
    event_type: EventType = field(compare=False)
    payload: Any = field(compare=False)


class EventQueue:
    """Small deterministic in-process priority queue for simulation clock events."""

    def __init__(self) -> None:
        self._events: list[SimulationEvent] = []
        self._sequence = 0

    def push(self, execute_at: datetime, event_type: EventType, payload: Any) -> None:
        self._sequence += 1
        heapq.heappush(
            self._events,
            SimulationEvent(
                execute_at=execute_at,
                sequence=self._sequence,
                event_type=event_type,
                payload=payload,
            ),
        )

    def pop(self) -> SimulationEvent:
        return heapq.heappop(self._events)

    def __bool__(self) -> bool:
        return bool(self._events)

    def __len__(self) -> int:
        return len(self._events)
