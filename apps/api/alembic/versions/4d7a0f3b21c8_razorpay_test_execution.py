"""Razorpay Test Mode execution boundary

Revision ID: 4d7a0f3b21c8
Revises: 8f2390123d94
Create Date: 2026-08-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4d7a0f3b21c8"
down_revision: str | Sequence[str] | None = "8f2390123d94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add durable Test Mode ingestion, execution, and attribution records."""
    op.create_table(
        "external_webhook_events",
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_event_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "processing_status",
            sa.Enum(
                "RECEIVED",
                "PROCESSING",
                "PROCESSED",
                "IGNORED",
                "FAILED",
                name="webhook_processing_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("external_entity_ids", sa.JSON(), nullable=False),
        sa.Column("redacted_payload", sa.JSON(), nullable=False),
        sa.Column("failure_reason", sa.String(length=200), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id"),
    )
    with op.batch_alter_table("external_webhook_events", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_external_webhook_events_correlation_id"),
            ["correlation_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_external_webhook_events_event_type"), ["event_type"], unique=False
        )

    op.create_table(
        "external_entity_mappings",
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("external_entity_type", sa.String(length=60), nullable=False),
        sa.Column("external_entity_id", sa.String(length=120), nullable=False),
        sa.Column("local_entity_type", sa.String(length=60), nullable=False),
        sa.Column("local_entity_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("last_provider_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "external_entity_type", "external_entity_id", name="uq_external_entity"
        ),
    )
    with op.batch_alter_table("external_entity_mappings", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_external_entity_mappings_correlation_id"),
            ["correlation_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_external_entity_mappings_local_entity_id"),
            ["local_entity_id"],
            unique=False,
        )

    op.create_table(
        "recovery_decisions",
        sa.Column("recovery_case_id", sa.Uuid(), nullable=False),
        sa.Column("decision_key", sa.String(length=160), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "ACTION",
                "STOP",
                "HUMAN_REVIEW",
                name="recovery_decision_kind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("selected_action", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.String(length=160), nullable=False),
        sa.Column("model_version", sa.String(length=30), nullable=False),
        sa.Column("policy_version", sa.String(length=30), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=30), nullable=False),
        sa.Column("context_metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_case_id"], ["recovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_key"),
    )
    with op.batch_alter_table("recovery_decisions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_recovery_decisions_recovery_case_id"),
            ["recovery_case_id"],
            unique=False,
        )

    op.create_table(
        "failure_events",
        sa.Column("recovery_case_id", sa.Uuid(), nullable=False),
        sa.Column("webhook_event_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("step", sa.String(length=120), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_case_id"], ["recovery_cases.id"]),
        sa.ForeignKeyConstraint(["webhook_event_id"], ["external_webhook_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("webhook_event_id"),
    )
    with op.batch_alter_table("failure_events", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_failure_events_recovery_case_id"),
            ["recovery_case_id"],
            unique=False,
        )

    op.create_table(
        "recovery_execution_plans",
        sa.Column("recovery_case_id", sa.Uuid(), nullable=False),
        sa.Column("recovery_decision_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column(
            "capability",
            sa.Enum(
                "REAL_TEST_EXECUTION",
                "INTERNAL_SCHEDULE_ONLY",
                "RECOMMENDATION_ONLY",
                "SIMULATION_ONLY",
                name="execution_capability",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "initiator",
            sa.Enum(
                "POLICY",
                "OPERATOR_INITIATED",
                name="execution_initiator",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("rationale", sa.String(length=300), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_case_id"], ["recovery_cases.id"]),
        sa.ForeignKeyConstraint(["recovery_decision_id"], ["recovery_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("recovery_execution_plans", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_recovery_execution_plans_recovery_case_id"),
            ["recovery_case_id"],
            unique=False,
        )

    op.create_table(
        "external_executions",
        sa.Column("recovery_case_id", sa.Uuid(), nullable=False),
        sa.Column("execution_plan_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column(
            "execution_mode",
            sa.Enum(
                "SIMULATION",
                "RAZORPAY_TEST",
                name="external_execution_mode",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "PLANNED",
                "QUEUED",
                "EXECUTING",
                "SUCCEEDED",
                "FAILED",
                "UNKNOWN",
                "CANCELLED",
                name="external_execution_state",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("provider_reference_id", sa.String(length=40), nullable=False),
        sa.Column("provider_entity_id", sa.String(length=120), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "payment_link_status",
            sa.Enum(
                "ISSUED",
                "PAID",
                "PARTIALLY_PAID",
                "EXPIRED",
                "CANCELLED",
                name="payment_link_status",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("provider_url", sa.Text(), nullable=True),
        sa.Column("failure_category", sa.String(length=80), nullable=True),
        sa.Column("failure_reason", sa.String(length=300), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_plan_id"], ["recovery_execution_plans.id"]),
        sa.ForeignKeyConstraint(["recovery_case_id"], ["recovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_plan_id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("provider_entity_id"),
        sa.UniqueConstraint("provider_reference_id"),
    )
    with op.batch_alter_table("external_executions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_external_executions_recovery_case_id"),
            ["recovery_case_id"],
            unique=False,
        )

    op.create_table(
        "external_outcomes",
        sa.Column("recovery_case_id", sa.Uuid(), nullable=False),
        sa.Column("external_execution_id", sa.Uuid(), nullable=True),
        sa.Column("webhook_event_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PAID",
                "CHARGED",
                "PARTIALLY_PAID",
                "EXPIRED",
                "CANCELLED",
                name="external_outcome_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("external_payment_id", sa.String(length=120), nullable=True),
        sa.Column("external_payment_link_id", sa.String(length=120), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_execution_id"], ["external_executions.id"]),
        sa.ForeignKeyConstraint(["recovery_case_id"], ["recovery_cases.id"]),
        sa.ForeignKeyConstraint(["webhook_event_id"], ["external_webhook_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_payment_id"),
        sa.UniqueConstraint("webhook_event_id"),
    )
    with op.batch_alter_table("external_outcomes", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_external_outcomes_recovery_case_id"),
            ["recovery_case_id"],
            unique=False,
        )

    op.create_table(
        "recovery_attributions",
        sa.Column("recovery_case_id", sa.Uuid(), nullable=False),
        sa.Column("external_execution_id", sa.Uuid(), nullable=True),
        sa.Column("external_outcome_id", sa.Uuid(), nullable=False),
        sa.Column(
            "execution_mode",
            sa.Enum(
                "SIMULATION",
                "RAZORPAY_TEST",
                name="recovery_attribution_mode",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("external_payment_id", sa.String(length=120), nullable=True),
        sa.Column("external_payment_link_id", sa.String(length=120), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attribution_source",
            sa.Enum(
                "PAYMENT_LINK_PAID",
                "SUBSCRIPTION_CHARGED",
                name="attribution_source",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_execution_id"], ["external_executions.id"]),
        sa.ForeignKeyConstraint(["external_outcome_id"], ["external_outcomes.id"]),
        sa.ForeignKeyConstraint(["recovery_case_id"], ["recovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_execution_id"),
        sa.UniqueConstraint("external_outcome_id"),
        sa.UniqueConstraint("external_payment_id"),
        sa.UniqueConstraint("recovery_case_id"),
    )


def downgrade() -> None:
    """Remove the Test Mode integration records."""
    op.drop_table("recovery_attributions")
    with op.batch_alter_table("external_outcomes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_external_outcomes_recovery_case_id"))
    op.drop_table("external_outcomes")
    with op.batch_alter_table("external_executions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_external_executions_recovery_case_id"))
    op.drop_table("external_executions")
    with op.batch_alter_table("recovery_execution_plans", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_recovery_execution_plans_recovery_case_id"))
    op.drop_table("recovery_execution_plans")
    with op.batch_alter_table("failure_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_failure_events_recovery_case_id"))
    op.drop_table("failure_events")
    with op.batch_alter_table("recovery_decisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_recovery_decisions_recovery_case_id"))
    op.drop_table("recovery_decisions")
    with op.batch_alter_table("external_entity_mappings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_external_entity_mappings_local_entity_id"))
        batch_op.drop_index(batch_op.f("ix_external_entity_mappings_correlation_id"))
    op.drop_table("external_entity_mappings")
    with op.batch_alter_table("external_webhook_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_external_webhook_events_event_type"))
        batch_op.drop_index(batch_op.f("ix_external_webhook_events_correlation_id"))
    op.drop_table("external_webhook_events")
