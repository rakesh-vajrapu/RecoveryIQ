from app.models import RecoveryCase, RecoveryCaseStatus


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
