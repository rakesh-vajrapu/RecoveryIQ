import json
from pathlib import Path
from typing import Any


def reject_duplicates(ordered_pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """JSON object_pairs_hook that rejects duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValueError(f"Duplicate key found in manifest: {k}")
        d[k] = v
    return d


def test_manifest_is_valid() -> None:
    manifest_path = Path(__file__).parent / "critical_financial_paths.json"
    with open(manifest_path, encoding="utf-8") as f:
        # 1. Enforce strict JSON uniqueness at load time
        manifest = json.load(f, object_pairs_hook=reject_duplicates)

    required_ids = [
        "CFP-01",
        "CFP-02",
        "CFP-03",
        "CFP-04",
        "CFP-05",
        "CFP-06",
        "CFP-07",
        "CFP-08",
        "CFP-09",
        "CFP-10",
        "CFP-11",
        "CFP-12",
    ]

    # 2. Assert exact set match, no extra or missing IDs allowed
    assert set(manifest.keys()) == set(required_ids), "Exact IDs required"

    for cfp_id, cfp_data in manifest.items():
        assert "name" in cfp_data, f"{cfp_id} missing name"
        assert "risk" in cfp_data, f"{cfp_id} missing risk"
        assert "invariant" in cfp_data, f"{cfp_id} missing invariant"

        # 3. Every required path has mapped test coverage
        tests = cfp_data.get("tests", [])
        assert len(tests) > 0, f"{cfp_id} has no tests"

        for t in tests:
            # 4. Static verification of test file existence. 
            # Note: Static validation alone does not prove the exact test function exists.
            # Exact node-ID validity is guaranteed by the canonical gate execution.
            file_part = t.split("::")[0]
            assert (Path(__file__).parent.parent / file_part).exists(), (
                f"Test file {file_part} not found"
            )
