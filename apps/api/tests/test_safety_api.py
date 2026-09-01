import json
from pathlib import Path
from pytest import MonkeyPatch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_safety_summary_success(monkeypatch: MonkeyPatch) -> None:
    import app.api.safety

    # Mock the artifact path to a fake successful artifact
    fake_artifact = Path(__file__).parent / "fixtures" / "fake_safety.json"
    fake_artifact.write_text(json.dumps({"schema_version": "1.0", "data": "ok"}))

    monkeypatch.setattr(app.api.safety, "ARTIFACT_PATH", fake_artifact)

    response = client.get("/api/safety/summary")
    assert response.status_code == 200
    assert response.json() == {"schema_version": "1.0", "data": "ok"}

    # Cleanup
    fake_artifact.unlink()


def test_get_safety_summary_missing(monkeypatch: MonkeyPatch) -> None:
    import app.api.safety

    fake_artifact = Path(__file__).parent / "fixtures" / "does_not_exist.json"
    monkeypatch.setattr(app.api.safety, "ARTIFACT_PATH", fake_artifact)

    response = client.get("/api/safety/summary")
    assert response.status_code == 404


def test_get_safety_summary_invalid_schema(monkeypatch: MonkeyPatch) -> None:
    import app.api.safety

    fake_artifact = Path(__file__).parent / "fixtures" / "fake_invalid.json"
    fake_artifact.write_text(json.dumps({"schema_version": "2.0"}))
    monkeypatch.setattr(app.api.safety, "ARTIFACT_PATH", fake_artifact)

    response = client.get("/api/safety/summary")
    assert response.status_code == 500
    assert "Unsupported" in response.json()["detail"]

    fake_artifact.unlink()
