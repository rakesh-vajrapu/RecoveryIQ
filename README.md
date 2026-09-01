# RecoveryIQ

RecoveryIQ is an autonomous revenue-recovery control plane for Razorpay-style payment workflows.

It detects revenue at risk, estimates recoverability across possible interventions, selects the highest-value action under deterministic guardrails, executes only supported recovery workflows, verifies provider outcomes, and attributes recovered revenue exactly once.

## Alignment with Razorpay Track 03

RecoveryIQ solves the critical business problem of **Involuntary Churn** using an explicitly safe, auditable AI architecture. Unlike generic AI chatbots where Large Language Models are unsafely given financial execution authority, RecoveryIQ enforces strict separation of concerns.

## Core Architecture

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** FastAPI, Python 3.12, Pydantic, SQLAlchemy
- **Local persistence:** SQLite
- **ML:** LightGBM, scikit-learn, isotonic calibration
- **Decision authority:** Deterministic ERV and Sequential Policy V2
- **Payment provider:** Razorpay Test Mode
- **Explanation:** Groq through the provider abstraction, with deterministic fallback

```text
Next.js UI
    ?
FastAPI API
    ?
Recovery intelligence ? ML estimates ? deterministic policy
    ?
Explicit execution boundary
    ?
Razorpay Test Mode
    ?
Verified outcome ? attribution ? audit

Precomputed evidence ? explanation provider
                     (no decision or execution authority)
```

## Evidence Types

RecoveryIQ strictly isolates four types of evidence. **Synthetic Demo Opportunities ? Simulated Batch Evaluation ? Razorpay Test Mode Evidence ? Isolated Local Verification.**

1. **DEMO · SYNTHETIC:** Presentation-scale operational opportunities shown in the UI. These are NOT provider recoveries.
2. **SEALED · SIMULATED:** Scientific/economic evaluation of policies at scale using synthetic test data. They are NOT Razorpay provider revenue.
3. **RAZORPAY · TEST MODE:** Provider integration and lifecycle proof. Verified test mode webhooks and states. No real money moved.
4. **ISOLATED LOCAL VERIFICATION:** Safety/concurrency proof utilizing a fake provider harness to test edge cases (e.g., race conditions, LLM outages) safely.

## Verified Metrics

All claims are backed by rigorous, verified evidence artifacts:
- **27,406** sealed simulated episodes
- **75.97%** simulated recovery
- **?4.72 Cr** simulated net recovery value
- **+?1.44 Cr** simulated net value vs Reminder + Retry
- **0** policy violations
- **?2.00** verified Razorpay Test Mode recovery
- **No real money moved**
- **10-way concurrency verification** proven in Isolated Local Verification

## Safety Model

RecoveryIQ is unique in how it handles Artificial Intelligence safety in fintech:
- **LLM explanation-only boundary:** The LLM (Groq) is explicitly banned from making decisions or triggering payments. It only translates complex data into human-readable summaries.
- **Deterministic Policy:** Bounded horizon, interventions, retries, and contacts.
- **Database guarantees:** Uniqueness and idempotency enforcement.
- **Webhook Authenticity:** HMAC-SHA256 verification over exact raw bytes.
- **Deduplication:** Event deduplication and idempotent processing.
- **Exactly-once constraints:** ExternalOutcome and RecoveryAttribution exactly-once local invariants.
- **Graceful Limitations:** Provider ambiguity is handled as a limitation; there is no automatic stale reservation reaper implemented in this demo.

## Razorpay Test Mode Integration

RecoverIQ implements a complete Razorpay Test Mode recovery lifecycle:
1. A failed recovery attempt is safely correlated to an existing case.
2. An operator-initiated payment link is generated and sent.
3. A successful payment is verified through an authentic signed webhook (`payment_link.paid`).
4. Recovered revenue is attributed exactly once.

## How to Run Locally

### Requirements
- Git, Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 24 LTS and npm

### Configure
```powershell
git clone <repository-url> RecoveryIQ
Set-Location RecoveryIQ
Copy-Item .env.example .env
```
Keep `.env` local.

### Start the backend
```powershell
Set-Location apps/api
uv sync --dev --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Start the frontend
```powershell
Set-Location apps/web
npm ci
npm run dev
```
Open `http://localhost:3000`.

## Judge Demo Journey

A recommended 5-minute manual walk-through for Razorpay judges:

1. **Command Center:** Observe the autonomous revenue-recovery control plane, three evidence lanes, and bounded autonomy principles.
2. **Batch Explorer / Evaluation:** Review the 27,406 sealed simulated episodes, 75.97% recovery rate, incremental value, and 0 policy violations.
3. **Decision Intelligence:** Examine candidate action probabilities, ERV, and Human Review abstentions, highlighting the explicit policy boundaries.
4. **Payment Health:** Check the issuer/method degradation intelligence (Watch ? Confirmed) and its advisory authority.
5. **Safety Lab:** View the proof of 10-way duplicate webhook isolation, 1 fake provider call, LLM isolation, and exact attribution protections.
6. **Razorpay Integration:** Inspect the Operator Initiated Test Mode recovery, signed webhook evidence, exactly-once attribution, and the verified ?2.00 all-time proof (with no real money).

## Verified Runtime Truth

- **Frontend:** Local Next.js
- **Backend:** Local FastAPI
- **Persistence:** SQLite demo persistence
- **Provider Mode:** Razorpay Test Mode only
- **Execution:** Local/eager execution where applicable

We do **NOT** claim production deployment, Docker deployment, PostgreSQL runtime, or Live Razorpay mode.

## Limitations

- Razorpay Test Mode only; Live Mode is intentionally blocked and unavailable. No real money moved.
- Sealed batch evaluations and Payment Health incident evidence are simulated.
- Safety concurrency verification utilizes a fake local provider harness.
- PostgreSQL concurrency is architecturally compatible but not tested in this demo.
- Detector V2 is advisory only.
- The automatic stale execution reservation reaper is not implemented.
- Some execution actions are internal-schedule or recommendation only.
- The LLM is an explanation-only layer and cannot authorize or execute payments.
