from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.entities import TimestampedUuidMixin, utc_now


class WebhookProcessingStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


class ProviderConfirmationStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    MISMATCH = "MISMATCH"


class ExecutionCapability(StrEnum):
    REAL_TEST_EXECUTION = "REAL_TEST_EXECUTION"
    INTERNAL_SCHEDULE_ONLY = "INTERNAL_SCHEDULE_ONLY"
    RECOMMENDATION_ONLY = "RECOMMENDATION_ONLY"
    SIMULATION_ONLY = "SIMULATION_ONLY"


class ExternalExecutionState(StrEnum):
    PLANNED = "PLANNED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"


class PaymentLinkStatus(StrEnum):
    ISSUED = "ISSUED"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ExecutionInitiator(StrEnum):
    POLICY = "POLICY"
    OPERATOR_INITIATED = "OPERATOR_INITIATED"


class DecisionKind(StrEnum):
    ACTION = "ACTION"
    STOP = "STOP"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ExecutionMode(StrEnum):
    SIMULATION = "SIMULATION"
    RAZORPAY_TEST = "RAZORPAY_TEST"


class AttributionSource(StrEnum):
    PAYMENT_LINK_PAID = "PAYMENT_LINK_PAID"
    SUBSCRIPTION_CHARGED = "SUBSCRIPTION_CHARGED"


class ExternalOutcomeStatus(StrEnum):
    PAID = "PAID"
    CHARGED = "CHARGED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ExternalWebhookEvent(TimestampedUuidMixin, Base):
    __tablename__ = "external_webhook_events"

    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="RAZORPAY")
    provider_event_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    provider_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[WebhookProcessingStatus] = mapped_column(
        Enum(WebhookProcessingStatus, name="webhook_processing_status", native_enum=False),
        default=WebhookProcessingStatus.RECEIVED,
        nullable=False,
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid.uuid4, nullable=False, index=True
    )
    external_entity_ids: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    redacted_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_confirmation_status: Mapped[ProviderConfirmationStatus] = mapped_column(
        Enum(ProviderConfirmationStatus, name="provider_confirmation_status", native_enum=False),
        default=ProviderConfirmationStatus.NOT_REQUIRED,
        nullable=False,
    )
    provider_confirmation_method: Mapped[str | None] = mapped_column(String(80))
    provider_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalEntityMapping(TimestampedUuidMixin, Base):
    __tablename__ = "external_entity_mappings"
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_entity_type", "external_entity_id", name="uq_external_entity"
        ),
    )

    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="RAZORPAY")
    external_entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    external_entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    local_entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    local_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    last_provider_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FailureEvent(TimestampedUuidMixin, Base):
    __tablename__ = "failure_events"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_cases.id"), nullable=False, index=True
    )
    webhook_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_webhook_events.id"), nullable=False, unique=True
    )
    reason: Mapped[str] = mapped_column(String(120), nullable=False, default="unknown")
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="unknown")
    step: Mapped[str] = mapped_column(String(120), nullable=False, default="unknown")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecoveryDecisionRecord(TimestampedUuidMixin, Base):
    __tablename__ = "recovery_decisions"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_cases.id"), nullable=False, index=True
    )
    decision_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    kind: Mapped[DecisionKind] = mapped_column(
        Enum(DecisionKind, name="recovery_decision_kind", native_enum=False), nullable=False
    )
    selected_action: Mapped[str | None] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False, default="2.0.0")
    policy_version: Mapped[str] = mapped_column(String(30), nullable=False, default="2.0.0")
    feature_schema_version: Mapped[str] = mapped_column(String(30), nullable=False, default="2.0")
    context_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RecoveryExecutionPlan(TimestampedUuidMixin, Base):
    __tablename__ = "recovery_execution_plans"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_cases.id"), nullable=False, index=True
    )
    recovery_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recovery_decisions.id")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    capability: Mapped[ExecutionCapability] = mapped_column(
        Enum(ExecutionCapability, name="execution_capability", native_enum=False), nullable=False
    )
    initiator: Mapped[ExecutionInitiator] = mapped_column(
        Enum(ExecutionInitiator, name="execution_initiator", native_enum=False), nullable=False
    )
    rationale: Mapped[str] = mapped_column(String(300), nullable=False)


class ExternalExecution(TimestampedUuidMixin, Base):
    __tablename__ = "external_executions"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_cases.id"), nullable=False, index=True
    )
    execution_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_execution_plans.id"), nullable=False, unique=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="RAZORPAY")
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        Enum(ExecutionMode, name="external_execution_mode", native_enum=False), nullable=False
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[ExternalExecutionState] = mapped_column(
        Enum(ExternalExecutionState, name="external_execution_state", native_enum=False),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    provider_reference_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    provider_entity_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    payment_link_status: Mapped[PaymentLinkStatus | None] = mapped_column(
        Enum(PaymentLinkStatus, name="payment_link_status", native_enum=False)
    )
    provider_url: Mapped[str | None] = mapped_column(Text)
    failure_category: Mapped[str | None] = mapped_column(String(80))
    failure_reason: Mapped[str | None] = mapped_column(String(300))
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalOutcome(TimestampedUuidMixin, Base):
    __tablename__ = "external_outcomes"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_cases.id"), nullable=False, index=True
    )
    external_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("external_executions.id")
    )
    webhook_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_webhook_events.id"), nullable=False, unique=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="RAZORPAY")
    status: Mapped[ExternalOutcomeStatus] = mapped_column(
        Enum(ExternalOutcomeStatus, name="external_outcome_status", native_enum=False),
        nullable=False,
    )
    verified: Mapped[bool] = mapped_column(nullable=False, default=True)
    external_payment_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    external_payment_link_id: Mapped[str | None] = mapped_column(String(120))
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecoveryAttribution(TimestampedUuidMixin, Base):
    __tablename__ = "recovery_attributions"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_cases.id"), nullable=False, unique=True
    )
    external_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("external_executions.id"), unique=True
    )
    external_outcome_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_outcomes.id"), nullable=False, unique=True
    )
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        Enum(ExecutionMode, name="recovery_attribution_mode", native_enum=False), nullable=False
    )
    external_payment_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    external_payment_link_id: Mapped[str | None] = mapped_column(String(120))
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attribution_source: Mapped[AttributionSource] = mapped_column(
        Enum(AttributionSource, name="attribution_source", native_enum=False), nullable=False
    )
