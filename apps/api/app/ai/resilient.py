from collections.abc import Mapping
from typing import Any

from app.ai.provider import ExplanationProvider
from app.ai.schemas import DecisionExplanation


class ResilientExplanationProvider:
    """Fall back deterministically when optional enrichment is unavailable."""

    def __init__(
        self,
        primary: ExplanationProvider,
        fallback: ExplanationProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    async def health_check(self) -> bool:
        try:
            return await self._primary.health_check()
        except Exception:
            return await self._fallback.health_check()

    async def explain_decision_trace(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        try:
            return await self._primary.explain_decision_trace(evidence)
        except Exception:
            return await self._fallback.explain_decision_trace(evidence)

    async def explain_recovery_case(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        try:
            return await self._primary.explain_recovery_case(evidence)
        except Exception:
            return await self._fallback.explain_recovery_case(evidence)

    async def explain_decision(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        """Compatibility alias for the original Phase 1 method."""
        return await self.explain_decision_trace(evidence)
