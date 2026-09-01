import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_get_evaluation_summary(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_type"] == "SIMULATED"
    assert "recoveryiq" in data
    assert "primary_baseline" in data
    assert "strategies" in data
    assert len(data["strategies"]) > 0
    assert data["recoveryiq"]["recovery_rate"] > 0
    assert data["primary_baseline"]["recovery_rate"] > 0
    assert "incremental" in data


async def test_get_simulated_decision_example(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/simulated-decision-example")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "SIMULATED"
    assert data["synthetic"] is True
    assert len(data["decisions"]) > 0
