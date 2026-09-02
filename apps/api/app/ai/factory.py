from app.ai.fallback import DeterministicFallbackProvider
from app.ai.groq import GroqExplanationProvider
from app.ai.provider import ExplanationProvider
from app.ai.resilient import ResilientExplanationProvider
from app.core.config import Settings


def create_explanation_provider(settings: Settings) -> ExplanationProvider:
    """Build the configured optional enrichment provider with safe fallback."""
    fallback = DeterministicFallbackProvider()
    if settings.explanation_provider == "groq":
        return ResilientExplanationProvider(
            GroqExplanationProvider(settings),
            fallback,
        )
    return fallback
