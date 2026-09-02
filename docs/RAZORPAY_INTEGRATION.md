# Razorpay Test Mode Integration

## Scope and evidence level

Integration version `1.0.0` implements RecoverIQ's Razorpay **Test Mode only** boundary. It proves an offline-verifiable provider contract, durable webhook ingestion, isolated Payment Link execution, reconciliation, and exactly-once Test Mode attribution. It does not enable Live Mode, repair a Razorpay Subscription through a Payment Link, or establish production recovery lift.

Completion has two distinct levels:

- **Level A — offline integration:** fixtures, fake gateway, signature/security tests, idempotency, state transitions, migration, and all regression checks pass without credentials or internet.
- **Level B — live Razorpay Test Mode:** claimed only after an explicitly opted-in real Test Mode call or the complete manual webhook flow actually occurs. Mocks never satisfy Level B.

Level B is complete for one synthetic INR 1.00 Payment Link. The sanitized evidence records create/fetch, a real signed `payment_link.paid` webhook, exact reference/amount/currency validation, one outcome, one attribution, one recovery transition, and a no-side-effect duplicate replay. It does not claim Subscription E2E or Live Mode. See [Phase 7.5 Test Mode Evidence](RAZORPAY_PHASE_7_5_TEST_MODE_EVIDENCE.md).

## Official contracts reviewed

Razorpay's current official documentation is the source of truth. The implementation uses these narrowly summarized contracts:

| Contract | Implemented interpretation | Official source |
|---|---|---|
| API authentication | HTTPS Basic Auth with Test Mode Key ID and Key Secret; secrets remain server-side. | [API Authentication](https://razorpay.com/docs/api/authentication/) |
| Subscription Test Mode | A subsequent test charge can be forced to success or failure from the Dashboard; failure produces pending behavior and success produces charged behavior. | [Test Subscriptions](https://razorpay.com/docs/payments/subscriptions/test/) |
| Subscription events | `subscription.pending` represents a failed charge/pending subscription and `subscription.charged` represents a successful charge. | [Subscribe to Subscription Webhooks](https://razorpay.com/docs/payments/subscriptions/subscribe-to-webhooks/), [Subscription Webhook Payloads](https://razorpay.com/docs/webhooks/subscriptions/) |
| Webhook signature | Validate `X-Razorpay-Signature` as HMAC-SHA256 using the webhook secret and the exact raw request body; parsing or re-serialization before validation is forbidden. | [Validate and Test Webhooks](https://razorpay.com/docs/webhooks/validate-test/) |
| Delivery/idempotency | Delivery is at least once; use unique `x-razorpay-event-id`; deliveries can be out of order; return 2xx within five seconds. | [Webhook Best Practices](https://razorpay.com/docs/webhooks/best-practices/), [Webhook Setup](https://razorpay.com/docs/payments/dashboard/account-settings/webhooks/) |
| Payment Link creation | `POST /v1/payment_links/`; amount is in currency subunits; `reference_id` is unique and at most 40 characters; notes allow at most 15 safe key/value pairs; partial payment defaults off. Test Mode allows at most 30 links per business. | [Create a Standard Payment Link](https://razorpay.com/docs/api/payments/payment-links/create-standard/) |
| Payment Link lookup | Fetch a link by provider ID, or fetch/filter all Standard Payment Links by unique `reference_id` for reconciliation. | [Fetch by ID](https://razorpay.com/docs/api/payments/payment-links/fetch-id-standard/), [Fetch by Reference](https://razorpay.com/docs/api/payments/payment-links/fetch-all-standard/) |
| Payment Link outcomes | Handle `payment_link.paid`, `payment_link.partially_paid`, `payment_link.expired`, and `payment_link.cancelled`; provider states include created/issued, paid, partially paid, expired, and cancelled. | [Payment Link Webhook Events](https://razorpay.com/docs/webhooks/payment-links/), [Payment Link States](https://razorpay.com/docs/payments/payment-links/states/) |
| General payment failure | `payment.failed` exposes normalized failure reason/source/step when present; unknowns remain explicit. | [Payment Webhook Events](https://razorpay.com/docs/webhooks/payments/) |

No undocumented Razorpay idempotency header, retry endpoint, subscription repair operation, messaging action, or recurring-payment retry operation is assumed.

## Configuration and Live Mode exclusion

The application execution environment is exactly one of:

- `SIMULATION` — default; external execution is disabled.
- `RAZORPAY_TEST` — enables the explicit Test Mode boundary when the relevant credentials exist.

`RAZORPAY_MODE` accepts only `test`. There is no `RAZORPAY_LIVE` enum or route. When a Key ID is supplied, settings require Razorpay's documented `rzp_test_` prefix; every other prefix is rejected. See the official [Payments Quickstart](https://razorpay.com/docs/payments/quickstart/) for the Test/Live prefix contract. Missing credentials do not block startup, health, simulation, migrations, or offline tests.

Secrets are limited to `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET`. They are Pydantic `SecretStr` values, never returned by health/status endpoints, never stored in audit metadata or webhook rows, and never written into Payment Link notes.

## Adapter and request contract

`RazorpayGateway` isolates four operations:

- `create_payment_link`;
- `fetch_payment_link`;
- `find_payment_link_by_reference`;
- `verify_webhook`.

`HttpRazorpayGateway` is the real Test Mode adapter. Normal tests use `FakeRazorpayGateway` or `httpx.MockTransport`; they never create provider resources. The create request uses INR minor units, `accept_partial=false`, disables provider notification/reminders, uses no customer PII, and writes only the RecoveryCase/correlation/mode/initiator identifiers into notes.

The deterministic reference is `riq_<recovery-case-uuid-hex>`, truncated to the documented 40-character maximum. A database-unique application idempotency key, unique plan, unique provider reference, and unique provider entity ID ensure one recovery action produces at most one Payment Link.

## Execution capability registry

The registry prevents a policy label from being mistaken for an external side effect.

| RecoverIQ action | Capability | Phase 7 meaning |
|---|---|---|
| `CREATE_PAYMENT_LINK` | `REAL_TEST_EXECUTION` | Documented Standard Payment Link create/fetch flow. |
| `WAIT`, `RETRY_NOW`, `RETRY_LATER`, delay variants | `INTERNAL_SCHEDULE_ONLY` | RecoverIQ may schedule; no Razorpay operation is claimed. |
| `SEND_NUDGE` | `RECOMMENDATION_ONLY` | No messaging provider is implemented. |
| `REQUEST_PAYMENT_METHOD_UPDATE` | `RECOMMENDATION_ONLY` | No documented provider mutation is invented. |
| `OFFER_ALTERNATE_METHOD` | `RECOMMENDATION_ONLY` | It is not silently relabelled as a Payment Link. |
| `ESCALATE_TO_HUMAN`, `STOP` | `RECOMMENDATION_ONLY` | Internal decision/no external provider call. |
| `HIDDEN_ORACLE_ACTION` | `SIMULATION_ONLY` | Evaluation-only concept and impossible to execute. |

The persisted boundary remains `RecoveryDecision → RecoveryExecutionPlan → ExternalExecution → ExternalOutcome/RecoveryAttribution`. A selected action never implies provider capability.

## Webhook path and fast acknowledgement

`POST /webhooks/razorpay` performs this order:

1. read the exact raw bytes, enforcing a 1 MiB limit;
2. require `X-Razorpay-Signature` and `x-razorpay-event-id`;
3. verify HMAC-SHA256 with the separate webhook secret;
4. parse JSON only after validation;
5. redact/minimize the payload, compute SHA-256, and insert the unique event row plus signature/receipt audit records;
6. commit, dispatch processing, and return `202`; a duplicate returns `200` without another domain/audit side effect.

With `CELERY_TASK_ALWAYS_EAGER=false`, only verification, minimal persistence, and dispatch occur before the response. The worker loads the event by UUID and processes it idempotently. Eager local/test mode deliberately executes the identical task service inline for deterministic development, so it does not demonstrate the production response-time property.

Razorpay's public endpoint requirement means `localhost` cannot receive provider calls. The app does not open a tunnel automatically. Use a controlled public HTTPS staging endpoint or follow the current official [webhook testing guidance](https://razorpay.com/docs/webhooks/validate-test/), which currently documents zrok as a localhost option and lists blocked testing domains.

## Durable event and ordering rules

`external_webhook_events.provider_event_id` is unique. Stored fields are provider, event type, receive/provider timestamps, payload checksum, processing status, correlation ID, safe external entity IDs, a redacted Test Mode payload, failure category, and completion time. Headers and secrets are never persisted. Email, phone/contact, card objects, and unrelated notes are discarded; only `recoveriq_*` notes survive.

Alembic revision `4d7a0f3b21c8` adds portable SQLite/PostgreSQL tables for `ExternalWebhookEvent`, `ExternalEntityMapping`, `FailureEvent`, `RecoveryDecisionRecord`, `RecoveryExecutionPlan`, `ExternalExecution`, `ExternalOutcome`, and `RecoveryAttribution`. `ExternalOutcome` is the verified provider fact; `RecoveryAttribution` is the separate exactly-once business interpretation bound to that fact.

`external_entity_mappings.last_provider_event_at` provides per-subscription event ordering. An older/equal `subscription.pending` cannot override a newer `subscription.charged`; RECOVERED is terminal; duplicate paid outcomes see the existing unique attribution. Unknown events are retained as `IGNORED` rather than trusted or dropped invisibly.

Retention must be defined by the deploying merchant. Even redacted Test Mode payloads contain opaque provider identifiers and operational payment metadata, so they should follow the same access control and deletion policy as audit records.

## Subscription normalization and frozen policy boundary

`subscription.pending` safely upserts opaque Merchant, Customer, Subscription, Payment, and PaymentAttempt records, then creates one FailureEvent and one RecoveryCase for the failed provider payment. Failure reason/source/step use documented values when present and `unknown` otherwise.

`RazorpayContextAdapter` exposes observed Test Mode fields but refuses to zero-fill incomplete historical customer/subscription observations or assume that provider category strings equal the frozen simulator vocabulary. For the first external event, it therefore records Model V2 `2.0.0` / Sequential Policy V2 `2.0.0` as `HUMAN_REVIEW: INSUFFICIENT_CONTEXT`. This is a successful safety decision, not a model failure. It does not modify, import into, retrain, or retune the frozen model/policy.

The operator may then explicitly request `CREATE_PAYMENT_LINK`. The audit trail labels that plan `OPERATOR_INITIATED` and `OPERATOR_APPROVED_EXECUTION_FALLBACK`; it never claims that AI selected the link.

`subscription.charged` can close an active case only when the subscription mapping, exact amount, and currency agree. It separately updates the Razorpay subscription state to active. A Payment Link payment never changes the stored subscription state: it means only “Recovered outstanding revenue through an alternate Razorpay Test Mode Payment Link.”

## Payment Link lifecycle and unknown outcomes

External execution states are `PLANNED`, `QUEUED`, `EXECUTING`, `SUCCEEDED`, `FAILED`, `UNKNOWN`, and `CANCELLED`. Provider Payment Link states are separately normalized to `ISSUED`, `PAID`, `PARTIALLY_PAID`, `EXPIRED`, and `CANCELLED`.

Create behavior is conservative:

- 400/401/403 validation/auth failures are permanent and are not retried blindly.
- Transport timeouts, network failures, 429, 5xx, and invalid responses after a create attempt are potentially ambiguous and become `UNKNOWN`.
- An unknown execution is looked up by stored provider ID or unique reference. A matching link resolves the same execution; a missing or failed lookup keeps replacement creation blocked.
- Fetch operations use at most three bounded attempts because they are read-only.

`payment_link.paid` attributes recovery only after a strict three-layer Provider Truth Triangulation:
1. The webhook must be authenticated via HMAC-SHA256 signature verification.
2. The system must independently fetch the Payment Link state from the provider to confirm it is actually paid, guarding against isolated webhook bugs.
3. Link ID/reference, optional RecoverIQ case/correlation notes, exact expected amount, full `amount_paid`, INR currency, and paid status all must agree with local invariants.

If the independent fetch transiently fails, the event remains `PENDING` for a deterministic retry. If it confirms a mismatch, it marks `MISMATCH`, persists an audit event, and denies the attribution. `partially_paid` does not recover the case. Expired/cancelled links terminate the external execution without attributing recovery.

Attribution is unique per RecoveryCase and external execution/payment. It stores `RAZORPAY_TEST`, external opaque IDs, amount/currency, provider event time, and source (`PAYMENT_LINK_PAID` or `SUBSCRIPTION_CHARGED`). Test rupees are never production revenue.

## API surface

- `GET /api/integrations/razorpay/status` — safe configuration/capability state; no secrets.
- `GET /api/recovery-cases?limit=20` — recent case identifiers and statuses.
- `GET /api/recovery-cases/{id}` — payment, decision, plan, execution, and attribution state.
- `GET /api/recovery-cases/{id}/audit` — correlation-scoped redacted audit trace.
- `POST /api/recovery-cases/{id}/test-payment-link` — explicit Test Mode operator action. It is unavailable in simulation, requires Test API credentials, returns an existing execution on replay, and never creates a second link for the case.
- `POST /webhooks/razorpay` — signed provider delivery endpoint.

## Opt-in live Test Mode smoke

The smoke command is never run by tests or startup. It requires all of `EXECUTION_ENVIRONMENT=RAZORPAY_TEST`, `RAZORPAY_MODE=test`, `RAZORPAY_TEST_SMOKE_ENABLED=true`, and Test API credentials:

```powershell
Set-Location apps/api
uv run alembic upgrade head
uv run python -m app.integrations.razorpay.smoke
```

It creates at most one ₹1.00 Test Mode Payment Link for a stable local smoke RecoveryCase, persists the external ID, and fetches it once. Re-running returns/reconciles the unique persisted execution rather than creating another resource. It does not create a Subscription, expose credentials, or claim webhook E2E success.
