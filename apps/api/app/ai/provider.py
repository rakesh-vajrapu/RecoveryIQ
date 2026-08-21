from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from app.ai.schemas import DecisionExplanation


class LLMConfigurationError(RuntimeError):
    """Raised by an explicitly invoked provider when required configuration is absent."""


class LLMProvider(Protocol):
    async def health_check(self) -> bool:
        """Check provider availability without mutating application state."""
        ...

    async def explain_decision(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        """Explain precomputed decision evidence without authorizing an action."""
        ...
