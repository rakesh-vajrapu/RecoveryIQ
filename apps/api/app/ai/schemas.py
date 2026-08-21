from pydantic import BaseModel, ConfigDict, Field


class DecisionExplanation(BaseModel):
    """Validated explanation of decision evidence calculated outside the LLM."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1_000)
    key_factors: list[str] = Field(min_length=1, max_length=8)
    uncertainty: str | None = Field(default=None, max_length=300)
