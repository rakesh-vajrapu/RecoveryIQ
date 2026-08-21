from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampedUuidMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class RecoveryCaseStatus(StrEnum):
    DETECTED = "DETECTED"
    DIAGNOSING = "DIAGNOSING"
    SCORING = "SCORING"
    POLICY_CHECK = "POLICY_CHECK"
    SCHEDULED = "SCHEDULED"
    WAITING = "WAITING"
    EXECUTING = "EXECUTING"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class Merchant(TimestampedUuidMixin, Base):
    __tablename__ = "merchants"

    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    customers: Mapped[list[Customer]] = relationship(back_populates="merchant")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="merchant")
    payments: Mapped[list[Payment]] = relationship(back_populates="merchant")


class Customer(TimestampedUuidMixin, Base):
    __tablename__ = "customers"

    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    anonymous_reference: Mapped[str] = mapped_column(String(100), nullable=False)

    merchant: Mapped[Merchant] = relationship(back_populates="customers")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="customer")
    payments: Mapped[list[Payment]] = relationship(back_populates="customer")


class Subscription(TimestampedUuidMixin, Base):
    __tablename__ = "subscriptions"

    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")

    merchant: Mapped[Merchant] = relationship(back_populates="subscriptions")
    customer: Mapped[Customer] = relationship(back_populates="subscriptions")
    payments: Mapped[list[Payment]] = relationship(back_populates="subscription")


class Payment(TimestampedUuidMixin, Base):
    __tablename__ = "payments"

    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(40), nullable=False)

    merchant: Mapped[Merchant] = relationship(back_populates="payments")
    customer: Mapped[Customer] = relationship(back_populates="payments")
    subscription: Mapped[Subscription] = relationship(back_populates="payments")
    attempts: Mapped[list[PaymentAttempt]] = relationship(back_populates="payment")
    recovery_cases: Mapped[list[RecoveryCase]] = relationship(back_populates="payment")


class PaymentAttempt(TimestampedUuidMixin, Base):
    __tablename__ = "payment_attempts"

    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    payment_method: Mapped[str | None] = mapped_column(String(40))
    issuer: Mapped[str | None] = mapped_column(String(100))
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    payment: Mapped[Payment] = relationship(back_populates="attempts")


class RecoveryCase(TimestampedUuidMixin, Base):
    __tablename__ = "recovery_cases"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id"), nullable=False, unique=True
    )
    status: Mapped[RecoveryCaseStatus] = mapped_column(
        Enum(RecoveryCaseStatus, name="recovery_case_status", native_enum=False),
        default=RecoveryCaseStatus.DETECTED,
        nullable=False,
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid.uuid4, nullable=False, index=True
    )

    payment: Mapped[Payment] = relationship(back_populates="recovery_cases")


class AuditEvent(TimestampedUuidMixin, Base):
    __tablename__ = "audit_events"

    correlation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
