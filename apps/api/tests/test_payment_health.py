import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

@pytest.mark.asyncio
async def test_payment_health_summary():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/payment-health/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["label"] == "DEMO SCENARIO — NOT BENCHMARK DATA"
        assert data["benchmark_data"] is False
        
        # Check final context for detector version and scopes
        fc = data["final_context"]
        assert fc["context_version"] == "2.0"
        
        # Verify supported scopes
        assert "global_health" in fc
        assert "issuer_health" in fc
        assert "method_health" in fc
        
        # Verify advisory-only authority (hard_policy_gate_passed = false)
        assert fc["confirmed_hard_policy_gate_passed"] is False
