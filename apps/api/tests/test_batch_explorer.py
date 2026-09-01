import json
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.main import app

client = TestClient(app)


def test_get_batch_explorer_success(monkeypatch: MonkeyPatch) -> None:
    import app.api.batch_explorer

    # Mock the artifact path to a fake successful artifact
    fake_artifact = Path(__file__).parent / "fixtures" / "fake_evaluation.json"
    fake_artifact.parent.mkdir(parents=True, exist_ok=True)
    fake_data = {
        "artifact_type": "sequential_policy_v2_one_time_validation",
        "full_horizon_evaluation": {
            "strategies": {
                "recoveriq_sequential_erv_v2": {
                    "episodes": 100,
                    "recovered_episodes": 75,
                    "recovery_rate": 0.75,
                    "simulated_gross_recovered_amount_minor": 1000,
                    "simulated_net_recovery_value_minor": 900,
                    "friction_cost_minor": 10,
                    "intervention_cost_minor": 20,
                    "customer_contacts": 50,
                    "retry_count": 60,
                    "human_reviews": 5,
                    "stop_outcomes": 10,
                    "policy_violations": 0,
                    "payment_links": 20,
                    "alternate_methods": 15,
                    "method_updates": 10,
                    "mean_actions_per_episode": 1.5,
                    "mean_recovery_time_hours": 12.5,
                    "friction_efficiency": {"contacts_per_recovered_payment": 0.5},
                },
                "reminder_retry_workflow": {
                    "recovery_rate": 0.5,
                    "simulated_net_recovery_value_minor": 500,
                },
            },
            "personalization_analysis": {
                "failure_reason": [
                    {"value": "AUTH_FAILURE", "episodes": 40, "recovery_rate": 0.8},
                    {"value": "INSUFFICIENT_FUNDS", "episodes": 60, "recovery_rate": 0.7},
                ],
                "payment_method": [],
                "amount_bucket": [],
                "prior_success_bucket": [],
                "subscription_tenure_bucket": [],
            },
        },
    }
    fake_artifact.write_text(json.dumps(fake_data), encoding="utf-8")

    monkeypatch.setattr(app.api.batch_explorer, "ARTIFACT_PATH", fake_artifact)

    response = client.get("/api/evaluation/batch-explorer")
    assert response.status_code == 200
    data = response.json()

    assert data["evidence_type"] == "SEALED_SIMULATED"
    assert data["episodes"] == 100
    assert data["portfolio"]["recovered_episodes"] == 75
    assert data["portfolio"]["recovery_rate"] == 0.75

    # Invariant: recovered_episodes <= episodes
    assert data["portfolio"]["recovered_episodes"] <= data["episodes"]

    # Invariant: recovery_rate = recovered_episodes / episodes
    assert (
        data["portfolio"]["recovery_rate"]
        == data["portfolio"]["recovered_episodes"] / data["episodes"]
    )

    # Check cohort sums
    failure_reasons = data["cohorts"]["failure_reason"]
    total_cohort_episodes = sum(c["episodes"] for c in failure_reasons)
    assert total_cohort_episodes == data["episodes"]

    assert data["baseline_comparison"]["incremental_recovery_rate_pp"] == 25.0
    assert data["baseline_comparison"]["incremental_net_value_minor"] == 400

    fake_artifact.unlink()


def test_get_batch_explorer_missing(monkeypatch: MonkeyPatch) -> None:
    import app.api.batch_explorer

    fake_artifact = Path(__file__).parent / "fixtures" / "does_not_exist_eval.json"
    monkeypatch.setattr(app.api.batch_explorer, "ARTIFACT_PATH", fake_artifact)

    response = client.get("/api/evaluation/batch-explorer")
    assert response.status_code == 404


def test_get_batch_explorer_invalid_schema(monkeypatch: MonkeyPatch) -> None:
    import app.api.batch_explorer

    fake_artifact = Path(__file__).parent / "fixtures" / "fake_invalid_eval.json"
    fake_artifact.parent.mkdir(parents=True, exist_ok=True)
    fake_artifact.write_text(json.dumps({"wrong": "schema"}), encoding="utf-8")

    monkeypatch.setattr(app.api.batch_explorer, "ARTIFACT_PATH", fake_artifact)

    response = client.get("/api/evaluation/batch-explorer")
    assert response.status_code == 500

    fake_artifact.unlink()
