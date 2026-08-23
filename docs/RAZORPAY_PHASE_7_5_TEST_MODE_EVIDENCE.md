# RecoverIQ Phase 7.5 — Razorpay Test Mode Evidence

Generated: `2026-08-22T12:55:15.749Z`

Repository commit tested: `f0f5df21924d6343b1163c3ac94acb3a0b692f04`

Execution boundary: `RAZORPAY_TEST` / provider mode `test`

## Scope and safety

This report records genuine Razorpay Test Mode evidence for one synthetic INR Payment Link. It contains no API credentials, webhook secret, raw webhook body, signature value, customer PII, provider entity ID, provider event ID, RecoverIQ case ID, correlation ID, or Payment Link URL.

- Gemini was not started.
- No Subscription Test Mode flow was run.
- No Simulator, Detector V2, Recovery Model V2, Sequential Policy V2, or final-evaluation seed artifact was modified or exercised.
- Exactly one Razorpay Test Mode resource was created: one non-partial Payment Link for `100` minor units (`INR 1.00`).
- No second Payment Link create request was issued.

## External activity counts

| Activity | Count | Evidence |
|---|---:|---|
| Real Razorpay API requests | 3 | One Payment Link create and two fetches of that same provider ID |
| Razorpay Test Mode resources created | 1 | One Payment Link |
| Real Razorpay webhooks received | 1 | One provider-origin `payment_link.paid` delivery, HTTP 202 |
| Local duplicate replays | 1 | Same persisted provider event ID, HTTP 200 `duplicate` |

## Result matrix

| Invariant | Result | Evidence |
|---|---|---|
| Payment Link create | PASS | Provider returned a link; normal `ExternalExecution` path persisted it |
| Payment Link fetch | PASS | Provider ID, reference, amount, currency, status, and URL matched persisted execution |
| `payment_link.paid` received | PASS | One processed webhook row and one HTTP 202 provider delivery |
| Signature header present | PASS | The endpoint rejects a missing header before persistence; this delivery reached the post-verification receipt path |
| Raw-body HMAC-SHA256 | PASS | One `WEBHOOK_SIGNATURE_VALIDATED` audit with method `HMAC_SHA256_RAW_BODY` |
| Provider event ID persisted | PASS | Non-empty unique provider event ID is present on the webhook row |
| Event deduplication | PASS | Replay returned HTTP 200 `duplicate`; webhook row count remained one |
| Payment Link ID/reference match | PASS | Both matched the existing persisted execution |
| Amount/currency match | PASS | Link amount and amount paid were `100`; currency was `INR` |
| External outcome | PASS | Exactly one verified `PAID` outcome linked to the webhook and execution |
| Recovery attribution | PASS | Exactly one `PAYMENT_LINK_PAID` attribution for `100 INR` |
| Recovery case transition | PASS | Case is `RECOVERED`; exactly one recovered-transition audit exists |
| Duplicate replay side effects | PASS | Outcome, attribution, transition, webhook row, and original payload-hash counts/identities were unchanged |
| Full Payment Link E2E | PASS | Real create/fetch, manual Test payment, real signed webhook, validation, persistence, attribution, recovery, and replay deduplication all passed |

## Persisted state after the real webhook

- Webhook processing status: `PROCESSED`
- External execution state: `SUCCEEDED`
- Payment Link status: `PAID`
- RecoveryCase status: `RECOVERED`
- Webhook rows: `1`
- ExternalOutcome rows for the case: `1`
- RecoveryAttribution rows for the case: `1`
- `RECOVERY_CASE_TRANSITIONED_RECOVERED` audit events: `1`

## Ordered sanitized audit trail

1. `2026-08-22T12:44:33.433433` — `OPERATOR_APPROVED_EXECUTION_FALLBACK`
   - Action: `CREATE_PAYMENT_LINK`
   - Capability: `REAL_TEST_EXECUTION`
   - Initiator: `OPERATOR_INITIATED`
2. `2026-08-22T12:44:33.456574` — `PAYMENT_LINK_CREATE_REQUESTED`
   - Amount: `100` minor units
   - Currency: `INR`
   - Execution mode: `RAZORPAY_TEST`
3. `2026-08-22T12:44:34.589716` — `PAYMENT_LINK_RETURNED`
   - Status: `ISSUED`
   - Reference and amount verified
4. `2026-08-22T12:49:07.490629` — `WEBHOOK_SIGNATURE_VALIDATED`
   - Method: `HMAC_SHA256_RAW_BODY`
5. `2026-08-22T12:49:07.490629` — `WEBHOOK_RECEIVED`
   - Event type: `payment_link.paid`
   - Execution mode: `RAZORPAY_TEST`
6. `2026-08-22T12:49:07.526543` — `EXTERNAL_OUTCOME_VERIFIED`
   - Status: `PAID`
   - Amount/currency: `100 INR`
7. `2026-08-22T12:49:07.527605` — `RAZORPAY_TEST_RECOVERY_ATTRIBUTED`
   - Source: `PAYMENT_LINK_PAID`
   - Amount/currency: `100 INR`
8. `2026-08-22T12:49:07.527605` — `RECOVERY_CASE_TRANSITIONED_RECOVERED`
   - Source: `PAYMENT_LINK_PAID`

## Duplicate replay proof

RecoverIQ intentionally does not persist the provider's raw webhook body or signature header. For the local replay, the stored redacted paid envelope was serialized, signed locally with the configured webhook secret, and sent with the same persisted provider event ID.

- Response: HTTP `200`, status `duplicate`
- Webhook rows before/after: `1 / 1`
- ExternalOutcome rows before/after: `1 / 1`
- RecoveryAttribution rows before/after: `1 / 1`
- Recovered-transition audits before/after: `1 / 1`
- Original provider payload hash: unchanged
- RecoveryCase remained: `RECOVERED`

This proves the authenticated duplicate-delivery path without retaining or disclosing the original sensitive request material.

## Regression and security checks

Post-live checks:

- Ruff: PASS
- Strict mypy: PASS (`44` source files)
- Pytest: PASS (`43` passed, `0` failed)

The suite includes settings/live-mode rejection, secret masking, health/status redaction, raw-body signature behavior, missing/invalid-signature rejection, provider gateway contracts, webhook persistence, event deduplication, Payment Link idempotency, amount/reference validation, outcome handling, and exactly-once attribution.

## Genuine issues

No application defects or security regressions were discovered, and no source-code fix was required. The intentional evidence limitation is that raw provider webhook bodies and signature values are not persisted; only the redacted payload and SHA-256 body digest are retained.
