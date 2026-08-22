from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from recoveriq_simulator.observation import (
    PaymentObservation,
    RecoveryAction,
    SubscriptionRecord,
)


class SequentialModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PreviousInterventionResult(StrEnum):
    NONE = "NONE"
    FAILED = "FAILED"


class EpisodeTermination(StrEnum):
    ACTIVE = "ACTIVE"
    RECOVERED = "RECOVERED"
    STOP = "STOP"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    HORIZON_EXHAUSTED = "HORIZON_EXHAUSTED"
    MAX_INTERVENTIONS = "MAX_INTERVENTIONS"
    NO_FEASIBLE_ACTION = "NO_FEASIBLE_ACTION"


class SequentialOperationalProfile(SequentialModel):
    customer_contact_allowed: bool
    alternate_method_available: bool


class SequentialEpisodeTemplate(SequentialModel):
    episode_id: str
    observation: PaymentObservation
    subscription: SubscriptionRecord
    last_success_at: datetime | None
    operational: SequentialOperationalProfile
    initial_active_payment_link: bool


class SequentialEpisodeState(SequentialModel):
    episode_id: str
    decision_index: int = Field(ge=1, le=4)
    decision_at: datetime
    horizon_at: datetime
    intervention_count: int = Field(ge=0, le=3)
    retry_count: int = Field(ge=0, le=2)
    contact_count: int = Field(ge=0, le=2)
    payment_link_count: int = Field(ge=0)
    method_update_count: int = Field(ge=0)
    alternate_method_count: int = Field(ge=0)
    active_payment_link: bool
    method_update_requested: bool
    alternate_method_used: bool
    last_action_label: str = "NONE"
    last_action_type: str = "NONE"
    last_action_executed_at: datetime | None = None
    previous_intervention_result: PreviousInterventionResult = PreviousInterventionResult.NONE
    recovered: bool = False
    recovered_at: datetime | None = None
    recovery_action_id: str | None = None
    recovery_action_label: str | None = None
    recovery_decision_index: int | None = None
    termination: EpisodeTermination = EpisodeTermination.ACTIVE


class SequentialCandidate(SequentialModel):
    label: str
    recovery_action: RecoveryAction
    is_customer_contact: bool
    requests_method_change: bool
    observation_window_hours: float = Field(ge=0)
    quiet_hours_delay_applied: bool = False


class SequentialActionOutcome(SequentialModel):
    episode_id: str
    decision_index: int
    candidate_label: str
    action_id: str
    executed_at: datetime
    recovered: bool
    oracle_probability: float = Field(ge=0, le=1)
    recovered_amount_minor: int = Field(ge=0)


class SequentialAttribution(SequentialModel):
    episode_id: str
    action_id: str
    action_label: str
    decision_index: int
    recovered_at: datetime
    recovered_amount_minor: int = Field(gt=0)
