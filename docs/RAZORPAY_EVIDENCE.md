# Razorpay Provider Evidence

[Back to README](../README.md)

> **Razorpay Test Mode Verified Recovery: ₹2.00**
> **No real money moved.**

This document provides canonical provider integration evidence for RecoveryIQ. It distinguishes the real verified Test Mode lifecycle from simulated recovery performance. 

## The Test Mode Lifecycle

RecoveryIQ proves its provider API integration through the following strict exactly-once lifecycle:

1. **Failure observed**
2. **`RecoveryCase`** created and correlated
3. **`HUMAN_REVIEW`** decision (due to intentional missing context)
4. **`OPERATOR_INITIATED`** execution
5. **Payment Link** creation via Razorpay Test Mode API
6. **Mapped failed recovery attempt** (authenticated webhook)
7. **Successful payment** against the Payment Link
8. **Authenticated webhook** received with HMAC SHA-256 signature
9. **`ExternalOutcome`** recorded exactly once
10. **`RecoveryAttribution`** mapped exactly once
11. **Case state** transitioned to **`RECOVERED`**

## What This Evidence Proves

This lifecycle evidence proves:
- Real provider API integration
- Payment Link execution where supported
- Signed webhook authenticity (raw-body HMAC validation)
- Independent Provider Truth Triangulation via live fetch
- Exact-match local invariant verification (amount, currency, references)
- Correlation logic
- External outcome recording and recovery attribution
- Exactly-once local accounting

## What This Evidence DOES NOT Prove

This lifecycle evidence does **NOT** prove:
- Production revenue
- Production-scale recovery performance (see Evaluation Results)
- Live-mode safety

---

## Historical E2E Verification & Timestamp Remediation

**Status:** **PASS.** The timestamp-quality observation discovered during verification was remediated without rewriting provider evidence or database history, as documented below.

On 30 Aug 2026, a real Razorpay Test Mode failure and a later successful retry were processed against the same RecoverIQ-created Payment Link and the same existing RecoveryCase. The failure remained non-terminal. The success produced one verified outcome, one recovery attribution, and one transition to `RECOVERED`.

No new RecoveryCase, Payment Link, ExternalExecution, webhook configuration, or recovery decision was created during Stage 2.

## Scope and identifiers

| Item | Value |
| --- | --- |
| RecoveryCase | `40ebd35f-6c4c-4bb5-b7b5-a25914393528` |
| Correlation ID | `9f656776-a5a3-4e3f-a8c1-b233908c674c` |
| Payment Link | `plink_TTChN26OROddNO` |
| Razorpay order | `order_TTCltgAjeLeOPM` |
| Amount | INR 1.00 (100 minor units) |
| Execution mode | `RAZORPAY_TEST` |

## Original defect

Razorpay `payment.failed` events for Payment Link attempts can omit `subscription_id`. The original webhook path required that field and classified such events as `MISSING_SUBSCRIPTION_ID`, even when their `order_id` belonged to an existing RecoverIQ-created Payment Link execution.

The narrow fix preserves subscription handling and adds correlation only when all of the following hold:

- the webhook signature is valid;
- the Razorpay event ID is unique;
- `order_id` is present;
- the order maps to exactly one RecoverIQ `ExternalExecution`;
- that execution maps to exactly one existing RecoveryCase;
- amount and currency match;
- provider and `RAZORPAY_TEST` execution constraints match.

An accepted failure creates a failed `PaymentAttempt`, a `FailureEvent`, and immutable `RECOVERY_PAYMENT_ATTEMPT_FAILED` audit evidence. It does not create an `ExternalOutcome`, `RecoveryAttribution`, RecoveryCase, Payment Link, or execution, and the case remains `EXECUTING`.

## Stage 1 — intentional failed recovery attempt

The operator-approved Stage 1 event was:

| Field | Evidence |
| --- | --- |
| Razorpay event ID | `TVwveXsB8l3kcO` |
| Payment ID | `pay_TVwvZx1UoHHM2r` |
| Event type | `payment.failed` |
| Payment created | 30 Aug 2026 10:32:57 UTC / 16:02:57 IST |
| Webhook received | 30 Aug 2026 10:33:02.315473 UTC / 16:03:02.315473 IST |
| Method | Wallet |
| Provider error | `BAD_REQUEST_ERROR` / `payment_failed` / `issuer` / `payment_authorization` |
| Processing status | `PROCESSED` |
| Signature | `HMAC_SHA256_RAW_BODY` validated |
| Mapped case | `40ebd35f-6c4c-4bb5-b7b5-a25914393528` |
| Case after failure | `EXECUTING` |

Stage 1 produced one persisted webhook row for this event ID, one failed PaymentAttempt, one FailureEvent, and one `RECOVERY_PAYMENT_ATTEMPT_FAILED` audit record for the mapped execution. Outcomes and attributions remained zero.

### Additional event observed during Stage 1

A separate late provider event, `TVwv713Ioqvspw`, for payment `pay_TVu7pnXqmHGySR` was received at 10:32:31 UTC. Its payment had been created earlier at 07:48:28 UTC. It was also safely correlated through the same order, processed once, and recorded as a failed Netbanking recovery attempt. It was not a new RecoveryCase. This explains why the immutable audit timeline contains two failed-attempt records before the successful retry.

## Stage 2 — successful recovery

Exactly one authorized retry was made through the same Payment Link using Razorpay Test Mode Netbanking and the mock-bank `Success` control.

### Provider evidence

| Field | Evidence |
| --- | --- |
| Razorpay event ID | `TVx4RQBSN7hCsR` |
| Payment ID | `pay_TVx3xkpxhgGous` |
| Payment Link ID | `plink_TTChN26OROddNO` |
| Order ID | `order_TTCltgAjeLeOPM` |
| Event type | `payment_link.paid` |
| Payment created | 30 Aug 2026 10:40:54 UTC / 16:10:54 IST |
| Webhook received | 30 Aug 2026 10:41:21.485748 UTC / 16:11:21.485748 IST |
| Payment status | `captured` |
| Captured | `true` |
| Payment Link status | `paid` |
| Amount paid | INR 1.00 |
| Method | Netbanking |

Two read-only provider GET requests confirmed the captured payment and paid Payment Link after webhook processing. No additional provider resource was created.

### Webhook and correlation evidence

- HTTP webhook delivery reached RecoverIQ through the configured HTTPS tunnel.
- Raw-body HMAC-SHA256 validation passed.
- Event `TVx4RQBSN7hCsR` was persisted exactly once with status `PROCESSED` and no failure reason.
- The existing Payment Link mapping resolved to the existing execution and RecoveryCase.
- Amount `100` and currency `INR` matched.
- The existing execution's Payment Link state changed to `PAID`.

### Database before and after

| Invariant | Before Stage 2 | After Stage 2 |
| --- | ---: | ---: |
| Total RecoveryCases | 2 | 2 |
| Target case status | `EXECUTING` | `RECOVERED` |
| Target ExternalExecutions | 1 | 1 |
| Target Payment Link executions | 1 | 1 |
| Target ExternalOutcomes | 0 | 1 |
| Target RecoveryAttributions | 0 | 1 |
| Total attributed revenue | INR 1.00 | INR 2.00 |

The successful outcome is verified, status `PAID`, amount 100 minor units, currency INR, payment `pay_TVx3xkpxhgGous`, and Payment Link `plink_TTChN26OROddNO`. The attribution uses source `PAYMENT_LINK_PAID` and contains the same payment, link, amount, and currency.

## Exactly-once evidence

- `TVx4RQBSN7hCsR` webhook rows: **1**
- Verified matching successful outcomes: **1**
- Matching recovery attributions: **1**
- `EXTERNAL_OUTCOME_VERIFIED` audit events: **1**
- `RAZORPAY_TEST_RECOVERY_ATTRIBUTED` audit events: **1**
- `RECOVERY_CASE_TRANSITIONED_RECOVERED` audit events: **1**
- Recovered value for the target case: **INR 1.00**

No live webhook was replayed. Duplicate idempotency was verified by the existing focused regression tests without altering provider state.

## Audit lifecycle

The immutable timeline preserves:

1. Aug 23: original failure receipt and signature validation.
2. Aug 23: RecoveryCase creation, deterministic model/policy review, and Human Review decision.
3. Aug 23: operator-approved Test Mode Payment Link creation.
4. Aug 30: authenticated failed recovery attempt(s), while the case remained `EXECUTING`.
5. Aug 30: authenticated `payment_link.paid` receipt and signature validation.
6. Aug 30: `EXTERNAL_OUTCOME_VERIFIED`.
7. Aug 30: `RAZORPAY_TEST_RECOVERY_ATTRIBUTED`.
8. Aug 30: `RECOVERY_CASE_TRANSITIONED_RECOVERED`.

The original Human Review decision remains unchanged. The UI continues to identify policy as the decision authority and AI as explanation-only.

## Browser verification

### Command Center

- Opportunities: **2**
- Recovered Revenue: **INR 2.00**
- Active Cases: **0**
- Success Rate: **100.0%**
- Pending Actions: **0**
- The separate seven-day trend remains INR 0.00 because it groups recovered value by the original case creation date rather than the Aug 30 recovery activity date.

### Recovery Queue

- Aug 23 target case: **RECOVERED**
- Aug 22 case: **RECOVERED**
- Total cases: **2**
- No Aug 30 RecoveryCase was created.
- The displayed dates remain the original case creation dates, as expected.
- A separate **Last Activity** column now derives from the latest immutable case audit event. The target case preserves its 23 Aug creation date and shows 30 Aug 2026, 4:11 pm as its latest activity.

### Target case

- Recovery state: **Recovered**
- Payment Link state: **Paid**
- External execution retained: **1**
- Verified outcome: **Paid / Yes / INR 1.00**
- Recovered revenue: **INR 1.00 / recorded exactly once**
- Payment completed: **30 Aug 2026, 4:11 pm IST**
- Outcome verified: **30 Aug 2026, 4:11 pm IST**
- Attribution recorded: **30 Aug 2026, 4:11 pm IST**

### Audit Timeline and Decision Trace

- Both failed-attempt audit entries remain immutable.
- The Aug 30 successful receipt, outcome, attribution, and recovered transition are visible.
- Recorded objects show one decision, two plans, one execution, one outcome, and one attribution.
- The deterministic decision remains `Human Review` with reason `Insufficient Context`.
- The interface explicitly states that models estimate, policy authorizes, providers verify, and AI explains.

## Validation

| Check | Result |
| --- | --- |
| Focused Razorpay tests | **35 passed** |
| Complete backend tests | **65 passed** |
| Frontend lint | **PASS** |
| Frontend TypeScript check | **PASS** |
| Frontend production build | **PASS** — 9 routes |
| Ruff | **PASS** |
| mypy | **PASS** — 38 source files |
| `git diff --check` | **PASS** — line-ending warnings only |

## Timestamp remediation

The Razorpay `payment_link.paid` payload's top-level `created_at` was `2026-08-23T12:01:36Z`, matching the Payment Link creation time, while the embedded payment was created on Aug 30, the Payment Link was updated on Aug 30, and the webhook was received on Aug 30. RecoverIQ had used that top-level field for `ExternalExecution.completed_at`, `ExternalOutcome.occurred_at`, and attribution `occurred_at`, causing the target-case outcome card to display Aug 23.

The future write path now resolves paid-link completion from the provider Payment Link `updated_at`, then the embedded payment `created_at`, and finally webhook receipt time. Payment Link `created_at` is never used as payment completion. The API read projection applies the same semantic resolution to preserved pre-hardening rows, so the existing live evidence was not rewritten. The UI separately labels:

- **Payment completed** from the resolved provider payment/link completion time.
- **Outcome verified** from `ExternalOutcome.created_at`.
- **Recovered revenue recorded** from `RecoveryAttribution.created_at`.
- **Webhook received** from immutable audit receipt time.

Naive SQLite UTC timestamps are explicitly interpreted as UTC before browser localization, so the IST UI now shows 4:11 pm rather than the raw 10:41 UTC clock value.

A focused regression proves that a Payment Link created on an earlier date and paid later stores and displays the later completion time. It also simulates a preserved pre-hardening row and verifies the corrected read projection without mutating provider payload evidence.

## Final checklist

- [x] Existing RecoveryCase reused
- [x] Existing Payment Link reused
- [x] Failed payment mapped through `order_id`
- [x] Failed attempt preserved while case remained `EXECUTING`
- [x] Exactly one Stage 2 payment attempt submitted
- [x] Razorpay payment captured
- [x] `payment_link.paid` received and HMAC-validated
- [x] Existing case and execution matched
- [x] ExternalOutcome created exactly once
- [x] RecoveryAttribution created exactly once
- [x] Target case transitioned to `RECOVERED` exactly once
- [x] Dashboard updated to INR 2.00 recovered and zero active cases
- [x] No duplicate case, link, execution, outcome, or attribution
- [x] Original policy authority preserved
- [x] Payment completion, outcome verification, and attribution timestamps use distinct semantics
- [x] Created date preserved and Last Activity displayed separately
- [x] No commit or push performed

 
 # #   R e c o v e r y   P r o o f   R e c o r d 
 
 T o   a d d r e s s   e x t e r n a l   a u d i t   r e q u i r e m e n t s   a n d   m a i n t a i n   t r a n s p a r e n c y ,   R e c o v e r y I Q   p r o v i d e s   a   D e t e r m i n i s t i c   R e c o v e r y   P r o o f   R e c o r d .   T h e   P r o o f   R e c o r d   a g g r e g a t e s   t h e   i n d e p e n d e n t   c o m p o n e n t s   o f   a   r e c o v e r y   l i f e c y c l e   ( d e c i s i o n ,   e x e c u t i o n ,   o u t c o m e ,   a t t r i b u t i o n ,   a n d   p r o v i d e r   e v i d e n c e )   i n t o   a   s i n g l e   r e a d - o n l y   v i e w .   
 
 T h e   P r o o f   R e c o r d   d o e s   N O T   u s e   b l o c k c h a i n   o r   c r y p t o g r a p h i c   i m m u t a b i l i t y .   I t   c o m p u t e s   a   c a n o n i c a l ,   d e t e r m i n i s t i c   S H A - 2 5 6   f i n g e r p r i n t   f r o m   t h e   e v i d e n c e   f i e l d s .   T h e   f i n g e r p r i n t   s e r v e s   a s   a n   i n t e g r i t y   c h e c k s u m   o v e r   t h e   s p e c i f i c   f i e l d s   a n d   v a l u e s   s h o w n   i n   t h e   P r o o f   R e c o r d ,   m a k i n g   a n y   c h a n g e s   t o   t h e   u n d e r l y i n g   d a t a b a s e   i m m e d i a t e l y   a p p a r e n t   b y   a l t e r i n g   t h e   f i n g e r p r i n t .  
 