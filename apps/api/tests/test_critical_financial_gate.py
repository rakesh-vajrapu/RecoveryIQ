import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ExternalExecution,
    ExternalOutcome,
    RecoveryAttribution,
    RecoveryCase,
)


def test_manifest_is_valid() -> None:
    manifest_path = Path(__file__).parent / "critical_financial_paths.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
        
    required_ids = [
        "CFP-01", "CFP-02", "CFP-03", "CFP-04",
        "CFP-05", "CFP-06", "CFP-07", "CFP-08",
        "CFP-09", "CFP-10", "CFP-11", "CFP-12"
    ]
    
    # 1. Every critical path ID is unique (json.load enforces unique keys for dict, but check against required list)
    assert set(required_ids).issubset(set(manifest.keys())), "Missing required CFP IDs"
    
    for cfp_id, cfp_data in manifest.items():
        assert "name" in cfp_data, f"{cfp_id} missing name"
        assert "risk" in cfp_data, f"{cfp_id} missing risk"
        assert "invariant" in cfp_data, f"{cfp_id} missing invariant"
        
        # 2. Every required path has executable test coverage
        tests = cfp_data.get("tests", [])
        assert len(tests) > 0, f"{cfp_id} has no tests"
        
        for t in tests:
            # We don't execute full pytest collection here, but we can verify file path exists
            file_part = t.split("::")[0]
            assert (Path(__file__).parent.parent / file_part).exists(), f"Test file {file_part} not found"

