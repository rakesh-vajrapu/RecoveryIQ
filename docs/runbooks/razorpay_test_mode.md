# Razorpay Test Mode Judge Demo Runbook

This runbook outlines the required configurations and steps to perform the Razorpay Test Mode Live Demo as part of the Judge evaluation process. 

**WARNING**: This feature is strictly constrained to `TEST` mode. Real money movement is mathematically and programmatically impossible when these constraints are enabled.

## 1. Required Azure App Settings
To enable the Razorpay Judge Demo in the Azure App Service, the following exact environment variables must be manually added/changed:

```env
EXECUTION_ENVIRONMENT=RAZORPAY_TEST
RAZORPAY_MODE=test
ENABLE_RAZORPAY_JUDGE_DEMO=true
RAZORPAY_KEY_ID=<rzp_test_...>
RAZORPAY_KEY_SECRET=<secret>
RAZORPAY_WEBHOOK_SECRET=<secret>
CELERY_TASK_ALWAYS_EAGER=true
RAZORPAY_TEST_SMOKE_ENABLED=false
```
*Note: You must obtain the test credentials (`rzp_test_...` and secrets) directly from your Razorpay Dashboard.*

## 2. Webhook Configuration
In your Razorpay Dashboard, configure the webhook to send events to the RecoveryIQ application.

**Exact Webhook URL:**
`https://recoveryiq-api-rakesh-2026.azurewebsites.net/webhooks/razorpay`

**Exact Webhook Events to Select:**
- Primary event: `payment_link.paid`
- Supported additional events: `payment_link.partially_paid`, `payment_link.expired`, `payment_link.cancelled`

*Ensure the `RAZORPAY_WEBHOOK_SECRET` you set in Azure matches the secret you use when setting up the webhook in Razorpay.*

## 3. Redeployment Process
If you change environment variables, you may need to redeploy or restart the Azure Backend.
**Exact Azure backend redeployment command/path using existing method:**
Use your standard GitHub Actions deployment pipeline, or from the Azure CLI:
```bash
az webapp restart --name recoveryiq-api-rakesh-2026 --resource-group <Your-Resource-Group>
```

## 4. Live ₹1,000 Judge Walkthrough
Once the backend and frontend are live and connected, follow these exact steps in the RecoveryIQ dashboard:

1. Navigate to **Integrations > Razorpay**.
2. Verify the status panel shows **RAZORPAY TEST MODE CONNECTED**.
3. Click **PREPARE ₹1,000 TEST CASE**.
4. Click **CREATE ₹1,000 RAZORPAY TEST PAYMENT LINK**.
5. Wait for the link to be created, then click **OPEN RAZORPAY TEST PAYMENT LINK**.
6. Complete the test payment via the Razorpay test interface (use Razorpay's test card details).
7. Return to RecoveryIQ. The webhook will be received (`payment_link.paid`), the signature will be verified, provider state will be confirmed, and you will see the exact `100000` minor units (₹1,000.00 INR) mapped to local attribution.

## 5. Remaining Limitations
- **No Live Mode Allowed**: If `RAZORPAY_MODE=live` or `EXECUTION_ENVIRONMENT=RAZORPAY_LIVE` is set, all execution paths will fail closed.
- **Fixed Demo Amounts**: The demo strictly enforces `₹1,000.00` cases only.
- **Isolated Tests**: Automated internal safety tests mock the gateway and never make real Razorpay network calls.
