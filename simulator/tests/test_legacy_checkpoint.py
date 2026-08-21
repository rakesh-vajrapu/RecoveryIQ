from __future__ import annotations

import json
from pathlib import Path

from recoveriq_simulator import SIMULATOR_VERSION


def test_phase2_checkpoint_fixture_is_preserved() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "phase2_020_summary.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["baseline_commit"] == "cc8fe0b09877e83758e08eef8c6e1a2d940aa439"
    assert fixture["experiment_id"] == "sim-v020-20260821-4bf5b3384b16"
    assert fixture["scenario_digest"] == (
        "a8c2167e8810517d7874c47fd5dad52439d74dab6b0f7db63d52fc6821f503cf"
    )
    assert fixture["simulator_version"] == "0.2.0"
    assert fixture["simulator_version"] != SIMULATOR_VERSION
