"""Structured evaluation outputs and aggregate metrics."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from recoveriq_simulator.enums import ActionType


class FrozenResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecoveryAttribution(FrozenResult):
    payment_id: str
    action_id: str
    action_type: ActionType
    recovered_at: datetime
    recovered_amount_minor: int


class PaymentPolicyOutcome(FrozenResult):
    policy_name: str
    payment_id: str
    failed_amount_minor: int
    recovered: bool
    recovery_action: ActionType | None
    recovered_at: datetime | None
    time_to_recovery_hours: float | None
    retry_count: int
    nudge_count: int
    customer_contacts: int
    payment_link_count: int
    human_review_count: int
    action_count: int
    intervention_cost_minor: int
    friction_cost_minor: int
    stopped: bool
    executed_action_counts: dict[str, int]


class BaselineMetrics(FrozenResult):
    policy_name: str
    failed_payment_count: int
    recovered_payment_count: int
    failed_amount_minor: int
    gross_recovered_amount_minor: int
    net_recovered_value_minor: int
    recovery_rate: float
    value_recovery_rate: float
    retry_count: int
    nudge_count: int
    customer_contact_count: int
    payment_link_count: int
    human_review_count: int
    intervention_cost_minor: int
    friction_cost_minor: int
    average_actions_per_failed_payment: float
    average_actions_per_recovered_payment: float
    average_time_to_recovery_hours: float | None
    action_counts: dict[str, int]
    action_success_counts: dict[str, int]


class PolicyEvaluation(FrozenResult):
    policy_name: str
    outcomes: tuple[PaymentPolicyOutcome, ...]
    attributions: tuple[RecoveryAttribution, ...]
    metrics: BaselineMetrics


class BenchmarkResult(FrozenResult):
    experiment_id: str
    simulator_version: str
    seed: int
    policies: tuple[PolicyEvaluation, ...]
