# Critical Financial Path Gate

The Critical Financial Path Gate explicitly exercises authentication, idempotency, provider-truth reconciliation, outcome uniqueness, attribution uniqueness, and fail-closed payment-state transitions in CI.

These are **ISOLATED LOCAL VERIFICATION** tests using fake/provider fixtures; they are not live Razorpay Test Mode transactions.

## Manifest

| ID | Name | Invariant | Evidence Lane | Limitation |
|---|---|---|---|---|
| **CFP-01** | Webhook authenticity | Invalid or missing Razorpay signature is rejected before processing | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-02** | Provider event idempotency | same x-razorpay-event-id replay is acknowledged safely without duplicate financial effect | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-03** | Execution idempotency / reservation | one durable execution reservation prevents duplicate provider calls for the same logical execution | ISOLATED_LOCAL_VERIFICATION | Stale execution reservation sweeper remains: NOT_IMPLEMENTED |
| **CFP-04** | Payment correlation invariants | Mismatch in amount, currency, or reference fails closed and creates no attribution | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-05** | Provider truth triangulation | CONFIRMED status requires matching independent provider state; MISMATCH blocks outcome | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-06** | External outcome uniqueness | Provider success replay yields exactly one ExternalOutcome | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-07** | Recovery attribution exactly once | Exactly-once local recovery attribution semantics per case | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-08** | Non-success payment states | Expired, cancelled, or partial payments produce no successful attribution | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-09** | Subscription.charged recovery | subscription.charged safely and independently recovers correctly correlated cases exactly once | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-10** | Execution authority | OPERATOR_INITIATED execution safely records autonomous=false separate from provenance | ISOLATED_LOCAL_VERIFICATION | - |
| **CFP-11** | Unknown provider outcome / crash ambiguity | Unknown outcomes are partially protected and safely block immediate blind replays | ISOLATED_LOCAL_VERIFICATION | Provider crash ambiguity remains: PARTIALLY_PROTECTED |
| **CFP-12** | Evidence does not create financial truth | Recovery proof is strictly read-only and does not persist confirmation records | ISOLATED_LOCAL_VERIFICATION | - |

> [!NOTE]
> Local tests do not replace live Razorpay Test Mode evidence, and test coverage does not prove the absence of all bugs. External provider execution is not exactly-once guaranteed.
