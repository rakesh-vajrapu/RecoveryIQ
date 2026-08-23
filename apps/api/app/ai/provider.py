from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from app.ai.schemas import DecisionExplanation


class LLMConfigurationError(RuntimeError):
    """Raised by an explicitly invoked provider when required configuration is absent."""


class ExplanationResponseError(RuntimeError):
    """Raised when a provider does not return a valid explanation."""


class ExplanationProviderError(RuntimeError):
    """Raised when an explanation provider request fails safely."""


class ExplanationProvider(Protocol):
    async def health_check(self) -> bool:
        """Check provider availability without mutating application state."""
        ...

    async def explain_decision_trace(
        self, evidence: Mapping[str, Any]
    ) -> DecisionExplanation:
        """Explain a precomputed decision trace without authorizing an action."""
        ...

    async def explain_recovery_case(
        self, evidence: Mapping[str, Any]
    ) -> DecisionExplanation:
        """Explain a recovery case without mutating it or determining its outcome."""
        ...


# Backward-compatible name for code that still refers to the Phase 1 abstraction.
LLMProvider = ExplanationProvider
