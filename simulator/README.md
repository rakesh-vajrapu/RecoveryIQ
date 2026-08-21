# RecoverIQ Simulator

This standalone Python package contains the deterministic Phase 2 payment environment and fixed-policy baselines. It intentionally has no dependency on the API, Gemini, Razorpay, or future recovery ML.

From the repository root:

```powershell
uv sync --project simulator --dev
uv run --project simulator python -m recoveriq_simulator.cli benchmark --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli inspect <experiment-id>
```

Generated datasets are written below `artifacts/simulations/` and are ignored by Git. See `docs/SIMULATOR.md` for the environment and leakage boundaries.

