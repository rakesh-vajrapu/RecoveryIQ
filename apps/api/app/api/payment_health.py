import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/payment-health", tags=["Payment Health"])

ARTIFACT_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "artifacts"
    / "detector_v2"
    / "demo-scenario-not-benchmark-v2.json"
)


@router.get("/summary")
async def get_payment_health_summary() -> dict[str, Any]:
    """Returns a static simulation of payment health degradation for the frontend."""
    if not ARTIFACT_PATH.exists():
        raise HTTPException(status_code=404, detail="Payment health artifact unavailable")
    try:
        with open(ARTIFACT_PATH, encoding="utf-8") as f:
            data = dict(json.load(f))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Invalid payment health artifact") from e
    
    return data
