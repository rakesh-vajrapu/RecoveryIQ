import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

pytestmark = pytest.mark.asyncio

async def test_get_razorpay_evidence_success():
    response = client.get("/api/integrations/razorpay/evidence")
    assert response.status_code == 200
    data = response.json()
    
    assert data["evidence_type"] == "RAZORPAY_TEST_MODE"
    assert data["no_real_money"] is True
    assert data["all_time_recovered_minor"] >= 200
    assert data["last_7_days_recovered_minor"] == 100
    
    selected_case = data["selected_case"]
    assert selected_case is not None
    assert selected_case["case_id"] == "40ebd35f-6c4c-4bb5-b7b5-a25914393528"
    assert selected_case["status"] == "RECOVERED"
    assert selected_case["amount_minor"] == 100
    assert selected_case["execution_initiator"] == "OPERATOR_INITIATED"
    
    # Check outcomes
    assert len(selected_case["outcomes"]) == 1
    assert selected_case["outcomes"][0]["status"] == "PAID"
    assert selected_case["outcomes"][0]["verified"] is True
    
    # Check attribution
    assert selected_case["attribution"] is not None
    assert selected_case["attribution"]["amount_minor"] == 100
    assert selected_case["attribution"]["attribution_source"] == "PAYMENT_LINK_PAID"
    
    # Check executions
    assert len(selected_case["executions"]) == 1
    assert selected_case["executions"][0]["action"] == "CREATE_PAYMENT_LINK"
    
    # Check failed attempts
    assert len(selected_case["failed_attempts"]) >= 1
    
    # Ensure no secrets leak
    assert "webhook_secret" not in str(data).lower()
    assert "hmac" not in selected_case["webhooks"][0].get("raw_payload", "")
