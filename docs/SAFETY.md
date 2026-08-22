# Safety and Trust Boundaries

## Operating environments

RecoverIQ supports deterministic simulation and an isolated Razorpay Test Mode boundary. Live Mode is absent: configuration accepts only `SIMULATION` or `RAZORPAY_TEST`, `RAZORPAY_MODE=test`, and requires the documented `rzp_test_` Key ID prefix whenever API credentials are supplied. Every monetary display must state **SIMULATED** or **TEST MODE**. No development fixture or demonstration uses real customer PII or real payment credentials.

## Sensitive payment data

The application must never collect, store, log, prompt with, or request PAN, CVV, OTP, full bank-account details, or authentication tokens. Payment methods are represented only by safe categories and provider-issued opaque identifiers. Raw webhooks are minimized and redacted before diagnostic logging or AI enrichment.

## Secret handling

Secrets enter through environment variables or a deployment secret store. `.env*` files are ignored except `.env.example`, which contains placeholders only. Pydantic secret types prevent accidental representation. Health endpoints, exceptions, audit metadata, CI logs, screenshots, fixtures, and Gemini prompts may not include secret values. Git history will be scanned before submission.

## Authorization boundary

Predictive models estimate outcomes; they do not prove provider capability. Sequential Policy V2 remains frozen, and incomplete Razorpay history routes to human review. The execution planner classifies every action before an executor can act. The sole Test Mode side effect is an explicit, persisted Payment Link plan; the operator fallback is visibly separate from policy selection. Executors accept only persisted, approved commands and re-check mode, amount, currency, state, and idempotency before side effects.

## LLM trust boundary

Gemini receives allowlisted structured evidence and returns validated enrichment. It cannot set payment state, decide that funds moved, change amounts, approve policy, bypass abstention, or invoke executors. External strings are untrusted data even when they contain instruction-like text. Provider failure selects a deterministic fallback and leaves the core workflow operating.

## Idempotency and concurrency

Provider event IDs, side-effect idempotency keys, Payment Link references/IDs, plans, external payments, and per-case revenue attribution are persisted with uniqueness constraints. A provider timeout after create remains `UNKNOWN`; reconciliation by the unique reference cannot authorize another create merely because a lookup is empty. PostgreSQL transactions provide the full-environment concurrency boundary. SQLite is for single-developer execution and tests, not evidence of production worker concurrency safety.

## Auditability

Meaningful ingestion, evidence, model, policy, execution, outcome, attribution, and enrichment events will be appended with UTC timestamp, correlation ID, entity, actor, event type, and redacted structured metadata. Audit records explain what the system knew and why an action was or was not allowed; they do not treat generated prose as authoritative evidence.

## Safe failure and abstention

Unknown events are retained and safely ignored. Signatures are HMAC-SHA256 verified over exact raw bytes before parsing. Contradictory states, stale events, amount/reference mismatches, missing required evidence, and unexpected provider responses lead to ignoring, `UNKNOWN`, failure, or human review—not optimistic recovery. Duplicate/out-of-order events, provider timeouts/failures, expiry, and worker replay are injected offline. No external outage may create duplicate financial or customer-facing side effects.

## Current limitations

Phase 7 is Level A offline complete; genuine credential/API/webhook evidence remains unverified until the opt-in runbook is executed. SQLite does not prove concurrent-worker locking. The context adapter deliberately abstains on a first provider event because complete frozen-V2 history/category semantics are unavailable. Payment Links recover an alternate Test Mode payment only; they do not repair the original subscription. Gemini, Live Mode, messaging, provider retry operations, and the final operational UI are not part of this phase.
