from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.integrations.razorpay.gateway import RazorpayGateway
from app.models import (
    ExternalExecution,
    ExternalExecutionState,
    RecoveryCase,
    RecoveryCaseStatus,
)
from app.models.entities import utc_now
from app.services.audit import add_audit_event
from app.services.razorpay_execution import reconcile_unknown_execution

logger = structlog.get_logger()


def sweep_stale_external_executions(
    session: Session,
    gateway: RazorpayGateway,
    timeout_minutes: int = 15,
    now: datetime | None = None,
) -> dict[str, int]:
    """
    Finds and resolves stale ExternalExecution reservations deterministically.
    Uses atomic Compare-And-Swap (CAS) to claim ownership and prevent races with executors.
    """
    if now is None:
        now = utc_now()

    threshold = now - timedelta(minutes=timeout_minutes)

    # 1. Sweep stale PRE-DISPATCH (PLANNED) executions
    # We can mathematically prove no provider action was taken because it never reached EXECUTING
    planned_executions = session.scalars(
        select(ExternalExecution)
        .where(ExternalExecution.state == ExternalExecutionState.PLANNED)
        .where(ExternalExecution.created_at < threshold)
    ).all()

    pre_dispatch_swept = 0
    for execution in planned_executions:
        # Atomic CAS: Try to claim this specific execution from PLANNED -> FAILED
        rowcount = session.execute(
            update(ExternalExecution)
            .where(ExternalExecution.id == execution.id)
            .where(ExternalExecution.state == ExternalExecutionState.PLANNED)
            .values(
                state=ExternalExecutionState.FAILED,
                failure_category="STALE_RESERVATION",
                failure_reason="Stale execution reservation swept before provider dispatch",
                updated_at=now,
            )
        ).rowcount  # type: ignore[attr-defined]

        if rowcount == 1:
            pre_dispatch_swept += 1
            session.refresh(execution)
            recovery_case = session.get(RecoveryCase, execution.recovery_case_id)
            if recovery_case:
                recovery_case.status = RecoveryCaseStatus.FAILED

            add_audit_event(
                session,
                correlation_id=recovery_case.correlation_id if recovery_case and recovery_case.correlation_id else execution.id,
                entity_type="ExternalExecution",
                entity_id=execution.id,
                actor="STALE_RESERVATION_SWEEPER",
                event_type="STALE_EXECUTION_SWEPT_BEFORE_DISPATCH",
                metadata={"previous_state": "PLANNED", "age_minutes": timeout_minutes},
            )
            session.commit()
            logger.info("stale_execution_swept_before_dispatch", execution_id=str(execution.id))
        else:
            session.rollback()

    # 2. Sweep stale POST-DISPATCH (EXECUTING) executions
    # Provider action may have happened. Must reconcile.
    executing_executions = session.scalars(
        select(ExternalExecution)
        .where(ExternalExecution.state == ExternalExecutionState.EXECUTING)
        .where(ExternalExecution.requested_at < threshold)
    ).all()

    post_dispatch_swept = 0
    for execution in executing_executions:
        # Atomic CAS: Try to claim this specific execution from EXECUTING -> UNKNOWN
        rowcount = session.execute(
            update(ExternalExecution)
            .where(ExternalExecution.id == execution.id)
            .where(ExternalExecution.state == ExternalExecutionState.EXECUTING)
            .values(
                state=ExternalExecutionState.UNKNOWN,
                updated_at=now,
            )
        ).rowcount  # type: ignore[attr-defined]

        if rowcount == 1:
            post_dispatch_swept += 1
            session.refresh(execution)
            recovery_case = session.get(RecoveryCase, execution.recovery_case_id)
            add_audit_event(
                session,
                correlation_id=recovery_case.correlation_id if recovery_case and recovery_case.correlation_id else execution.id,
                entity_type="ExternalExecution",
                entity_id=execution.id,
                actor="STALE_RESERVATION_SWEEPER",
                event_type="STALE_EXECUTION_MARKED_UNKNOWN",
                metadata={"previous_state": "EXECUTING", "age_minutes": timeout_minutes},
            )
            session.commit()
            logger.info("stale_execution_marked_unknown", execution_id=str(execution.id))

            # Invoke reconciliation logic
            reconcile_unknown_execution(session, execution=execution, gateway=gateway)
        else:
            session.rollback()

    return {
        "pre_dispatch_swept": pre_dispatch_swept,
        "post_dispatch_swept": post_dispatch_swept,
    }
