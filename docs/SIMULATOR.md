# RecoverIQ Deterministic Simulator

## Purpose and boundary

Phase 2 provides a seeded, in-process recurring-payment environment for honest policy comparison. It is not a CSV faker and it is not connected to Razorpay. All issuers, merchants, customers, subscriptions, failures, prices, and recovery outcomes are synthetic.

The package has two deliberately separate data surfaces:

- `observation.py` contains immutable policy-visible records and `PaymentObservation`.
- `ground_truth.py` contains environment-owned latent state, true causes, instruments, incidents, and initial outcome probabilities.

A `RecoveryPolicy` receives only `PaymentObservation` plus the public synthetic cost configuration. `RecoveryEnvironment` owns `GeneratedScenario.ground_truth` and resolves action outcomes. The API, UI, Gemini providers, and future ML package are not dependencies of the simulator.

## Event architecture

`ScenarioGenerator` creates merchants, customers, subscriptions, hidden incidents, and staggered renewals. A stable priority queue processes incident start/end, payment-due, and delayed status-delivery events. Observable histories are updated only when a status event is delivered, so an observation at time `T` cannot contain an event observed after `T`.

Recovery evaluation uses a second event queue for scheduled actions. Execution stops after the first attributed success or an explicit `STOP`. `AttributionLedger` rejects a second recovery for the same payment.

## Synthetic population

The default configuration produces 20,000 attempts across five merchants, 4,000 customers, 5,000 subscriptions, and 120 simulated days. Scale is configurable. Attempts at smaller scales are sampled across the full horizon, rather than truncating the scenario to its earliest days.

Merchant-specific log-normal amount distributions create skewed low-, medium-, and high-value subscriptions, capped between configured minimum and maximum values. Each merchant has its own method mix and baseline success rate. Renewals are staggered across the billing cycle. Identifiers begin with `SIM_`; issuers are `ISSUER_A` through `ISSUER_D`. No PAN, CVV, OTP, provider payload, or real PII is generated.

## Hidden variables

Customer ground truth contains:

- liquidity propensity;
- historical reliability;
- nudge responsiveness;
- payment-method stability;
- instrument-update propensity;
- retry sensitivity.

Subscription truth contains instrument state. Payment truth contains the true failure cause, initial success probability, instrument state, and optional hidden incident membership. Incident truth contains its window, method/issuer scope, severity, health shift, and dominant hidden cause.

These values influence observable history and action outcomes but are absent from `PaymentObservation`.

## Observable variables

At failure-delivery time, a policy can see the synthetic entity IDs, amount, method, optionally missing issuer, observed failure reason/source, event and observation timestamps, attempt number, prior subscription counts, past customer success aggregate, recent six-hour scope aggregate, and up to five already-observed customer events.

It cannot see true cause, latent customer values, instrument state, incident membership or clearance time, future events, future action outcomes, or hidden response probabilities. Pydantic models reject extra fields, and tests inspect the public schema and event timestamps.

## Failures and data imperfections

Observable failure families are:

- `INSUFFICIENT_FUNDS`
- `ISSUER_UNAVAILABLE`
- `AUTHENTICATION_FAILURE`
- `INSTRUMENT_EXPIRED`
- `MANDATE_INACTIVE`
- `TEMPORARY_NETWORK_ERROR`
- `CUSTOMER_ACTION_REQUIRED`
- `UNKNOWN_TRANSIENT_ERROR`

Hidden causes overlap with observable reasons. A configurable fraction is ambiguous or unknown. Issuer values can be missing, and status events can arrive late. Therefore an observed reason does not identify one guaranteed successful action.

## Degradation incidents

Incidents affect one payment-method and synthetic-issuer scope for 12–36 hours by default. They reduce initial success probability and shift the hidden failure mix toward issuer or network causes. Policies never receive an `active_incident` flag. Incident truth is emitted separately so a future detector can be evaluated without contaminating policy inputs.

## Action semantics and outcome model

The stable action set is `WAIT`, `RETRY_NOW`, `RETRY_LATER`, `SEND_NUDGE`, `CREATE_PAYMENT_LINK`, `REQUEST_PAYMENT_METHOD_UPDATE`, `OFFER_ALTERNATE_METHOD`, `ESCALATE_TO_HUMAN`, and `STOP`. Actions carry execution time, delay, attempt number, intervention cost, and friction cost.

Recovery probability is a bounded response surface over hidden cause, customer responsiveness/update/retry tendencies, instrument state, active issuer health, action, elapsed time, prior retries, and prior contacts. It is intentionally simple, non-causal, and nontrivial:

- liquidity failures improve with later retries;
- issuer/network retries are poor during an incident and improve after it clears;
- expired/inactive instruments respond poorly to repeated retry and better to update/alternate actions;
- reminders depend on hidden customer responsiveness;
- repeated attempts and contacts accumulate friction.

No action always succeeds. Outcome draws are derived from a SHA-256 key containing seed, payment, action type, execution timestamp, and retry ordinal. Policy identity and action ID are excluded, so equivalent retries share counterfactual randomness across paired baselines.

## Baselines

`fixed_retry` waits six hours, retries, waits to twelve hours, retries again, then stops. The delay and maximum retries are configurable.

`reminder_then_fixed_retry` sends one generic reminder after five minutes and otherwise follows the same fixed retry schedule and stopping rule. It has no customer personalisation or degradation awareness.

Both policies are evaluated over the same failure observations and hidden environment. There is no ML, detector, Gemini selection, or RecoverIQ intelligent policy in Phase 2.

## Costs and attribution

All monetary values use integer minor INR units. Configured retry, message, payment-link, method-update, alternate-method, human-review, contact-friction, and retry-friction values are synthetic evaluation assumptions—not Razorpay prices. Net value is exactly:

`gross recovered amount - executed intervention cost - executed friction cost`

Only executed actions accrue cost. Gross recovery is credited once, to the first successful action.

## Reproducibility and artifacts

From the repository root:

```powershell
uv sync --project simulator --dev --locked
uv run --project simulator python -m recoveriq_simulator.cli generate --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli benchmark --seed 20260821
uv run --project simulator python -m recoveriq_simulator.cli inspect <experiment-id>
```

The same simulator version, seed, and configuration produces the same experiment ID, scenario digest, observations, hidden truth, and outcomes. The manifest uses the simulation clock start as a logical creation timestamp so generated artifacts remain reproducible.

Experiments are written to `artifacts/simulations/<experiment-id>/` with:

- `manifest.json`
- `observable_events.parquet`
- `payments.parquet`
- `subscriptions.parquet`
- `incident_ground_truth.parquet`
- `outcome_ground_truth.parquet`
- `baseline_results.json`
- `analysis.json`

Generated datasets are ignored by Git.

## Sanity analysis

The benchmark reports amount quantiles; payment-method, issuer, and failure distributions; overall failure rate; incident duration and count; observed success during/outside incidents; policy recovery/action/contact outcomes; and named assertions. The command fails if payment values are nonpositive, successes or failures disappear, the failure fraction leaves configured bounds, incident windows are invalid, incident deterioration is absent, one reason exceeds 75%, or a baseline recovers every failure.

## Limitations

This simulator is a controlled synthetic benchmark, not evidence of real provider or customer behaviour. The probability equations are hand-designed rather than estimated from production data. Customer state is static within this first version, apart from its time-dependent effects. Billing cadence is monthly, currency is INR, issuer scope is small, and recovery has no provider execution latency. A single seed is useful for reproducibility but not statistical confidence; later final evaluation must freeze strategies and report multiple seeds or intervals. Phase 2 baseline results must always be labelled `SIMULATED`.
