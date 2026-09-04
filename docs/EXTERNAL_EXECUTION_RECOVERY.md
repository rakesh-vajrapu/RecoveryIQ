# External Execution Reliability

[Back to README](../README.md) · [Safety & Reliability](SAFETY_AND_RELIABILITY.md) · [Critical Financial Path Gate](CRITICAL_FINANCIAL_PATH_GATE.md)

---

## Problem

An `ExternalExecution` reservation can become stale if the process is interrupted around provider dispatch. RecoveryIQ must distinguish:

**A.** A stale reservation where provider dispatch can be **proven not to have happened** (pre-dispatch).

from

**B.** A stale or ambiguous execution where a provider side effect **may already have happened** (post-dispatch).

Blind duplicate provider calls are never acceptable. A stale reservation must not silently authorize a replacement Payment Link, because the original provider action may have already succeeded externally.

---

## Execution State Boundary

```
PLANNED → EXECUTING → SUCCEEDED
                    → FAILED
                    → UNKNOWN
```

| State | Meaning | Provider Action |
|---|---|---|
| `PLANNED` | Execution reservation created, provider dispatch has **not yet occurred** | None |
| `EXECUTING` | Provider dispatch has been attempted | May have occurred |
| `SUCCEEDED` | Provider confirmed the action | Confirmed |
| `FAILED` | Execution definitively did not produce a provider side effect | None |
| `UNKNOWN` | Provider dispatch was attempted but local outcome is ambiguous | Uncertain |

---

## Idempotency

Each `ExternalExecution` is protected by:

- `execution_plan_id` UNIQUE constraint — one execution per plan.
- `idempotency_key` UNIQUE constraint — deterministic key prevents duplicate provider calls.
- `provider_reference_id` UNIQUE constraint — one provider reference per execution.

These database constraints prevent duplicate reservations before the sweeper is even needed.

---

## Stale Reservation Detection

The `sweep_stale_external_executions` function detects stale reservations using a configurable timeout threshold (default: 15 minutes).

It scans for:

1. **PLANNED** executions older than the threshold → pre-dispatch recovery.
2. **EXECUTING** executions older than the threshold → post-dispatch recovery.

Terminal states (`SUCCEEDED`, `FAILED`) are never modified.

---

## Pre-Dispatch Recovery

**Condition:** `ExternalExecution.state == PLANNED` and `created_at < threshold`.

**Safety proof:** The execution never reached `EXECUTING`, so provider dispatch can be **mathematically proven** not to have happened. No provider API call was made.

**Action:** Atomic Compare-And-Swap (CAS) transitions `PLANNED → FAILED` with `failure_category = STALE_RESERVATION`. The associated `RecoveryCase` is also transitioned to `FAILED`.

**Audit:** `STALE_EXECUTION_SWEPT_BEFORE_DISPATCH` event is recorded with actor `STALE_RESERVATION_SWEEPER`.

**Idempotency:** If the CAS fails (another thread already changed the state), the sweep skips this execution.

---

## Post-Dispatch (Ambiguous) Recovery

**Condition:** `ExternalExecution.state == EXECUTING` and `requested_at < threshold`.

**Safety concern:** Provider dispatch was attempted. The provider may have accepted and created a Payment Link even if the local process crashed before persisting the response.

**Action:** Atomic CAS transitions `EXECUTING → UNKNOWN`, then invokes provider reconciliation.

**Audit:** `STALE_EXECUTION_MARKED_UNKNOWN` event is recorded with actor `STALE_RESERVATION_SWEEPER`.

---

## Provider Reconciliation

When an execution enters `UNKNOWN` state, `reconcile_unknown_execution` attempts to determine the provider-side truth:

### Lookup Strategy

1. If `provider_entity_id` is available (provider already returned an ID before crash): fetch by entity ID.
2. Otherwise: search by `provider_reference_id` (the deterministic reference RecoveryIQ generated before dispatch).

### Verification

The reconciled provider resource is verified against the persisted execution:

- **Reference ID** must match.
- **Amount** (minor units) must match.
- **Currency** must match.

### Reconciliation Outcomes

| Provider Lookup Result | Action | Final State |
|---|---|---|
| **Found and matches** | Resolve the SAME execution with the found provider resource | `SUCCEEDED` |
| **Found but mismatches** | Fail closed. Record `RECONCILIATION_MISMATCH` | `UNKNOWN` (blocked) |
| **Not found** | Record `RECONCILIATION_NOT_FOUND`. Does NOT authorize a new Payment Link | `UNKNOWN` (blocked) |
| **Lookup error** | Record `RECONCILIATION_PENDING`. Deferred for future retry | `UNKNOWN` (blocked) |

### Why Blind Replay Is Forbidden

A `NOT_FOUND` result from the provider list API does not authorize creating a replacement Payment Link because:

- The provider's list endpoint may be eventually consistent.
- The original Payment Link may exist but not yet appear in search results.
- Creating a duplicate would violate the exactly-once execution reservation invariant.

The execution remains blocked until explicit reconciliation succeeds or an operator intervenes.

---

## Audit Evidence

Every stale recovery action produces an immutable audit event:

| Event Type | Actor | Meaning |
|---|---|---|
| `STALE_EXECUTION_SWEPT_BEFORE_DISPATCH` | `STALE_RESERVATION_SWEEPER` | Pre-dispatch reservation safely cleaned |
| `STALE_EXECUTION_MARKED_UNKNOWN` | `STALE_RESERVATION_SWEEPER` | Post-dispatch execution moved to reconciliation |
| `UNKNOWN_EXECUTION_RECONCILED` | `RAZORPAY_RECONCILER` | Provider resource found and matched |

---

## Tests

8 focused tests in `tests/test_stale_recovery.py`:

| Test | What It Proves |
|---|---|
| `test_stale_pre_dispatch_reservation_swept` | PLANNED → FAILED with zero provider calls |
| `test_stale_post_dispatch_ambiguous_execution` | EXECUTING → UNKNOWN when reconciliation fails |
| `test_provider_resource_found_during_reconciliation` | EXECUTING → UNKNOWN → SUCCEEDED when provider has the link |
| `test_provider_lookup_mismatch` | Mismatched provider resource does not resolve execution |
| `test_duplicate_sweeper_invocation` | Repeated sweep is idempotent (second run finds nothing) |
| `test_concurrent_sweeper_race` | CAS prevents sweep when executor already claimed the reservation |
| `test_terminal_execution_ignored` | SUCCEEDED executions are never modified |
| `test_provider_lookup_returns_none` | NOT_FOUND does not authorize a replacement Payment Link |

Evidence lane: **ISOLATED LOCAL VERIFICATION** (fake gateway, isolated SQLite).

---

## CFP Mapping

| CFP ID | Status | Evidence |
|---|---|---|
| **CFP-03** | **PROVEN** | Execution idempotency + stale reservation recovery. 3 tests mapped in CFP gate |
| **CFP-11** | **PARTIALLY_PROTECTED** | Unknown provider outcome / crash ambiguity. Reconciliation uses known provider identity but unresolved external ambiguity may require manual resolution |

---

## Remaining Provider Ambiguity

CFP-11 remains `PARTIALLY_PROTECTED` because:

A provider may accept an external action (e.g., create a Payment Link) while the application crashes before receiving or persisting the provider's response. RecoveryIQ prevents blind replay and reconciles using known provider identity/reference, but:

- The provider's list/search API may be eventually consistent.
- If the provider accepted the action but the resource is not yet searchable, the execution remains `UNKNOWN` until a later reconciliation attempt succeeds.
- Unresolved external ambiguity may still require provider-side evidence or manual operator resolution.

This is safer and more credible than claiming impossible provider-level exactly-once execution semantics.

---

## Production Scheduling Boundary

The current implementation exposes `sweep_stale_external_executions` as an explicit service function that can be invoked via API endpoint or task. It is **not** a continuously running production scheduler.

A production deployment would need an external scheduler (e.g., cron job, cloud scheduler, or Celery beat) to invoke the sweep at regular intervals. This is intentionally outside the current demo/reference scope.
