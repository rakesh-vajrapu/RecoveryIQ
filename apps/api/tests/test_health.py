import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_reports_safe_runtime_state(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "recoveriq-api",
        "status": "healthy",
        "environment": "test",
        "database": "sqlite",
        "gemini_enabled": False,
        "celery_eager": True,
    }


@pytest.mark.asyncio
async def test_health_response_contains_no_secret_fields(client: AsyncClient) -> None:
    response_body = (await client.get("/health")).json()

    assert not any("key" in field or "secret" in field for field in response_body)
