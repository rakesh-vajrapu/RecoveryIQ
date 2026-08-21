from collections.abc import Mapping
from typing import Any

from app.ai.schemas import DecisionExplanation


class DeterministicFallbackProvider:
    """Create a safe explanation using only explicitly supplied evidence."""

    async def health_check(self) -> bool:
        return True

    async def explain_decision(self, evidence: Mapping[str, Any]) -> DecisionExplanation:
        selected_action = str(evidence.get("selected_action", "not selected"))
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
            headline="Deterministic recovery explanation",
            summary=(
                "RecoverIQ used the supplied decision evidence and deterministic policy result. "
                "No generative AI response was required."
            ),
            key_factors=factors,
            uncertainty=(
                "This fallback reports only supplied evidence and does not infer payment outcomes."
            ),
        )
