# Razorpay Test Mode Demo Runbook

This is a human-operated Test Mode demonstration. It creates no live-money transaction and does not prove production recovery lift. Use only synthetic customer data and Razorpay Test Mode payment instruments.

## Prepare the endpoint and credentials

1. Log in to the Razorpay Dashboard and visibly switch to **Test Mode**.
2. Generate or retrieve Test Mode API keys under Account & Settings → API Keys. Do not paste them into source code, chat, screenshots, or this document.
3. Make `POST /webhooks/razorpay` reachable at a controlled public HTTPS URL. Razorpay cannot deliver to localhost. Use a staging host or the current official [local webhook testing guidance](https://razorpay.com/docs/webhooks/validate-test/); RecoverIQ never exposes the machine automatically.
4. In Test Mode, open Account & Settings → Webhooks → Add New Webhook. Set the URL to `https://<your-host>/webhooks/razorpay`.
5. Generate a strong, separate webhook secret and configure it in the Dashboard. This is not the API Key Secret.
6. Subscribe to `subscription.pending`, `subscription.charged`, `payment_link.paid`, `payment_link.partially_paid`, `payment_link.expired`, and `payment_link.cancelled`. `payment.failed` is optional supplementary evidence.
7. Create `apps/api/.env` or set process variables without committing them:

```env
APP_ENV=development
EXECUTION_ENVIRONMENT=RAZORPAY_TEST
RAZORPAY_MODE=test
RAZORPAY_TEST_SMOKE_ENABLED=false
RAZORPAY_KEY_ID=<test-key-id>
RAZORPAY_KEY_SECRET=<test-key-secret>
RAZORPAY_WEBHOOK_SECRET=<same-separate-webhook-secret-as-dashboard>
DATABASE_URL=sqlite:///./recoveriq.db
CELERY_TASK_ALWAYS_EAGER=true
```

8. Apply migrations and start the API:

```powershell
Set-Location apps/api
uv sync --dev --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For a production-shaped asynchronous demonstration, set `CELERY_TASK_ALWAYS_EAGER=false`, configure Redis, and run a second process:

```powershell
uv run celery -A app.celery_app.celery_app worker --loglevel=INFO
```

Eager mode uses the same idempotent processing service inline and needs no worker, but it does not prove fast asynchronous acknowledgement.

## Trigger a real Test Mode subscription failure

9. In the Test Mode Dashboard, create or use a synthetic test Subscription according to Razorpay's [Test Subscriptions guide](https://razorpay.com/docs/payments/subscriptions/test/). Do not use real customer PII.
10. Trigger a subsequent charge using **Charge this now**, choose the documented failure outcome, and wait for `subscription.pending` in Dashboard webhook logs.
11. Confirm the event was accepted by RecoverIQ. A valid new event returns HTTP `202`; an already persisted event ID safely returns HTTP `200` with `duplicate`.
12. List recent cases, copy the relevant Test Mode case ID, and inspect it:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/recovery-cases?limit=20
Invoke-RestMethod http://127.0.0.1:8000/api/recovery-cases/<case-id>
```

13. Verify the response distinguishes the frozen decision from external capability. With incomplete first-event history, the expected safe result is `HUMAN_REVIEW / INSUFFICIENT_CONTEXT`; no fabricated Model V2 input is allowed. If a future complete adapter produces an executable `CREATE_PAYMENT_LINK` policy action, execute only that approved plan.
14. Otherwise invoke the explicitly labelled operator fallback:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/recovery-cases/<case-id>/test-payment-link
```

Confirm `execution_mode=RAZORPAY_TEST`, `state=SUCCEEDED`, `payment_link_status=ISSUED`, and a Test Mode `provider_url`. Repeating the command must return the same execution and must not create another provider link.

## Complete and verify the alternate Test Mode recovery

15. Open the returned Test Mode Payment Link URL in a browser.
16. Complete the payment with Razorpay's Test Mode flow and choose the documented success outcome. Use only Test Mode data.
17. Observe `payment_link.paid` in the Dashboard webhook delivery log and a 2xx RecoverIQ response.
18. Re-fetch the case and audit trail:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/recovery-cases/<case-id>
Invoke-RestMethod http://127.0.0.1:8000/api/recovery-cases/<case-id>/audit
```

The case must be `RECOVERED`, the link `PAID`, and there must be exactly one `RAZORPAY_TEST` attribution for the exact amount/currency. The trace should contain receipt/signature validation, normalization, case/context/decision/capability records, the operator fallback, create request/result, paid outcome validation, attribution, and terminal case transition.

The original Subscription may remain `pending`. Correct interpretation: **outstanding revenue was recovered through an alternate Razorpay Test Mode Payment Link**. Do not state that the Payment Link repaired the subscription mandate or state.

## Optional smallest API smoke

If a public webhook URL or Subscription setup is not ready, a credential-only smoke can create at most one ₹1.00 Test Mode link and fetch it. Set `RAZORPAY_TEST_SMOKE_ENABLED=true` only for that explicit invocation:

```powershell
Set-Location apps/api
$env:EXECUTION_ENVIRONMENT = "RAZORPAY_TEST"
$env:RAZORPAY_MODE = "test"
$env:RAZORPAY_TEST_SMOKE_ENABLED = "true"
uv run python -m app.integrations.razorpay.smoke
```

This can prove the API credential/create/fetch boundary, but without genuine webhook receipt the complete end-to-end status remains **PARTIAL**, not PASS. Reset the opt-in to `false` afterward.
