# RecoverIQ API

Run `uv sync --dev --locked`, apply migrations with `uv run alembic upgrade head`, and start with `uv run uvicorn app.main:app --reload`. The default configuration uses SQLite, eager Celery tasks, `SIMULATION`, and no external credentials.

Phase 7 adds an optional Razorpay Test Mode boundary. See [Razorpay Integration](../../docs/RAZORPAY_INTEGRATION.md) and the [Test Demo Runbook](../../docs/RAZORPAY_TEST_DEMO.md). Live Mode is not implemented. The opt-in smoke command is `uv run python -m app.integrations.razorpay.smoke`; it refuses to run unless Test Mode, credentials, and `RAZORPAY_TEST_SMOKE_ENABLED=true` are all explicit.
