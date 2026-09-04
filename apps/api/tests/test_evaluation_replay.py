import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_get_replay_presets_returns_list(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/replay/presets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    ids = {item["id"] for item in data}
    assert "successful-adaptive-trace-v2" in ids
    assert "bounded-failure-trace-v2" in ids


async def test_get_replay_trace_returns_trace(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/replay/successful-adaptive-trace-v2")
    assert response.status_code == 200
    data = response.json()
    assert "episode_id" in data
    assert "initial_failure" in data
    assert "decisions" in data


async def test_get_replay_trace_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/replay/unknown-trace")
    assert response.status_code == 404
