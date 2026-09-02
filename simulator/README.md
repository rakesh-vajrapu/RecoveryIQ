# RecoverIQ Simulator

This standalone Python package contains the deterministic Phase 2/2.5 payment environment, validation reports, fixed-policy baselines, the frozen Phase 3 detector-v1 benchmark, the separate Phase 3.5 observable-only detector v2, and the completed Phase 4 action-conditioned recovery-model pipeline. It intentionally has no dependency on the API, LLMs, Razorpay, or a production recovery policy.

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
uv run --project simulator recovery-model generate-logged --group training
uv run --project simulator recovery-model generate-logged --group development
uv run --project simulator recovery-model train
uv run --project simulator recovery-model calibrate
uv run --project simulator recovery-model evaluate-heldout
uv run --project simulator recovery-model shap-report
uv run --project simulator recovery-model phase4-summary
```

Generated datasets and bulky replay reports below `artifacts/` are ignored by Git; frozen configurations, model/calibration binaries, manifests, and compact evidence are versioned. Detector-v2 validation and recovery-model held-out evaluation refuse overwrite. Consumed or reserved calibration, held-out, and final seeds are forbidden to ordinary replay commands. See `docs/SIMULATOR.md`, `docs/SIMULATOR_VALIDATION.md`, `docs/DEGRADATION_DETECTION_V2.md`, and `docs/RECOVERY_MODEL.md` for boundaries and findings.
