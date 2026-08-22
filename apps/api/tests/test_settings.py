import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_application_settings_do_not_require_external_credentials() -> None:
    settings = Settings(_env_file=None)

    assert settings.gemini_enabled is False
    assert settings.gemini_api_key is None
    assert settings.razorpay_key_secret is None
    assert settings.execution_environment == "SIMULATION"
    assert settings.razorpay_mode == "test"
    assert settings.database_kind == "sqlite"


def test_settings_mask_secrets_in_representations() -> None:
    raw_secret = "must-never-appear"
    settings = Settings(
        _env_file=None,
        gemini_api_key=SecretStr(raw_secret),
        razorpay_key_secret=SecretStr(raw_secret),
        razorpay_webhook_secret=SecretStr(raw_secret),
    )

    assert raw_secret not in repr(settings)
    assert raw_secret not in settings.model_dump_json()


def test_razorpay_live_mode_is_not_a_valid_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, razorpay_mode="live")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, execution_environment="RAZORPAY_LIVE")


def test_live_key_is_rejected_even_in_test_configuration() -> None:
    with pytest.raises(ValidationError, match="only rzp_test_"):
        Settings(_env_file=None, razorpay_key_id=SecretStr("rzp_live_forbidden"))


def test_empty_razorpay_placeholders_are_unconfigured() -> None:
    settings = Settings(
        _env_file=None,
        razorpay_key_id="",
        razorpay_key_secret="",
        razorpay_webhook_secret="",
    )

    assert settings.razorpay_key_id is None
    assert settings.razorpay_api_configured is False
    assert settings.razorpay_webhook_configured is False
