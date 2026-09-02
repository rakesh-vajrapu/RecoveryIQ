import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio


async def test_get_governance_profile(client: AsyncClient) -> None:
    response = await client.get("/api/governance/profile")
    assert response.status_code == 200
    data = response.json()

    assert data["policy_version"] == "2.0.0"
    assert data["model_version"] == "2.0.0"
    assert data["config_hash"] == "ce7712b1ee4e800d54a875eb65a7bc826680e59faa465b54cbc1db7472010b25"
    assert data["evidence_lane"] == "SEALED_SIMULATED"

    limits = data["limits"]
    assert limits["recovery_horizon_hours"] == 48.0
    assert limits["max_autonomous_interventions"] == 3
    assert limits["max_retries"] == 2
    assert limits["max_contacts"] == 2
    assert limits["minimum_retry_interval_hours"] == 2.0

    authority = data["authority"]
    assert authority["model"] == "ESTIMATES"
    assert authority["erv"] == "RANKS"
    assert authority["policy"] == "AUTHORIZES"
    assert authority["provider"] == "VERIFIES"
    assert authority["llm"] == "EXPLAINS_ONLY"

    rules = data["rules"]
    assert len(rules) == 16

    rule_ids = {r["id"] for r in rules}
    assert "CUSTOMER_OPT_OUT" in rule_ids
    assert "MODEL_SUPPORT" in rule_ids
    assert "NON_POSITIVE_INCREMENTAL_ERV" in rule_ids
    assert "BUDGETS_EXHAUSTED" in rule_ids

    # Check semantics
    for rule in rules:
        if rule["id"] in [
            "MODEL_SCHEMA_VALID",
            "MODEL_SUPPORT",
            "CALIBRATION_SUPPORT",
            "LOW_DECISION_MARGIN"
        ]:
            assert rule["enforcement"] == "HUMAN_REVIEW"
        elif rule["id"] in ["ATTRIBUTION_ONCE"]:
            assert rule["enforcement"] == "ACCOUNTING_INVARIANT"


def test_missing_artifact(tmp_path: Path) -> None:
    # Patch the Path.exists to return False
    with patch("app.api.governance.Path.exists", return_value=False):
        client = TestClient(app)
        response = client.get("/api/governance/profile")
        assert response.status_code == 500
        assert "is missing" in response.json()["detail"]


def test_corrupt_artifact() -> None:
    # Mock open and read corrupt JSON
    from unittest.mock import mock_open
    m = mock_open(read_data="{ bad json }")
    with patch("app.api.governance.Path.exists", return_value=True), patch("builtins.open", m):
        client = TestClient(app)
        response = client.get("/api/governance/profile")
        assert response.status_code == 500
        assert "is corrupt" in response.json()["detail"]


def test_invalid_schema() -> None:
    # Valid JSON, but missing required fields
    valid_json_invalid_schema = '{"policy_version": "2.0.0"}'
    from unittest.mock import mock_open
    m = mock_open(read_data=valid_json_invalid_schema)
    with patch("app.api.governance.Path.exists", return_value=True), patch("builtins.open", m):
        client = TestClient(app)
        response = client.get("/api/governance/profile")
        assert response.status_code == 500
        assert "schema" in response.json()["detail"]


def test_invalid_artifact_type() -> None:
    # Valid JSON, correct schema, wrong artifact_type
    valid_json = json.dumps({
        "artifact_type": "WRONG_TYPE",
        "policy_version": "2.0.0",
        "model_version": "2.0.0",
        "config_hash": "abc",
        "cost_regime": "BALANCED",
        "horizon_hours": 48.0,
        "max_interventions": 3,
        "max_retries": 2,
        "max_contacts": 2,
        "min_retry_interval_hours": 2.0,
        "stopping_rules": [],
        "validation_status": "VALIDATED"
    })
    from unittest.mock import mock_open
    m = mock_open(read_data=valid_json)
    with patch("app.api.governance.Path.exists", return_value=True), patch("builtins.open", m):
        client = TestClient(app)
        response = client.get("/api/governance/profile")
        assert response.status_code == 500
        assert "artifact_type" in response.json()["detail"]


def test_cwd_independence() -> None:
    """Test that the API works even if the current working directory changes."""
    original_cwd = os.getcwd()
    try:
        # Change to a completely different directory, e.g. root
        os.chdir(os.path.abspath(os.sep))
        client = TestClient(app)
        response = client.get("/api/governance/profile")
        assert response.status_code == 200
        assert response.json()["policy_version"] == "2.0.0"
    finally:
        os.chdir(original_cwd)
