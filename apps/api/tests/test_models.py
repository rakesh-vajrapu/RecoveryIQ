from app.integrations.razorpay.capabilities import resolve_capability
from app.models import (
    ExecutionCapability,
    ExternalExecutionState,
    PaymentLinkStatus,
    RecoveryCase,
    RecoveryCaseStatus,
)


def test_recovery_case_status_declares_foundation_lifecycle() -> None:
    assert {status.value for status in RecoveryCaseStatus} == {
        "DETECTED",
        "DIAGNOSING",
        "SCORING",
        "POLICY_CHECK",
        "SCHEDULED",
        "WAITING",
        "EXECUTING",
        "RECOVERED",
        "FAILED",
        "STOPPED",
        "HUMAN_REVIEW",
    }


def test_recovery_case_defaults_to_detected() -> None:
    status_default = RecoveryCase.__table__.c.status.default

    assert status_default is not None
    assert status_default.arg is RecoveryCaseStatus.DETECTED


def test_external_execution_and_payment_link_states_are_separate() -> None:
    assert {state.value for state in ExternalExecutionState} == {
        "PLANNED",
        "QUEUED",
        "EXECUTING",
        "SUCCEEDED",
        "FAILED",
        "UNKNOWN",
        "CANCELLED",
    }
    assert {state.value for state in PaymentLinkStatus} == {
        "ISSUED",
        "PAID",
        "PARTIALLY_PAID",
        "EXPIRED",
        "CANCELLED",
    }


def test_execution_capability_registry_does_not_invent_provider_actions() -> None:
    assert resolve_capability("CREATE_PAYMENT_LINK") is ExecutionCapability.REAL_TEST_EXECUTION
    assert resolve_capability("RETRY_LATER_6H") is ExecutionCapability.INTERNAL_SCHEDULE_ONLY
    assert resolve_capability("SEND_NUDGE") is ExecutionCapability.RECOMMENDATION_ONLY
    assert resolve_capability("HIDDEN_ORACLE_ACTION") is ExecutionCapability.SIMULATION_ONLY
    assert resolve_capability("UNRECOGNIZED") is ExecutionCapability.RECOMMENDATION_ONLY
