import pytest

from app.ai.fake import FakeLLMProvider
from app.ai.fallback import DeterministicFallbackProvider
from app.ai.gemini import GeminiLLMProvider
from app.ai.provider import LLMConfigurationError, LLMProvider
from app.ai.schemas import DecisionExplanation
from app.core.config import Settings


def assert_provider_contract(_: LLMProvider) -> None:
    """Static type assertion that concrete providers implement the protocol."""


@pytest.mark.asyncio
async def test_fake_provider_returns_valid_structured_explanation() -> None:
    provider = FakeLLMProvider()
    assert_provider_contract(provider)

    result = await provider.explain_decision({"selected_action": "RETRY_LATER"})

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

    result = await provider.explain_decision(evidence)

    assert any("WAITING" in factor for factor in result.key_factors)
    assert any("issuer_unavailable" in factor for factor in result.key_factors)
    assert all("payment succeeded" not in factor.lower() for factor in result.key_factors)


@pytest.mark.asyncio
async def test_disabled_gemini_fails_only_when_explicitly_invoked() -> None:
    settings = Settings(_env_file=None, gemini_enabled=False, gemini_api_key=None)
    provider = GeminiLLMProvider(settings)
    assert_provider_contract(provider)

    with pytest.raises(LLMConfigurationError, match="disabled"):
        await provider.health_check()


@pytest.mark.asyncio
async def test_enabled_gemini_without_key_has_clear_error() -> None:
    settings = Settings(_env_file=None, gemini_enabled=True, gemini_api_key=None)
    provider = GeminiLLMProvider(settings)

    with pytest.raises(LLMConfigurationError, match="GEMINI_API_KEY"):
        await provider.health_check()
