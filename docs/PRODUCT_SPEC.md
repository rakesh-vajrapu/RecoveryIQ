# RecoverIQ Product Specification

## Product thesis

RecoverIQ is a bounded control plane for recovering failed recurring payments. It determines whether a failure is an isolated customer event or part of broader payment-system degradation before choosing a recovery action. It then predicts the economic value of allowed actions, applies deterministic safety policy, executes only approved actions, observes authoritative outcomes, and attributes recovered revenue once.

RecoverIQ is being built for Razorpay Buildathon 2026, Track 03: AI Revenue Recovery. Its evidence must come from reproducible simulation and Razorpay Test Mode—not fabricated dashboard values or live customer money.

## Problem and target user

Recurring payments fail for materially different reasons: insufficient balance, expired instruments, authentication requirements, issuer outages, network degradation, and mandate problems. A fixed retry schedule treats those situations as equivalent. During issuer or payment-method degradation it can repeatedly send traffic into a failing route, waste retry capacity, annoy customers, and make eventual recovery less likely.

The primary users are merchant revenue-operations and payment-operations teams responsible for subscription renewal performance. Secondary users are engineers and risk reviewers who need a defensible decision trace and an audit trail.

## Business value

RecoverIQ aims to increase net recovered revenue while reducing unnecessary retries and customer contacts. It must express value in minor currency units and separate gross recovered amount from costs. Simulation results are always labelled **SIMULATED**; Razorpay results are always labelled **TEST MODE**. Neither may be represented as live revenue.

## Workflow and differentiator

1. Ingest and durably identify a payment event.
2. Normalize the customer, subscription, payment method, issuer, and failure context.
3. Compare individual failure evidence with aggregate payment-health evidence.
4. Detect whether a matching degradation incident is active.
5. Score permitted candidate actions and estimate expected recovery value (ERV).
6. Apply deterministic policy, confidence gates, retry/contact limits, and stopping rules.
7. Execute, wait, abstain, or send the case to human review.
8. Observe an authoritative outcome and attribute revenue at most once.
9. Record every meaningful decision and action in an append-oriented audit trail.

The product's differentiator is step 3: aggregate health changes the appropriate intervention for an individual payment. A normally healthy UPI/issuer route dropping sharply across a credible sample should suppress immediate retries even when a customer-level model might otherwise recommend one.

## V1 scope

V1 covers failed subscription or recurring-payment recovery in two clearly labelled environments:

- deterministic, seeded simulation for development and evaluation;
- Razorpay Test Mode for webhook validation and a bounded end-to-end demonstration.

The planned action space is:

- `RETRY_NOW`;
- `RETRY_LATER`;
- `WAIT_FOR_RECOVERY`;
- `SEND_PAYMENT_LINK`;
- `CUSTOMER_NUDGE`;
- `HUMAN_REVIEW`;
- `STOP`.

An action is a candidate, not an authorization. The policy engine remains authoritative.

## Non-goals

V1 is not a chatbot, fraud engine, abandoned-cart system, general customer-support platform, B2B collections product, reconciliation system, or live-mode payment processor. It will not collect PAN, CVV, OTP, or raw bank credentials. It will not use Gemini to set payment state, determine whether money moved, approve policy, or execute actions.

## Success metrics

Future held-out evaluation will compare RecoverIQ against fixed retry and retry-plus-reminder baselines on identical scenarios. Primary measures are recovery rate, SIMULATED gross recovered amount, net recovery value, and policy violations. Guardrail measures include unnecessary retries, contact count, actions per case, human-review and abstention rates, degradation precision/recall/delay, Brier score, calibration error, latency, throughput, Gemini calls, and fallback rate.

No target number is asserted before the simulator and evaluation harness exist.

## Definition of done

A reviewer can clone the repository, install locked dependencies, run a seeded benchmark, start the API and UI without external credentials, inspect a degradation-aware decision trace, run the tests, and reproduce reported results. Optional credentials unlock explicit Gemini smoke tests and Razorpay Test Mode only. Core recovery continues when Gemini, Redis, or an external payment API is unavailable, according to documented fallbacks and policy.

