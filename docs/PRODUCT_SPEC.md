# RecoverIQ Product Specification

## Product thesis

RecoverIQ is a bounded control plane for safe adaptive multi-step recovery of failed recurring payments. It summarizes observable payment and episode state, predicts the incremental value of allowed actions, applies deterministic safety policy, executes only approved bounded interventions, replans after observed failure, and attributes recovered revenue once.

RecoverIQ is being built for Razorpay Buildathon 2026, Track 03: AI Revenue Recovery. Its evidence must come from reproducible simulation and Razorpay Test Mode—not fabricated dashboard values or live customer money.

## Problem and target user

Recurring payments fail for materially different reasons: insufficient balance, expired instruments, authentication requirements, issuer outages, network instability, and mandate problems. A fixed sequence treats those situations and the outcome of each prior intervention as equivalent. A safe adaptive controller can change its next bounded action after observing failure while limiting retries, contacts, cost, and customer friction.

The primary users are merchant revenue-operations and payment-operations teams responsible for subscription renewal performance. Secondary users are engineers and risk reviewers who need a defensible decision trace and an audit trail.

## Business value

RecoverIQ aims to increase net recovered revenue while reducing unnecessary retries and customer contacts. It must express value in minor currency units and separate gross recovered amount from costs. Simulation results are always labelled **SIMULATED**; Razorpay results are always labelled **TEST MODE**. Neither may be represented as live revenue.

## Workflow and differentiator

1. Ingest and durably identify a payment event.
2. Normalize the customer, subscription, payment method, issuer, and failure context.
3. Construct observable customer, subscription, and current recovery-episode state.
4. Generate feasible bounded actions for the current decision index.
5. Score permitted candidates and estimate incremental expected recovery value (ERV).
6. Apply deterministic support, retry/contact, horizon, feasibility, and stopping rules.
7. Execute one action, observe its attributable outcome, and replan only if unresolved.
8. Stop after recovery, review, STOP, horizon, or three autonomous interventions.
9. Attribute revenue at most once and record every decision/action in an audit trail.

The product differentiator is safe, evidence-based adaptation across a short recovery episode rather than blindly replaying one fixed workflow. Phase 4 and Phase 5 found that Detector V2/payment-health features did not improve primary recovery prediction or policy outcomes, so they are no longer a headline revenue claim. Detector V2 remains advisory operational observability for dashboards, investigations, and later incident explanation; it cannot authorize or block recovery.

Phase 6 supplies the first apples-to-apples full-horizon evidence for that thesis. On its sealed synthetic validation, bounded RecoverIQ exceeded Fixed Retry, Reminder + Retry, the simple observable sequential rule, and the best-global sequence on recovery and net value with zero violations. It did not exceed the probability-only policy: ERV/support decisions traded a small amount of gross recovery for fewer contacts. Product claims must preserve both findings and must never generalize simulator value into live revenue.

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

Held-out evaluation compares RecoverIQ against fixed retry, Reminder + Retry, strong transparent sequential rules, probability-only selection, and an evaluation-only bounded oracle on identical full-horizon scenarios. Primary measures are recovery rate, SIMULATED gross recovered amount, net recovery value, and policy violations. Guardrails include unnecessary retries, contacts, action count, friction efficiency, human review/STOP, Model V2 quality by decision index, calibration, latency, and throughput.

No target number is asserted before the simulator and evaluation harness exist.

## Definition of done

A reviewer can clone the repository, install locked dependencies, run a seeded benchmark, start the API and UI without external credentials, inspect a degradation-aware decision trace, run the tests, and reproduce reported results. Optional credentials unlock explicit Gemini smoke tests and Razorpay Test Mode only. Core recovery continues when Gemini, Redis, or an external payment API is unavailable, according to documented fallbacks and policy.
