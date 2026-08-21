from app.celery_app import celery_app, health_ping


def test_health_ping_executes_in_eager_mode() -> None:
    assert celery_app.conf.task_always_eager is True

    result = health_ping.delay().get(timeout=2)

    assert result == {"status": "ok", "service": "recoveriq-worker"}
