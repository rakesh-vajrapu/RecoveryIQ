# RecoverIQ

RecoverIQ is an AI-powered revenue recovery agent that detects revenue leakage, diagnoses observable payment failures, estimates recovery potential with machine learning, selects bounded interventions through deterministic ERV/policy logic, executes approved Razorpay Test Mode workflows, and records verified recovery attribution with an immutable audit trail.

The project demonstrated a complete **Razorpay Test Mode** recovery lifecycle: a failed recovery attempt was safely correlated to an existing case, a later successful payment was verified through a signed webhook, and recovered revenue was attributed exactly once. **No real money was moved.**

## What RecoverIQ Does

The name combines:

- **Recover** — recover revenue at risk from failed recurring payments.
- **IQ** — use prediction, expected-value analysis, policy rules, and explanation-only AI to choose and communicate a safe recovery approach.

RecoverIQ is more than a payment-failure predictor. It connects detection, decisioning, bounded execution, verified outcomes, attribution, and auditability in one workflow.

## Why It Matters

Payment failures have different causes and should not all receive the same retry. A fixed strategy can waste attempts, increase customer friction, and make it difficult to prove which action recovered revenue.

RecoverIQ uses observable evidence to compare supported interventions. It stops or requests human review when context is incomplete, and it records recovery only after authenticated provider evidence confirms the outcome.

## Core Flow

```text
Detect → Diagnose → Decide → Execute → Recover → Audit
```

| Stage | Responsibility |
|---|---|
| Detect | Record payment failures and advisory degradation signals |
| Diagnose | Build a safe view of the failure and recovery episode |
| Decide | Compare ML recovery estimates through deterministic ERV and policy rules |
| Execute | Run only an explicitly supported, bounded capability |
| Recover | Verify the provider outcome and attribute recovered value exactly once |
| Audit | Preserve redacted, immutable lifecycle evidence |

## What Is Actually Implemented

- persisted `RecoveryCase` workflows for failed recurring payments;
- degradation detection with Detector V2 kept advisory-only;
- LightGBM recovery scoring with calibrated probabilities;
- deterministic Expected Recovery Value and policy decisioning;
- bounded sequential recovery with retry, contact, horizon, support, and stopping rules;
- explicit execution capabilities rather than unrestricted model actions;
- Razorpay Test Mode Payment Link creation and reconciliation;
- signed Razorpay webhook processing and provider-event deduplication;
- failed-attempt correlation through provider order mapping for RecoverIQ-created links;
- exactly-once external outcome and recovery attribution;
- immutable audit timelines and decision traces;
- Groq-backed, schema-validated explanations with deterministic fallback;
- a responsive local Next.js operations dashboard.

## Verified Local Demo

The demonstrated application ran directly on the local Windows Server environment:

- FastAPI backend;
- Next.js frontend;
- SQLite persistence;
- Razorpay Test Mode;
- signed webhooks delivered to the local backend through a temporary public tunnel;
- Groq explanation provider with local fallback boundaries.

The final local Test Mode dataset showed:

| Metric | Verified demo value |
|---|---:|
| Opportunities | 2 |
| Recovered cases | 2 |
| Active cases | 0 |
| Attributed recovered value | ₹2.00 |

The ₹2.00 value is **Razorpay Test Mode evidence only**. It is not production revenue and no real funds moved.

## Razorpay Test Mode E2E Proof

```text
Existing RecoveryCase
    ↓
RecoverIQ-created Payment Link
    ↓
payment.failed
    ↓
Provider order mapped to the same execution and case
    ↓
Failed-attempt audit evidence; case remains EXECUTING
    ↓
Customer retries the same link successfully
    ↓
payment_link.paid
    ↓
Signed webhook validation
    ↓
One ExternalOutcome + one RecoveryAttribution
    ↓
Existing case becomes RECOVERED exactly once
```

The verified target case retained:

- one RecoveryCase;
- one Payment Link execution;
- failed-attempt audit evidence;
- one successful external outcome;
- one recovery attribution;
- one recovered transition.

No duplicate RecoveryCase, Payment Link, outcome, or attribution was created.

Implemented Razorpay controls:

- Test Mode only; Live Mode is intentionally unavailable;
- HMAC-SHA256 verification over the exact raw webhook body;
- constant-time signature comparison;
- required unique provider event IDs;
- durable event deduplication and idempotent processing;
- exact reference, amount, currency, and status matching;
- allowlisted, redacted provider evidence;
- safe ignore behavior for unmatched or malformed events.

During verification, a temporary Cloudflare Quick Tunnel exposed the local webhook endpoint. The Quick Tunnel URL was temporary and is not a production endpoint or deployment.

## Architecture

| Area | Verified implementation |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.12, Pydantic, SQLAlchemy |
| Local persistence | SQLite |
| ML | LightGBM, scikit-learn, isotonic calibration |
| Decision authority | Deterministic ERV and Sequential Policy V2 |
| Payment provider | Razorpay Test Mode |
| Explanation | Groq through the provider abstraction, with deterministic fallback |

```text
Next.js UI
    ↓
FastAPI API
    ↓
Recovery intelligence → ML estimates → deterministic policy
    ↓
Explicit execution boundary
    ↓
Razorpay Test Mode
    ↓
Verified outcome → attribution → audit

Precomputed evidence → explanation provider
                     (no decision or execution authority)
```

SQLite is used for the verified local demo. SQLAlchemy-based database abstractions and configuration for broader deployment environments exist, but no production database deployment is claimed.

## Decision Authority and Safety

Authority is deliberately separated:

```text
ML estimates
    +
ERV/policy decides
    +
deterministic guardrails authorize execution

LLM explains the resulting evidence only
```

The LLM can summarize a case, explain supplied factors, and state uncertainty. It cannot select arbitrary actions, modify probabilities or policy, bypass guardrails, trigger Razorpay independently, or change recovery state.

Other safety controls include:

- maximum intervention, retry, contact, and recovery-horizon limits;
- model-support and action-feasibility checks;
- human review for incomplete or contradictory evidence;
- explicit Test Mode capabilities;
- signed webhooks and idempotency;
- exactly-once attribution;
- redacted audit evidence.

Groq was successfully validated as the active explanation provider. Gemini remains implemented only as an optional provider abstraction; live Gemini generation is not claimed as verified.

## Evaluation

The simulator, Recovery Model V2, Detector V2, and Sequential Policy V2 are implemented and reproducible.

Strongest frozen evaluation evidence:

- Recovery Model V2 passed its held-out quality gate on 62,918 decisions across 27,451 synthetic episodes.
- Sequential Policy V2 recovered 75.97% of 27,406 sealed synthetic episodes versus 53.09% for Reminder + Retry, with zero policy violations.
- Detector V2 failed its registered hard-policy gate and therefore remains advisory-only.

All simulator recovery amounts and policy comparisons are **SIMULATED**. They are separate from the ₹2.00 Razorpay Test Mode demo evidence. Neither is a production real-money claim.

Detailed methodology and frozen evidence are available in:

- [Recovery Model V2](docs/RECOVERY_MODEL_V2.md)
- [Sequential Recovery](docs/SEQUENTIAL_RECOVERY.md)
- [Detector V2](docs/DEGRADATION_DETECTION_V2.md)

## Local Setup

### Requirements

- Git
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 24 LTS and npm

No external credentials are required for normal startup or automated tests.

### Configure

```powershell
git clone <repository-url> RecoveryIQ
Set-Location RecoveryIQ
Copy-Item .env.example .env
```

Keep `.env` local and untracked. Default local operation uses SQLite, eager task execution, simulation, and deterministic explanations.

### Start the backend

```powershell
Set-Location apps/api
uv sync --dev --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

- Health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`

### Start the frontend

In a second terminal:

```powershell
Set-Location apps/web
npm ci
npm run dev
```

Open `http://localhost:3000`.

Razorpay and Groq are optional integrations. Their credentials must remain only in ignored local configuration.

### Optional portability configuration

PostgreSQL, Redis, Celery worker, and Docker Compose configuration exists for broader environments. These services were **not** the runtime used for the verified demo.

Container configuration is included for portability, but the verified demo was run directly on the local Windows Server environment.

## Repository Structure

```text
RecoveryIQ/
├── apps/api/       FastAPI, domain services, Razorpay, AI, tests
├── apps/web/       Next.js operations interface
├── simulator/      Simulator, detector, ML, policy, evaluation
├── artifacts/      Frozen models, policies, schemas, and evidence
├── docs/           Architecture, safety, methodology, and runbooks
└── .github/        Continuous integration
```

## Testing

The release checks include:

- backend Pytest, Ruff, and strict mypy;
- focused Razorpay signature, correlation, mismatch, deduplication, and attribution tests;
- simulator, detector, ML, policy, reproducibility, seed, and frozen-artifact tests;
- frontend ESLint, TypeScript checks, and production build;
- secret, Git diff, and protected-artifact checks;
- GitHub Actions for backend, simulator, and frontend quality.

Canonical dependencies are locked by `apps/api/uv.lock`, `simulator/uv.lock`, and `apps/web/package-lock.json`.

```powershell
# Backend
Set-Location apps/api
uv run ruff check .
uv run mypy app tests
uv run pytest

# Simulator, detector, ML, and policy
Set-Location ../../simulator
uv run ruff check .
uv run mypy recoveriq_simulator recoveriq_detector recoveriq_detector_v2 recoveriq_ml recoveriq_ml_v2 recoveriq_policy recoveriq_policy_evaluation recoveriq_sequential recoveriq_sequential_policy tests
uv run pytest

# Frontend
Set-Location ../apps/web
npm run lint
npm run typecheck
npm run build
```

Reserved overall-final seeds must not be rerun during ordinary development.

## Limitations

- Razorpay execution is Test Mode only; Live Mode is intentionally blocked.
- No production or container deployment is claimed.
- The verified demo uses SQLite and local/eager task behavior.
- The Cloudflare Quick Tunnel was temporary webhook connectivity for testing.
- Arbitrary new non-subscription `payment.failed` events are not claimed to create RecoveryCases automatically; local subscription or RecoverIQ-created execution correlation is required.
- The LLM is explanation-only and cannot influence payment decisions or execution.
- Simulator results are simulated and based on designed synthetic data.
- Complete provider-history mapping for online Model V2 scoring is not implemented.
- API authentication, merchant tenancy, operator roles, and production concurrency controls are not implemented.
- No published frontend browser-E2E or line/branch coverage report exists.

## Demo and Evidence

- [Payment Link Recovery E2E Verification](docs/PAYMENT_LINK_RECOVERY_E2E_VERIFICATION.md)
- [Razorpay Test Mode Evidence](docs/RAZORPAY_PHASE_7_5_TEST_MODE_EVIDENCE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Safety Boundaries](docs/SAFETY.md)

## Judge Summary

**RecoverIQ demonstrated a complete Razorpay Test Mode recovery lifecycle in which a failed recovery attempt was safely correlated to an existing case, a later successful payment was verified through a signed webhook, and recovered revenue was attributed exactly once. ML and deterministic policy own recovery decisions; the LLM remains a downstream explanation layer. No real money was moved.**
