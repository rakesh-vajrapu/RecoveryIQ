from pathlib import Path

from sqlalchemy import inspect

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_database_engine
from app.models import entities  # noqa: F401


def test_sqlite_can_create_foundation_schema(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'schema-test.db'}",
    )
    engine = create_database_engine(settings)

    Base.metadata.create_all(engine)

    assert set(inspect(engine).get_table_names()) == {
        "audit_events",
        "customers",
        "merchants",
        "payment_attempts",
        "payments",
        "recovery_cases",
        "subscriptions",
    }
    engine.dispose()
