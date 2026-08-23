from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.factory import create_explanation_provider
from app.ai.fallback import DeterministicFallbackProvider
from app.ai.groq import GroqExplanationProvider
from app.ai.provider import ExplanationProvider, ExplanationResponseError
from app.ai.resilient import ResilientExplanationProvider
from app.ai.schemas import DecisionExplanation
from app.core.config import Settings


def assert_provider_contract(_: ExplanationProvider) -> None:
    """Static type assertion that concrete providers implement the protocol."""


def valid_explanation_json() -> str:
    return json.dumps(
        {
            "summary": "The trace records a policy-allowed retry candidate.",
            "factors": [
                "Failure reason: INSUFFICIENT_FUNDS",
                "Candidate action: RETRY_LATER_12H",
            ],
            "confidence": 0.9,
            "limitations": ["The supplied evidence does not guarantee recovery."],
        }
    )


class StubCompletions:
    def __init__(self, content: str | None) -> None:
        self.content = content
        self.arguments: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.arguments = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class StubModels:
    def __init__(self, model_ids: tuple[str, ...]) -> None:
        self.model_ids = model_ids

    def list(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=model_id) for model_id in self.model_ids]


class FailingProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def health_check(self) -> bool:
        raise self.error

    async def explain_decision_trace(
        self, evidence: Mapping[str, Any]
    ) -> DecisionExplanation:
        raise self.error

    async def explain_recovery_case(
        self, evidence: Mapping[str, Any]
    ) -> DecisionExplanation:
        raise self.error


@pytest.mark.asyncio
async def test_groq_returns_structured_pydantic_explanation_only() -> None:
    completions = StubCompletions(valid_explanation_json())
    provider = GroqExplanationProvider(
        Settings(
            _env_file=None,
            explanation_provider="groq",
            groq_api_key="test-secret",
            groq_model="openai/gpt-oss-120b",
        )
    )
    provider._client_instance = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=completions)
    )
    assert_provider_contract(provider)
    evidence = {
        "candidate_action": "RETRY_LATER_12H",
        "policy_result": "ALLOWED",
        "recovery_probability": 0.61,
    }
    original = deepcopy(evidence)

    result = await provider.explain_decision_trace(evidence)

    assert isinstance(result, DecisionExplanation)
    assert result.confidence == 0.9
    assert evidence == original
    assert completions.arguments["model"] == "openai/gpt-oss-120b"
    assert completions.arguments["response_format"] == {"type": "json_object"}
    assert "test-secret" not in json.dumps(completions.arguments)
    assert not hasattr(result, "selected_action")
    assert not hasattr(result, "policy_result")


@pytest.mark.asyncio
async def test_groq_health_check_supports_namespaced_model_ids() -> None:
    provider = GroqExplanationProvider(
        Settings(
            _env_file=None,
            groq_api_key="test-secret",
            groq_model="openai/gpt-oss-120b",
        )
    )
    provider._client_instance = SimpleNamespace(  # type: ignore[assignment]
        models=StubModels(("openai/gpt-oss-120b",))
    )

    assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_groq_rejects_invalid_or_authoritative_response_shape() -> None:
    completions = StubCompletions(
        json.dumps(
            {
                "summary": "I selected an action.",
                "factors": ["Untrusted output"],
                "confidence": 0.5,
                "limitations": ["None"],
                "selected_action": "EXECUTE_RAZORPAY",
            }
        )
    )
    provider = GroqExplanationProvider(
        Settings(_env_file=None, groq_api_key="test-secret")
    )
    provider._client_instance = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=completions)
    )

    with pytest.raises(ExplanationResponseError, match="invalid explanation"):
        await provider.explain_decision_trace({"policy_result": "ALLOWED"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_error",
    [
        RuntimeError("invalid API key"),
        TimeoutError("provider timeout"),
        ConnectionError("network unavailable"),
        ExplanationResponseError("invalid model response"),
    ],
)
async def test_provider_failures_use_deterministic_fallback(
    provider_error: Exception,
) -> None:
    provider = ResilientExplanationProvider(
        FailingProvider(provider_error),
        DeterministicFallbackProvider(),
    )
    assert_provider_contract(provider)
    evidence = {
        "candidate_action": "RETRY_LATER_12H",
        "policy_result": "ALLOWED",
        "failure_reason": "INSUFFICIENT_FUNDS",
    }

    result = await provider.explain_decision_trace(evidence)

    assert isinstance(result, DecisionExplanation)
    assert any("RETRY_LATER_12H" in factor for factor in result.factors)
    assert any("ALLOWED" in factor for factor in result.factors)


@pytest.mark.asyncio
async def test_missing_groq_key_uses_fallback_without_breaking_recovery() -> None:
    settings = Settings(
        _env_file=None,
        explanation_provider="groq",
        groq_api_key=None,
    )
    provider = create_explanation_provider(settings)
    evidence = {
        "candidate_action": "SEND_NUDGE",
        "policy_result": "ALLOWED",
        "recovery_case_status": "OPEN",
    }
    original = deepcopy(evidence)

    result = await provider.explain_recovery_case(evidence)

    assert isinstance(result, DecisionExplanation)
    assert evidence == original
    assert evidence["policy_result"] == "ALLOWED"
    assert evidence["recovery_case_status"] == "OPEN"


def test_explanation_layer_has_no_razorpay_or_execution_dependency() -> None:
    source = "\n".join(
        [
            inspect.getsource(GroqExplanationProvider),
            inspect.getsource(ResilientExplanationProvider),
        ]
    ).casefold()

    assert "razorpay" not in source
    assert "payment_link" not in source
    assert "recoverymodel" not in source
    assert "sequential" not in source
    assert "execute" not in source
