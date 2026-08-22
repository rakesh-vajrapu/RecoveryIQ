# RecoverIQ

**Safe Adaptive Revenue Recovery for Recurring Payments**

RecoverIQ is a bounded recovery control plane for Razorpay Buildathon 2026, Track 03: AI Revenue Recovery. It is designed to compare policy-permitted actions, adapt after observed intervention failure, limit autonomous retries and contacts, and measure exactly attributed recovery against transparent workflows.

The central product insight is simple: **recovery should adapt to observable episode state without becoming unbounded or opaque.** Payment health remains useful operational evidence, but two held-out phases found no primary recovery benefit from using it as a model feature.

## Current status

Phase 0–6 foundation, deterministic simulator, robustness validation, tiered degradation detection, action-conditioned recovery prediction, and bounded sequential ERV policy are implemented:

- FastAPI health API with typed, secret-safe configuration;
- portable SQLAlchemy 2 domain foundation and initial Alembic migration;
- SQLite local development with PostgreSQL configuration support;
- Celery with eager local/test execution and Redis full-environment configuration;
- structured JSON logging;
- isolated Gemini, fake, and deterministic fallback providers;
- a Pydantic-validated `DecisionExplanation` proof;
- Next.js App Router shell with strict TypeScript, Tailwind, shadcn/ui, and runtime API health status;
- backend/frontend CI, linting, types, and tests;
- PostgreSQL and Redis Docker Compose definition.
- seeded event-driven simulation with hidden ground truth and leakage-safe observations;
- synthetic multi-merchant payments, failure families, and issuer degradation incidents;
- fixed-retry and reminder-plus-retry baselines with paired counterfactual draws;
- reproducible Parquet/JSON experiment artifacts, sanity analysis, and baseline metrics.
- pre-registered development/validation/final seed groups and multi-seed confidence intervals;
- heterogeneous incident severity/duration/volume, causal nudge audits, cost regimes, sensitivity analysis, and machine-checkable leakage boundaries.
- one-action randomized exploration logs with explicit propensities and no unselected training counterfactuals;
- leakage-safe `RecoveryFeatureSnapshot` V1, deterministic logistic/LightGBM pipelines, isotonic calibration, held-out ranking, ablation, and structured SHAP evidence.
- exact-minor-unit ERV scoring, nine deterministic action candidates, structured safety/support rules, STOP/HUMAN_REVIEW, paired policy validation, and decision traces.
- randomized maximum-three-action trajectory logging with exact propensities and current-action attribution;
- no-health trajectory-aware Recovery Model V2 with frozen isotonic calibration and a passing one-time held-out gate;
- full 48-hour Sequential Policy V2 evaluation against Fixed Retry, Reminder + Retry, strong observable rules, probability-only selection, and a greedy hidden oracle.

Implemented through Phase 6: Recovery Model V2 predicts action-level recovery from past observable trajectory state, and RecoverIQ Sequential Policy V2 replans for at most three interventions inside 48 hours. Its sealed validation recovered 75.97% of 27,406 episodes versus 53.09% for equivalent Reminder + Retry and 64.60% for the simple observable rule, with zero violations. The pure probability policy recovered slightly more than ERV Policy V2 (76.18%), so Phase 6 does not claim that economic selection improved gross recovery over probability-only selection. Detector V2 remains advisory-only and absent from primary Model V2. Not implemented yet: production recovery execution, Razorpay APIs, production Gemini prompts, or final operational dashboards. The overall-final seeds remain untouched, and the UI intentionally shows no recovery metrics.

## Architecture

```text
payment event → normalized evidence → aggregate payment health
                                      ↓
                              degradation evidence
                                      ↓
candidate actions → trajectory-aware probabilities → incremental expected recovery value
                                      ↓
                       deterministic bounded policy
                    ↙ execute  ↓ replan  ↘ abstain
                                      ↓
                         authoritative outcome + audit

Gemini: structured explanation beside this flow; never financial authority.
```

The API uses synchronous SQLAlchemy sessions consistently across FastAPI, Alembic, and Celery. Local development defaults to SQLite so it requires no container daemon. Full environments select PostgreSQL through `DATABASE_URL`. Celery remains the task boundary in both modes: eager execution uses memory transport locally; non-eager execution uses Redis.

Detailed decisions are in [Architecture](docs/ARCHITECTURE.md), [Gemini Design](docs/GEMINI_DESIGN.md), [Safety](docs/SAFETY.md), and [Evaluation](docs/EVALUATION.md).

## Repository layout

```text
apps/api/       FastAPI, SQLAlchemy, Alembic, Celery, Gemini providers, tests
apps/web/       Next.js operational shell
docs/           Product, architecture, evaluation, safety, and delivery records
simulator/recoveriq_ml/  Leakage-safe recovery logging, models, calibration, and evaluation
simulator/recoveriq_ml_v2/  Trajectory-aware no-health Model V2
simulator/recoveriq_sequential*/  Episode environment and bounded Policy V2
simulator/      Deterministic payment environment, baseline policies, CLI, and tests
artifacts/      Ignored generated simulation experiments (with tracked placeholders)
infra/          Reserved for deployment-specific assets
scripts/        Reserved for reproducible developer and evaluation commands
```

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 24 LTS and npm
- Git
- optional Docker Engine with Compose for PostgreSQL/Redis

Gemini and Razorpay credentials are not required. Never use Razorpay Live Mode credentials.

## Local development without Docker

From the repository root, create a local environment file if you need to change defaults:

```powershell
Copy-Item .env.example .env
```

The checked-in defaults already select SQLite, eager Celery, and disabled Gemini.

### Backend

```powershell
Set-Location apps/api
uv sync --dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/health`. The response reports only safe operational state.

### Frontend

In a second terminal:

```powershell
Set-Location apps/web
npm install
npm run dev
```

Visit `http://localhost:3000`. The browser connects to `http://localhost:8000/health` by default. Override it in `apps/web/.env.local` with `NEXT_PUBLIC_API_BASE_URL` when necessary.

### Celery eager proof

```powershell
Set-Location apps/api
uv run python -c "from app.celery_app import health_ping; print(health_ping.delay().get(timeout=2))"
```

No worker or Redis instance is required when `CELERY_TASK_ALWAYS_EAGER=true`.

### Deterministic simulator

```powershell
uv sync --project simulator --dev --locked
uv run --project simulator python -m recoveriq_simulator.cli benchmark --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli benchmark-suite --group development
uv run --project simulator python -m recoveriq_simulator.cli benchmark-suite --group validation
uv run --project simulator python -m recoveriq_simulator.cli quality-report --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli sensitivity
uv run --project simulator python -m recoveriq_simulator.cli inspect <experiment-id>
```

The default benchmark evaluates 20,000 attempts and writes ignored artifacts below `artifacts/simulations/`. Multi-seed and sensitivity reports use adjacent ignored directories. Reserved final seeds are not run during development. All financial outputs are synthetic. See [Simulator](docs/SIMULATOR.md) and [Simulator Validation](docs/SIMULATOR_VALIDATION.md).

### Recovery Model V1

The completed machine-readable reports and reproducibility protocol are documented in [Recovery Model](docs/RECOVERY_MODEL.md). The guarded pipeline is:

```powershell
uv run --project simulator recovery-model generate-logged --group training
uv run --project simulator recovery-model generate-logged --group development
uv run --project simulator recovery-model train
uv run --project simulator recovery-model calibrate
uv run --project simulator recovery-model evaluate-heldout
uv run --project simulator recovery-model shap-report
uv run --project simulator recovery-model phase4-summary
```

The held-out command refuses overwrite. Overall-final seeds remain command-guarded and untouched.

### RecoverIQ ERV Policy V1

The development audit, frozen policy, one-time validation, and structured decision trace are documented in [Recovery Policy](docs/RECOVERY_POLICY.md). Reproduction commands are deliberately stage-guarded:

```powershell
uv run --project simulator recovery-policy audit-development
uv run --project simulator recovery-policy develop-policy
uv run --project simulator recovery-policy evaluate-validation
```

Each completed stage refuses overwrite; validation was executed once and cannot be rerun silently. The overall-final seeds remain untouched.

## Full PostgreSQL and Redis environment

On a supported Docker host:

```powershell
docker compose up -d postgres redis
```

Configure the API with:

```env
DATABASE_URL=postgresql+psycopg://recoveriq:recoveriq-local-only@localhost:5432/recoveriq
REDIS_URL=redis://localhost:6379/0
CELERY_TASK_ALWAYS_EAGER=false
```

Then apply migrations and run separate API and Celery worker processes. Docker Compose is provided for infrastructure only in Phase 1. On this repository's current Windows Server VM, Compose syntax can be validated but Linux containers cannot be launched because no local daemon is available.

## Quality checks

```powershell
Set-Location apps/api
uv sync --dev --locked
uv run ruff check .
uv run mypy app tests
uv run pytest

Set-Location ../web
npm ci
npm run lint
npm run typecheck
npm run build

Set-Location ../..
uv sync --project simulator --dev --locked
uv run --project simulator ruff check simulator
uv run --project simulator mypy simulator/recoveriq_simulator simulator/tests
uv run --project simulator pytest simulator/tests
```

CI runs the same checks without Docker, Redis, PostgreSQL, Gemini, or Razorpay credentials.

## Safety and evidence

- Simulation and Test Mode are always labelled; no live-money claim is made.
- PAN, CVV, OTP, real customer PII, and live credentials are prohibited.
- Models produce evidence; deterministic policy authorizes actions.
- Gemini returns validated explanations and cannot mutate financial state.
- Side effects and recovered revenue will be idempotent and auditable.
- Benchmark results will be generated reproducibly and will not be fabricated.

## Current limitations

The current API schema proves relationships and migrations but does not yet implement repositories, transition locks, or idempotent event ingestion. SQLite is suitable for local development and tests, not production worker concurrency. PostgreSQL compatibility still requires CI or a supported host to exercise against a real service. The simulator is hand-designed synthetic evidence, not a claim about real customers, issuers, Razorpay performance, or achievable recovery lift.
