# Safety and Trust Boundaries

## Operating environments

RecoverIQ supports deterministic simulation and, in a future milestone, Razorpay Test Mode. Live Mode is outside V1 and must not be enabled by configuration alone. Every monetary display must state **SIMULATED** or **TEST MODE**. No development fixture or demonstration uses real customer PII or real payment credentials.

## Sensitive payment data

The application must never collect, store, log, prompt with, or request PAN, CVV, OTP, full bank-account details, or authentication tokens. Payment methods are represented only by safe categories and provider-issued opaque identifiers. Raw webhooks are minimized and redacted before diagnostic logging or AI enrichment.

## Secret handling

Secrets enter through environment variables or a deployment secret store. `.env*` files are ignored except `.env.example`, which contains placeholders only. Pydantic secret types prevent accidental representation. Health endpoints, exceptions, audit metadata, CI logs, screenshots, fixtures, and Gemini prompts may not include secret values. Git history will be scanned before submission.

## Authorization boundary

Future predictive models estimate outcomes; they do not authorize actions. A deterministic policy engine will enforce retry and contact limits, opt-out state, channel permission, active degradation blocks, amount/risk thresholds, confidence requirements, cooldowns, test-mode restrictions, and stopping rules. Executors accept only persisted, approved commands and re-check idempotency before side effects.

## LLM trust boundary

Gemini receives allowlisted structured evidence and returns validated enrichment. It cannot set payment state, decide that funds moved, change amounts, approve policy, bypass abstention, or invoke executors. External strings are untrusted data even when they contain instruction-like text. Provider failure selects a deterministic fallback and leaves the core workflow operating.

## Idempotency and concurrency

Provider event IDs and side-effect idempotency keys will be persisted with uniqueness constraints. Recovery creation, retry scheduling, payment-link creation, contact, and revenue attribution will each have independent deduplication. PostgreSQL transactions and row locking will protect concurrent workers in full environments. SQLite is for single-developer execution and tests, not evidence of production concurrency safety.

## Auditability

Meaningful ingestion, evidence, model, policy, execution, outcome, attribution, and enrichment events will be appended with UTC timestamp, correlation ID, entity, actor, event type, and redacted structured metadata. Audit records explain what the system knew and why an action was or was not allowed; they do not treat generated prose as authoritative evidence.

## Safe failure and abstention

Unknown events are retained and safely ignored. Invalid signatures are rejected. Contradictory states, low confidence, exhausted limits, missing required evidence, and unexpected provider responses lead to waiting, stopping, or human review—not an optimistic action. Gemini, Redis, Razorpay, and worker failures are injected during reliability testing. No external outage may create duplicate financial or customer-facing side effects.

## Current foundation limitations

Phase 1 contains models, configuration, a health endpoint, an eager Celery proof, and provider skeletons. It does not yet ingest provider events, make recovery decisions, execute actions, or attribute money. These missing capabilities are marked as unfinished rather than simulated through fake production metrics.

