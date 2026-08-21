from pydantic import SecretStr

from app.core.config import Settings


def test_application_settings_do_not_require_external_credentials() -> None:
    settings = Settings(_env_file=None)

    assert settings.gemini_enabled is False
    assert settings.gemini_api_key is None
    assert settings.razorpay_key_secret is None
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
