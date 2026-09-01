from collections.abc import Mapping
from typing import Any

from app.ai.schemas import DecisionExplanation


class DeterministicFallbackProvider:
    """Create a safe explanation using only explicitly supplied evidence."""

    async def health_check(self) -> bool:
        return True

    async def _explain(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        selected_action = str(
            evidence.get("selected_action", evidence.get("candidate_action", "not selected"))
        )
        policy_result = str(evidence.get("policy_result", "not provided"))
        failure_reason = str(evidence.get("failure_reason", "not provided"))

        factors = [
            f"Selected action: {selected_action}",
            f"Policy result: {policy_result}",
            f"Failure reason: {failure_reason}",
        ]
        if "degradation_active" in evidence:
            factors.append(f"Degradation active: {bool(evidence['degradation_active'])}")

        return DecisionExplanation(
            summary=(
                "RecoverIQ used the supplied decision evidence and deterministic policy result. "
                "No generative AI response was required."
            ),
            factors=factors,
            confidence=1.0,
            limitations=[
                "This fallback reports only supplied evidence and does not infer payment outcomes."
            ],
        )

    async def explain_decision_trace(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        return await self._explain(evidence)

    async def explain_recovery_case(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        return await self._explain(evidence)

    async def explain_decision(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        """Compatibility alias for the original Phase 1 method."""
        return await self.explain_decision_trace(evidence)
