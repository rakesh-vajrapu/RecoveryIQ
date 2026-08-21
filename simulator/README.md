# RecoverIQ Simulator

This standalone Python package contains the deterministic Phase 2/2.5 payment environment, validation reports, and fixed-policy baselines. It intentionally has no dependency on the API, Gemini, Razorpay, or future recovery ML.

From the repository root:

```powershell
uv sync --project simulator --dev
uv run --project simulator python -m recoveriq_simulator.cli benchmark --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli benchmark-suite --group development
uv run --project simulator python -m recoveriq_simulator.cli benchmark-suite --group validation
uv run --project simulator python -m recoveriq_simulator.cli quality-report --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli sensitivity
uv run --project simulator python -m recoveriq_simulator.cli inspect <experiment-id>
```

Generated datasets and reports below `artifacts/` are ignored by Git. Final evaluation seeds are reserved and require explicit acknowledgement. See `docs/SIMULATOR.md` and `docs/SIMULATOR_VALIDATION.md` for boundaries and findings.
