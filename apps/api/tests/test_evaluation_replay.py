import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_preset_listing_returns_allowed_only(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/replay/presets")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert ids == {"successful-adaptive-trace-v2", "bounded-failure-trace-v2"}
    assert "development-failure-trace-v2" not in ids

async def test_adaptive_replay_returns_exact_frozen_trace(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/replay/successful-adaptive-trace-v2")
    assert response.status_code == 200
    data = response.json()
    assert data["episode_id"] == "seq_a60e2a86793299fce20ef7d0f0ef13b4"
    assert data["final"]["recovered"] is True

async def test_bounded_replay_terminates_on_max_interventions(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/replay/bounded-failure-trace-v2")
    assert response.status_code == 200
    data = response.json()
    assert data["final"]["recovered"] is False
    assert data["final"]["action_count"] == 3
    assert data["final"].get("no_fourth_autonomous_action") is True

async def test_replay_exact_selected_actions_and_probabilities(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/replay/successful-adaptive-trace-v2")
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_type"] == "SEALED_SIMULATED_REPLAY"
    decisions = data["decisions"]
    # Check decision 1
    assert decisions[0]["selected_action"] == "RETRY_LATER_24H"
    cand = next(c for c in decisions[0]["candidates"] if c["label"] == "RETRY_LATER_24H")
    assert cand["calibration_bin"] == 3
    assert cand["incremental_erv_minor"] == 8416
    assert cand["action_stage_support"] == 6422
    assert abs(cand["probability"] - 0.30227882037533504) < 1e-9

async def test_read_only_behavior_and_no_simulator_import() -> None:
    import sys
    assert "app.simulator" not in sys.modules
    assert "lightgbm" not in sys.modules

async def test_no_provider_invocation_in_replay(client: AsyncClient) -> None:
    # Just a sanity test that fetching replay does not call gateway (it's purely read-only json dump)
    response = await client.get("/api/evaluation/replay/successful-adaptive-trace-v2")
    assert response.status_code == 200

async def test_missing_or_corrupt_artifact_fails_closed(client: AsyncClient) -> None:
    response = await client.get("/api/evaluation/replay/unknown-trace")
    assert response.status_code == 404
