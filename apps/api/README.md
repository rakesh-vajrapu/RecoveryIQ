# RecoverIQ API

Run `uv sync --dev`, apply migrations with `uv run alembic upgrade head`, and start with `uv run uvicorn app.main:app --reload`. The default configuration uses a local SQLite database and eager Celery tasks; see the repository `.env.example` for full-environment settings.

