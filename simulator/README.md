# RecoverIQ Simulator

This standalone Python package contains the deterministic Phase 2/2.5 payment environment, validation reports, fixed-policy baselines, the frozen Phase 3 detector-v1 benchmark, and the separate Phase 3.5 observable-only detector v2. It intentionally has no dependency on the API, Gemini, Razorpay, or future recovery ML.

From the repository root:

```powershell
uv sync --project simulator --dev
uv run --project simulator python -m recoveriq_simulator.cli benchmark --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli benchmark-suite --group development
uv run --project simulator python -m recoveriq_simulator.cli benchmark-suite --group validation
uv run --project simulator python -m recoveriq_simulator.cli quality-report --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli sensitivity
uv run --project simulator python -m recoveriq_simulator.cli inspect <experiment-id>
uv run --project simulator python -m recoveriq_detector_v2.cli replay --seed 20260901
uv run --project simulator python -m recoveriq_detector_v2.cli demo
uv run --project simulator python -m recoveriq_detector_v2.cli summary
```

Generated datasets and bulky replay reports below `artifacts/` are ignored by Git; frozen configurations and compact evidence summaries are versioned. Detector-v2 validation refuses to overwrite its one-time result, consumed detector-v1 validation seeds are forbidden to v2 commands, and final evaluation seeds remain reserved. See `docs/SIMULATOR.md`, `docs/SIMULATOR_VALIDATION.md`, and `docs/DEGRADATION_DETECTION_V2.md` for boundaries and findings.
