import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/safety", tags=["Safety"])

# Path to the generated artifact
ARTIFACT_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "apps"
    / "api"
    / "artifacts"
    / "demo"
    / "safety-verification.json"
)


@router.get("/summary")
async def get_safety_summary() -> dict[str, Any]:
    """
    Read-only API that serves the sanitized generated safety evidence.
    It does not mutate the database, trigger chaos, or execute shell commands.
    """
    if not ARTIFACT_PATH.exists():
        raise HTTPException(status_code=404, detail="Safety evidence unavailable")

    try:
        with open(ARTIFACT_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Invalid safety artifact") from e

    schema_version = data.get("schema_version")
    if not schema_version or schema_version != "1.0":
        raise HTTPException(status_code=500, detail="Unsupported safety artifact schema")

    return data
