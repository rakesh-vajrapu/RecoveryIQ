# RecoverIQ ERV Policy V1

## Phase boundary and pre-registration status

This document was pre-registered before any Phase 5 policy seed was generated. Development, policy freeze, and the one-time validation are now complete. The recorded order was preserved: the development-only personalization audit ran first, baseline mappings and policy configuration were frozen, and only then were the ten validation seeds executed once.

Simulator `0.3.0`, Detector V1, Detector V2, Recovery Model V1 training/hyperparameters/calibration, and all Phase 4 results remain frozen at commit `eb2da6bc7b32b6ffd0b646ee1ebe065bf585bba0`. Detector V2 is an **advisory feature source only**. WATCH and CONFIRMED cannot authorize, block, force, or stop an action. The negative Phase 4 health-feature ablation remains part of the evidence.

Phase 5 evaluates first-intervention decisions only. It does not implement sequential replanning, production side effects, LLM integration, Razorpay, frontend policy controls, model retraining, detector retuning, or the overall-final benchmark.

## Registered policy seeds

- Policy development and learnability audit: `20270501`–`20270510`.
- One-time policy validation: `20270601`–`20270610`.
- Optional stress group: `20270701`–`20270705`; not required for the primary checkpoint.
- Overall-final Buildathon group: `20261101`–`20261120`, untouched and forbidden to policy commands.

Phase 4 held-out seeds `20270401`–`20270410` are forbidden to policy tuning. Validation cannot run until the development audit, ERV definition, costs, candidates, baseline mappings, feasibility rules, support rules, abstention threshold, safety rules, and policy configuration hash are frozen. The validation command must refuse overwrite.

## Development-first personalization audit

Before freezing RecoverIQ ERV Policy V1, the development audit reports:

- hidden oracle best-probability and best-ERV action distributions;
- frozen primary Model V1 top-probability action distribution;
- the development-best global action and complete global action ordering;
- a minimum-support observable failure-reason lookup with global fallback;
- a failure-reason plus payment-method lookup only for cells with at least 500 decisions;
- probability ranking, ERV regret, and context/action heterogeneity by observable failure reason, payment method, amount, customer payment history, subscription tenure, prior retry count, payment-health evidence, and time since failure.

The global and lookup policies maximize mean hidden oracle ERV on development only. Hidden truth is permitted solely in this development evaluation/selection layer. It is never a policy input. Failure-reason cells require at least 200 decisions; unsupported cells fall back to the global action. Ties use the frozen candidate order below.

The audit determines whether Model V1 learned context-sensitive action preferences or mostly global action averages. A lightweight conditional action-distribution/effect analysis replaces expensive SHAP interaction computation unless that computation is demonstrably cheap. No positive personalization claim is made unless later validation beats simple frozen comparators.

## Candidate actions and first-intervention semantics

The frozen ordered candidate set contains nine modeled interventions:

1. `RETRY_NOW`, delay 0 hours;
2. `RETRY_LATER_2H`;
3. `RETRY_LATER_6H`;
4. `RETRY_LATER_12H`;
5. `RETRY_LATER_24H`;
6. `SEND_NUDGE`;
7. `CREATE_PAYMENT_LINK`;
8. `REQUEST_PAYMENT_METHOD_UPDATE`;
9. `OFFER_ALTERNATE_METHOD`.

STOP and HUMAN_REVIEW are policy outcomes, never Model V1 actions. All modeled delays execute inside the frozen 48-hour target horizon. The first-intervention benchmark treats each initial failed payment as one decision and does not feed a selected intervention back into another decision loop.

## Observable operational-profile assumptions

The simulator is not modified. A policy-evaluation adapter supplies deterministic, strategy-independent observable feasibility fields that are absent from Simulator V0.3.0:

- customer contact allowed for 95% of stable synthetic customer profiles;
- an existing active payment link for 3% of stable synthetic payment profiles;
- alternate-method workflow available for 90% of stable synthetic payment profiles;
- quiet hours from 22:00 inclusive to 07:00 exclusive in the scenario's UTC clock.

These values are generated with keyed deterministic randomness before strategy intervention. Policies receive only the resulting Boolean observations, never the seed, raw identity, hidden cause, incident membership, latent customer traits, oracle probability, or future outcome. They are **SYNTHETIC POLICY EVALUATION ASSUMPTIONS**, not production facts.

## Economic score and exact money arithmetic

For each model-scored candidate:

`ERV_minor = round(P48 × payment_amount_minor) − intervention_cost_minor − friction_cost_minor`

The calibrated probability is converted from its serialized decimal representation to `Decimal`; multiplication and half-up rounding occur in decimal arithmetic. Every stored monetary value is an integer minor-INR amount. Hidden simulator probabilities never enter ERV.

The primary cost regime is frozen as existing Simulator `BALANCED`, independent of policy results:

- retry operational cost 250 minor; retry friction 100 minor for the first retry;
- message 100, payment link 300, method update 400, alternate method 500 minor;
- first contact friction 400 minor, growing by the simulator's 1.8 multiplier for later contacts and capped at 8,000;
- human review 4,000 minor.

LOW_FRICTION and HIGH_FRICTION remain configuration-compatible but are not used to choose the primary validation regime. Costs are synthetic evaluation assumptions, not Razorpay pricing. Candidate actions carry their intervention and friction costs once; outcome evaluation does not subtract them again.

## Typed decision layers

Phase 5 keeps these boundaries separate:

1. observable decision context and deterministic candidate generation;
2. frozen Model V1 scoring and frozen isotonic calibration;
3. exact ERV calculation;
4. structured feasibility, support, and safety rules;
5. deterministic decision selection and abstention;
6. structured decision trace;
7. separate simulator-only outcome/oracle evaluation.

Core policy code must not import simulator ground truth or oracle helpers. Evaluation joins hidden outcomes only after a complete decision exists.

## Frozen feasibility and safety rules

Policy V1 registers these rule IDs and defaults before development:

- `MODEL_SCHEMA_INVALID`: REVIEW when the exact feature boundary cannot be constructed or scored.
- `RECOVERY_HORIZON_EXCEEDED`: BLOCK candidates executing after 48 hours.
- `MAX_RETRY_COUNT`: BLOCK retry when observable retry count is at least 2.
- `MIN_RETRY_INTERVAL`: BLOCK retry-now when the configured minimum interval of 0 hours is not met; the rule remains explicit for future configurations.
- `MAX_CONTACT_COUNT`: BLOCK customer contact when observable contact count is at least 2.
- `CUSTOMER_OPT_OUT`: BLOCK all contact actions when contact is not allowed.
- `QUIET_HOURS`: BLOCK immediate contact actions from 22:00–07:00 UTC.
- `DUPLICATE_PAYMENT_LINK`: BLOCK payment-link creation when an active link is observed.
- `ALTERNATE_METHOD_UNAVAILABLE`: BLOCK alternate-method offer when its workflow is unavailable.
- `LOW_SUPPORT`: REVIEW a candidate when its action has fewer than 1,000 Phase 4 training examples, its calibrated probability occupies a calibration bin with fewer than 100 examples, or a categorical value is unknown to the frozen pipeline.
- `NON_POSITIVE_ERV`: BLOCK a candidate whose ERV is zero or negative.
- `LOW_DECISION_MARGIN`: REVIEW when the selected threshold is not met.

Every candidate retains `PASS`, `BLOCK`, or `REVIEW` evidence with observed value, threshold, and reason. A blocked candidate cannot be selected. A REVIEW result for the highest-ERV non-blocked candidate produces HUMAN_REVIEW rather than silently falling through to a lower action. Detector state is absent from the hard-rule list.

If every candidate is blocked or has non-positive ERV, the decision is STOP. STOP and HUMAN_REVIEW execute no autonomous intervention. Human review incurs the configured synthetic review cost in evaluation but cannot receive automated recovery attribution.

## Support and abstention selection

Action support comes from the frozen Phase 4 training manifest. Reliability-bin support comes from the frozen calibration artifact's equal-width calibrated reliability bins. Schema and categorical support come from the frozen model pipeline. No new uncertainty estimator or model-confidence claim is introduced.

Development studies normalized ERV-margin candidates `0`, `0.001`, `0.0025`, `0.005`, and `0.01`, where:

- `absolute_erv_margin = top_erv − second_best_erv`;
- `normalized_erv_margin = absolute_erv_margin / payment_amount_minor`.

The selected threshold maximizes mean development simulated net recovery value subject to zero deterministic policy violations and at least 70% autonomous coverage. Ties within one minor unit choose greater autonomous coverage, then the smaller threshold. The threshold freezes before validation. It is called a decision margin, not model confidence.

## Frozen comparison strategies

The equivalent first-intervention view contains:

- fixed retry: `RETRY_LATER_6H`;
- generic reminder: `SEND_NUDGE`;
- development-frozen best global action;
- development-frozen failure-reason lookup;
- development-frozen failure-reason plus payment-method lookup when supported;
- frozen Model V1 highest-probability policy, with feasibility but no economic selection;
- RecoverIQ ERV Policy V1;
- RecoverIQ no-health ERV research comparator using the exact Phase 4 ablation artifact;
- hidden-oracle ERV upper bound, evaluation only.

Existing Phase 2 fixed-retry and reminder-plus-retry workflows are reported separately under their original multi-action semantics. They are not used as a misleading equivalent first-action headline.

## Development objective and validation gates

The primary development objective is maximum simulated net recovery value subject to zero rule violations, bounded action/contact counts, and at least 70% autonomous coverage. Gross revenue alone is not the selection objective.

Before validation, the following gate is frozen:

1. **Deterministic safety:** RecoverIQ has zero policy violations.
2. **Fixed-retry value:** mean paired validation net-value difference versus equivalent first-action Fixed Retry is greater than zero to claim improvement.
3. **Personalization value:** RecoverIQ beats at least one of Best Global Action or the failure-reason lookup on mean paired net value, or reduces mean oracle-ERV regret by at least one minor unit, while retaining zero violations.
4. **Abstention transparency:** autonomous, HUMAN_REVIEW, and STOP rates plus review reasons are present in the report.

Overall policy validation passes only if all four checks pass. Reminder comparison is always reported; underperformance is preserved and is not an implementation bug. No arbitrary percentage lift is required, and validation results cannot alter the policy.

## Required validation evidence

For every strategy, the report includes decisions, recovery, simulated gross/net value, intervention/friction costs, actions, retries, contacts, links, method changes, alternate methods, review, STOP, recovery timing, policy violations, oracle agreement/regret, and selected-action distribution. Paired differences across the ten validation seeds include mean, median, and a normal 95% seed interval.

Diagnostics include hidden failure family only after decision, observable failure reason, amount buckets, abstention, rule blocks and oracle value forgone, primary/no-health downstream comparison, context heterogeneity, and at least one complete structured decision trace. Results remain machine-readable and Markdown only.

## State and attribution invariants

- Each evaluated failure receives at most one recovery attribution.
- STOP and HUMAN_REVIEW cannot execute an autonomous action.
- A blocked candidate cannot be selected.
- Retry/contact caps and opt-out rules cannot be bypassed.
- Duplicate links cannot be created where forbidden.
- All strategies see the same scenario and pre-intervention observable policy profile for a seed.
- No validation, Phase 4 held-out, or final seed is available to tuning commands.

## Results

Policy V1 froze with normalized ERV-margin threshold `0` and config hash `ddf875ea3406f62236b4a9fe91f9e40c0ad129ee60d6482c4524f64a0ed1e8b5`. A zero threshold maximized development simulated net value; support checks still produced 214 reviews and non-positive/fully blocked candidates produced 69 STOP decisions on 27,635 development cases. Development had zero deterministic policy violations and 99.0% autonomous coverage. No policy setting changed after validation.

### Development personalization audit

The hidden development oracle's best-ERV action was distributed across all nine candidates: `RETRY_NOW` 6.69%, `RETRY_LATER_2H` 0.02%, `RETRY_LATER_6H` 0.62%, `RETRY_LATER_12H` 15.23%, `RETRY_LATER_24H` 26.17%, `SEND_NUDGE` 1.44%, `CREATE_PAYMENT_LINK` 25.24%, `REQUEST_PAYMENT_METHOD_UPDATE` 21.36%, and `OFFER_ALTERNATE_METHOD` 3.23%. Frozen Model V1's top-probability distribution was `RETRY_LATER_6H` 1.41%, `RETRY_LATER_12H` 20.91%, `RETRY_LATER_24H` 26.37%, `SEND_NUDGE` 0.03%, `CREATE_PAYMENT_LINK` 24.24%, `REQUEST_PAYMENT_METHOD_UPDATE` 19.63%, and `OFFER_ALTERNATE_METHOD` 7.41%; it selected neither retry-now nor retry-2h as top probability on development.

The best global development action was `OFFER_ALTERNATE_METHOD`, with infeasible cases falling through the frozen global order. Model V1 achieved 68.53% oracle-probability top-1 agreement, 83.19% top-2 coverage, and 88.36% pairwise ranking accuracy. Preference changed across failure reason, payment method, amount, customer history, and other registered observable slices, so the development data contained genuine context/action heterogeneity. That did not by itself prove that ML complexity beat transparent policies; validation was required.

On development, RecoverIQ net value was 2,598,927,300 minor versus 2,655,537,350 for the failure-reason lookup and 2,630,645,150 for the no-health research comparator. This warning was retained before validation: context dependence existed, but Model V1 did not dominate the strongest simple or ablation comparators on development realized value.

### One-time validation

Validation seeds `20270601`-`20270610` produced 27,135 paired decisions and 244,215 candidate rows. All four frozen gates passed:

1. zero deterministic policy violations;
2. mean paired net-value lift over equivalent first-action Fixed Retry of 102,958,840 minor per seed;
3. positive mean paired net-value and lower oracle-regret results versus both Best Global Action and the failure-reason lookup;
4. explicit autonomous, review, STOP, and review-reason reporting.

| Equivalent first-intervention strategy | Recovered | Rate | Simulated net minor | Reviews | STOP | Mean oracle ERV regret minor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed Retry | 6,671 | 24.58% | 1,379,738,050 | 0 | 0 | 45,533.96 |
| Generic Reminder | 1,653 | 6.09% | 336,166,800 | 0 | 11,129 | 83,368.16 |
| Best Global Action | 9,542 | 35.16% | 1,953,624,100 | 0 | 0 | 23,827.20 |
| Failure Reason + Method | 11,400 | 42.01% | 2,368,239,450 | 0 | 0 | 8,611.44 |
| Failure Reason | 11,527 | 42.48% | 2,394,187,650 | 0 | 0 | 7,308.27 |
| Model Probability | 11,649 | 42.93% | 2,409,028,450 | 186 | 0 | 7,323.70 |
| **RecoverIQ ERV Policy V1** | **11,653** | **42.94%** | **2,409,326,450** | **186** | **85** | **7,316.76** |
| No-health ERV research comparator | 11,872 | 43.75% | 2,450,967,750 | 36 | 18 | 5,694.85 |
| Oracle ERV + rational STOP upper bound | 12,604 | 46.45% | 2,622,225,100 | 0 | 675 | 0.00 |

RecoverIQ beat Best Global by 455,702,350 total simulated net minor and 2,111 recoveries, and beat the failure-reason lookup by 15,138,800 net minor and 126 recoveries. Against the probability-only policy, ERV added only 298,000 net minor and four recoveries while making 109 fewer contacts and 24 more retries; this is a small economic-selection effect, not a large headline gain.

The no-health research comparator again won: it recovered 219 more payments, added 41,641,300 simulated net minor, and reduced mean oracle ERV regret by about 1,622 minor per decision. Payment-health features therefore have **not** demonstrated downstream policy value. Model V1 remains the frozen primary by protocol; this is evidence to consider a future independently validated Model V1.1, not permission for a post-hoc switch.

RecoverIQ selected `RETRY_LATER_24H` most often at 36.87%, far below the 80% dominance investigation threshold. It made 18,995 retries and 7,869 customer contacts. All 186 reviews were caused by `LOW_SUPPORT`; 69.35% were oracle-ambiguous at the registered 0.005 normalized margin, while the evaluation-only underlying top model action matched the oracle-best action in 65.59% of review cases. Human-review outcomes were not simulated and received no attributed recovery.

The highest predicted-ERV candidate was blocked 6,238 rule-times: 5,156 quiet-hours blocks, 693 opt-out blocks, 198 unavailable-alternate-method blocks, and 191 duplicate-link blocks. These are evaluation-only false-safety diagnostics and did not cause rules to be loosened.

### Fairness boundary and limitations

The equivalent first-action view is the Phase 5 headline comparison. Under their original multi-action semantics, the existing Fixed Retry workflow recovered 10,357 payments at 38.17% with 2,131,122,950 net minor, while Reminder + Retry recovered 12,885 at 47.48% with 2,623,000,700 net minor. RecoverIQ did **not** beat the existing Reminder + Retry workflow. That workflow takes an average 2.55 actions per failure and is not an equivalent first-intervention comparator, but its stronger outcome remains visible.

All evidence is synthetic and simulator-specific. Policy V1 evaluates only the first intervention, uses deterministic point probabilities rather than epistemic uncertainty, uses synthetic cost/operational assumptions, and does not simulate the outcome of human review. It contains no production execution, Razorpay integration, LLM explanation, sequential replanning, or overall-final evaluation. The compact source of truth is `artifacts/policy/recoveriq-policy-v1/validation-evaluation-v1.json`.

## Phase 6 addendum — Sequential Policy V2

Policy V1 remains immutable historical first-intervention evidence. Phase 6 adds a separate `recoveriq_sequential_policy` package and artifact namespace; it does not rewrite V1. Sequential Policy V2 consumes frozen no-health Recovery Model V2, computes current-action incremental ERV, applies explicit action-stage/calibration support, and replans after an observed failure for at most three interventions in a 48-hour episode. It intentionally uses bounded greedy receding-horizon selection instead of reinforcement learning.

Development seeds `20271201`-`20271210` froze the simple failure-reason/stage mapping, global stage rankings, BALANCED costs, two-retry/two-contact caps, support thresholds 500/100, and a zero normalized margin. The resulting config hash is `ce7712b1ee4e800d54a875eb65a7bc826680e59faa465b54cbc1db7472010b25`. Validation seeds `20280101`-`20280110` then ran exactly once.

Sequential validation passed every preregistered claim with zero violations. RecoverIQ recovered 75.97% versus 53.09% for Reminder + Retry and 64.60% for the simple sequential rule, and did so with fewer retries/contacts than both. Its paired net-value interval versus Reminder + Retry excluded zero. The probability-only policy nevertheless recovered 76.18% and produced slightly higher net value; ERV Policy V2's measurable advantage there was 491 fewer contacts overall, not superior recovery. Full episode metrics, paired intervals, sequences, transition matrices, personalization slices, oracle regret, and traces are documented in `docs/SEQUENTIAL_RECOVERY.md` and the sealed validation artifact.
