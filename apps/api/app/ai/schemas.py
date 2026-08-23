from pydantic import BaseModel, ConfigDict, Field


class DecisionExplanation(BaseModel):
    """Validated explanation of decision evidence calculated outside the LLM."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1_000)
    factors: list[str] = Field(min_length=1, max_length=8)
    confidence: float = Field(
        ge=0,
        le=1,
        description=(
            "Confidence that the explanation reflects supplied evidence; "
            "not a recovery probability."
        ),
    )
    limitations: list[str] = Field(min_length=1, max_length=8)
