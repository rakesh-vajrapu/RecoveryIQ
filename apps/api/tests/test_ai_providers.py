import pytest

from app.ai.fake import FakeLLMProvider
from app.ai.fallback import DeterministicFallbackProvider
from app.ai.provider import ExplanationProvider
from app.ai.schemas import DecisionExplanation


def assert_provider_contract(_: ExplanationProvider) -> None:
    """Static type assertion that concrete providers implement the protocol."""


@pytest.mark.asyncio
async def test_fake_provider_returns_valid_structured_explanation() -> None:
    provider = FakeLLMProvider()
    assert_provider_contract(provider)

    result = await provider.explain_decision_trace({"selected_action": "RETRY_LATER"})

    assert isinstance(result, DecisionExplanation)
    assert "RETRY_LATER" in result.summary


@pytest.mark.asyncio
async def test_deterministic_fallback_uses_only_supplied_evidence() -> None:
    provider = DeterministicFallbackProvider()
    assert_provider_contract(provider)
    evidence = {
        "selected_action": "WAITING",
        "policy_result": "APPROVED",
        "failure_reason": "issuer_unavailable",
        "degradation_active": True,
    }

    result = await provider.explain_decision_trace(evidence)

    assert any("WAITING" in factor for factor in result.factors)
    assert any("issuer_unavailable" in factor for factor in result.factors)
    assert all("payment succeeded" not in factor.lower() for factor in result.factors)
