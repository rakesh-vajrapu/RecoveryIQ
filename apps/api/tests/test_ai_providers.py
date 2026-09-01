from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.fake import FakeLLMProvider
from app.ai.fallback import DeterministicFallbackProvider
from app.ai.gemini import GeminiLLMProvider
from app.ai.provider import ExplanationProvider, LLMConfigurationError
from app.ai.schemas import DecisionExplanation
from app.core.config import Settings


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


@pytest.mark.asyncio
async def test_gemini_uses_api_compatible_schema_and_validates_response() -> None:
    captured: dict[str, Any] = {}

    class StubModels:
        def generate_content(self, **kwargs: Any) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                parsed=None,
                text=(
                    '{"summary":"The supplied recovery probability is 0.61.",'
                    '"factors":["Policy result: ALLOWED"],'
                    '"confidence":0.95,'
                    '"limitations":["The probability does not guarantee recovery."]}'
                ),
            )

    settings = Settings(
        _env_file=None,
        gemini_enabled=True,
        gemini_api_key="test-key",
        gemini_model="gemini-3.7-flash",
        gemini_api_version="v1",
        gemini_thinking_level="low",
    )
    provider = GeminiLLMProvider(settings)
    provider._client_instance = SimpleNamespace(models=StubModels())  # type: ignore[assignment]

    result = await provider.explain_decision_trace(
        {
            "candidate_action": "RETRY_LATER_12H",
            "recovery_probability": 0.61,
            "policy_result": "ALLOWED",
        }
    )

    config = captured["config"]
    assert "additionalProperties" not in config.response_schema
    assert config.response_mime_type == "application/json"
    assert "Do not choose actions." in captured["contents"]
    assert isinstance(result, DecisionExplanation)


@pytest.mark.asyncio
async def test_gemini_model_diagnostic_filters_generate_content_models() -> None:
    class StubModels:
        def list(self) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    name="models/gemini-3.6-flash",
                    supported_actions=["generateContent", "countTokens"],
                ),
                SimpleNamespace(
                    name="models/gemini-embedding",
                    supported_actions=["embedContent"],
                ),
                SimpleNamespace(name=None, supported_actions=["generateContent"]),
            ]

    settings = Settings(
        _env_file=None,
        gemini_enabled=True,
        gemini_api_key="test-key",
        gemini_model="gemini-3.6-flash",
    )
    provider = GeminiLLMProvider(settings)
    provider._client_instance = SimpleNamespace(models=StubModels())  # type: ignore[assignment]

    assert await provider.available_generate_content_models() == ("models/gemini-3.6-flash",)
    assert await provider.health_check() is True
