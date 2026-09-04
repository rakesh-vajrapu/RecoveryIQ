# RecoveryIQ Safety Model

[Back to README](../README.md)

---

## Safety Philosophy

RecoveryIQ's control plane treats generative AI risk, API unreliability, and concurrency chaos as primary engineering constraints. The system enforces strict deterministic bounds at the database and policy layers, completely segregating explanation generation from financial execution.

## Financial Authority Boundaries

RecoveryIQ enforces four fundamental boundaries:

1. **AI cannot authorize financial execution.** Generative models act in an explanation-only capacity.
2. **Duplicate events cannot create duplicate local recovery attribution.** Database `UNIQUE` constraints enforce exactly-once boundaries.
3. **Recovery workflows are bounded by deterministic stopping rules.** ML predictions that violate policy limits are blocked.
4. **Evidence categories are isolated.** Simulated money and provider evidence are never financially combined.

---

## Adversarial Verification (Isolated Local)

Safety is not assumed; it is actively verified through isolated local adversarial testing to confirm the resilience of exactly-once invariants.

| Scenario | Measured | Defense Mechanism | Status |
| :--- | :--- | :--- | :--- |
| **Concurrent Webhook Race** | 10 concurrent identical webhook requests → 1 unique persisted event (9 deduplicated) | `ExternalWebhookEvent.provider_event_id` UNIQUE constraint | **PROVEN** |
| **Concurrent Execution Race** | 10 concurrent creation invocations → 1 logical execution → 1 fake provider call | `idempotency_key` UNIQUE constraint & execution reservation | **PROVEN** |
| **Duplicate Success** | 10 identical success events → 1 `ExternalOutcome` → 1 `RecoveryAttribution` | `RecoveryAttribution.external_outcome_id` UNIQUE constraint | **PROVEN** |
| **Stale Execution Recovery** | Stale local execution reservations are detected and reconciled without blind provider replay | Atomic CAS state transitions + provider reconciliation | **PROVEN** |

---

## Exactly-Once Local Attribution

RecoveryIQ relies on SQLite + UNIQUE Constraints (not WAL dependency) to provide exactly-once local outcome and recovery attribution semantics. 

These strict constraints include:
- `ExternalWebhookEvent.provider_event_id`
- `ExternalExecution.execution_plan_id`
- `ExternalExecution.idempotency_key`
- `ExternalExecution.provider_reference_id`
- `ExternalOutcome.webhook_event_id`
- `ExternalOutcome.external_payment_id`
- `RecoveryAttribution.recovery_case_id`
- `RecoveryAttribution.external_outcome_id`

## Failure Isolation

| Scenario | Consequence | Status |
| :--- | :--- | :--- |
| **LLM Outage** | Explanation provider becomes UNAVAILABLE. Policy decision and financial state remain UNCHANGED. | **PROVEN** |
| **Malformed LLM Output** | Pydantic strict schema rejection traps invalid shapes. Financial state remains unchanged. | **PROVEN** |
| **Unmapped Payment** | Unmapped provider failures are ignored safely. No execution, outcome, or attribution is created. | **PROVEN** |
| **Retry Storm** | Actions exceeding deterministic policy limits (e.g. max retries/contacts) are blocked before reaching executors. | **PROVEN** |

---

## Stale Execution Recovery

Stale `ExternalExecution` reservations are detected and deterministically recovered without blind provider replay.

### Pre-Dispatch Recovery (PLANNED → FAILED)

If an execution reservation remains in `PLANNED` state beyond the configured timeout (default: 15 minutes), it is provably pre-dispatch — no provider API call was made. The sweeper atomically transitions it to `FAILED` with `failure_category = STALE_RESERVATION`.

### Post-Dispatch Recovery (EXECUTING → UNKNOWN → Reconciliation)

If an execution remains in `EXECUTING` state beyond the timeout, the provider dispatch may have occurred. The sweeper transitions it to `UNKNOWN` and invokes provider reconciliation using:

- The `provider_entity_id` (if the provider returned an ID before crash), or
- The `provider_reference_id` (the deterministic reference generated before dispatch).

The reconciled provider resource is verified against the persisted amount, currency, and reference. Matching resources resolve the same execution. Mismatches, not-found results, and lookup errors all fail closed — no replacement Payment Link is authorized.

### Evidence

8 focused tests in `tests/test_stale_recovery.py` verify pre-dispatch sweep, post-dispatch reconciliation, mismatch rejection, idempotent re-sweep, concurrent sweep race protection, terminal state safety, and not-found blocking.

Evidence lane: **ISOLATED LOCAL VERIFICATION**.

[Read the full External Execution Recovery documentation →](EXTERNAL_EXECUTION_RECOVERY.md)

---

## Provider Uncertainty & Reconciliation

**Provider Crash Ambiguity:**
If the local process crashes before persisting a successful provider response, the reservation transitions to `UNKNOWN`. Reconciliation uses known provider identity/reference to resolve the execution without blind replay. Unresolved external ambiguity may require provider-side evidence or manual operator resolution.
*Status: **PARTIALLY_PROTECTED** (CFP-11)*

**Stale Execution Reservations:**
Stale pre-dispatch and post-dispatch reservations are detected and reconciled as described above. Repeated sweep invocations are idempotent.
*Status: **PROVEN** (CFP-03)*
