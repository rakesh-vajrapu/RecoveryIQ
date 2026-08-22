# RecoverIQ Bounded Sequential Recovery

## Phase 6 preregistration status

This document preregisters Phase 6 before generating any sequential trajectory. Phase 5 commit `a869fe9a73e25d37d51a73433b7fac4a6c7d6d20`, Simulator `0.3.0`, both detectors, Recovery Model V1, Recovery Policy V1, and all prior reports remain immutable historical evidence.

One disclosure applies to the requested seed range: `20270802` was generated before this Phase 6 request as an unregistered Phase 5 one-action validation-harness smoke. That smoke printed only scenario/decision counts and harness invariants. No sequential environment existed, and no trajectory, sequential target, Model V2 feature, counterfactual ranking, policy selection, or Phase 6 metric was generated or inspected. It therefore supplies no Phase 6 tuning information; the requested seed remains in the registered training group.

Phase 6 does not call Gemini, integrate Razorpay, change the frontend, run the overall-final benchmark, or modify production side effects.

## Registered seed groups

- Sequential logged training: `20270801`-`20270820`.
- Model V2 development: `20270901`-`20270910`.
- Model V2 calibration: `20271001`-`20271010`.
- Model V2 held-out test, exactly once after model/calibration freeze: `20271101`-`20271110`.
- Sequential policy development: `20271201`-`20271210`.
- Sequential policy validation, exactly once after policy freeze: `20280101`-`20280110`.
- Optional stress: `20280201`-`20280205`; not required for the primary checkpoint.
- Overall-final Buildathon: `20261101`-`20261120`, untouched and forbidden to all Phase 6 commands.

Model-test and policy-validation commands must write durable attempt markers before generating their registered worlds and refuse overwrite. A genuine implementation defect requires an explicit invalid record before any transparent rerun; poor performance is never a software defect.

## Product and authority boundary

RecoverIQ is now positioned as **safe adaptive multi-step revenue recovery**. Detector V2 remains useful for operational observability, dashboards, incident investigation, and later explanation, but it is advisory only. Phase 4 and Phase 5 found no recovery-prediction or downstream-policy benefit from payment-health features. Primary Model V2 excludes every Detector V2/payment-health field by preregistration.

The sequential controller is a simulator-only bounded receding-horizon policy. It is not a production executor and cannot move money or contact a real customer. Statistical models provide action-level recovery evidence; deterministic rules retain authorization authority.

## Episode semantics

An episode begins at an eligible recurring payment's initial failure and has a fixed 48-hour horizon. It terminates immediately upon the first of:

- attributable recovery;
- horizon exhaustion;
- STOP;
- HUMAN_REVIEW, which ends autonomous execution;
- three executed autonomous interventions.

Autonomy is limited to three interventions. Retry and customer-contact caps are both two. A recovered payment ends the episode and is attributed exactly once to its recovering action and decision index.

## Candidate and observation timing

The ordered modeled candidates remain:

1. `RETRY_NOW`;
2. `RETRY_LATER_2H`;
3. `RETRY_LATER_6H`;
4. `RETRY_LATER_12H`;
5. `RETRY_LATER_24H`;
6. `SEND_NUDGE`;
7. `CREATE_PAYMENT_LINK`;
8. `REQUEST_PAYMENT_METHOD_UPDATE`;
9. `OFFER_ALTERNATE_METHOD`.

Retry outcome is observed at execution, followed by a deterministic two-hour cooling/observation interval before another decision. Contact, link, method-update, and alternate-method outcomes are observed at execution, followed by a deterministic six-hour opportunity interval before replanning. These intervals summarize the existing simulator's immediate keyed action outcome while preventing unrealistic instantaneous repeated decisions. A delayed retry must execute inside the 48-hour horizon; the following observation interval is truncated at the horizon.

An immediate contact candidate during quiet hours is scheduled at the next 07:00 UTC boundary when that execution remains inside the episode horizon. It is never credited before execution and never extends the episode beyond 48 hours. Opt-out, contact cap, retry cap, existing-link, alternate-workflow, repeated method-update/alternate-action, and horizon state remove infeasible actions before behaviour-policy selection or autonomous scoring.

## Sequential exploration logger

For each unresolved decision the logger constructs observable state, deterministically enumerates feasible candidates, and selects exactly one candidate uniformly. The exact propensity is `1 / feasible_candidate_count`. Selection uses semantic keyed randomness over seed, episode key, and decision index; it never reads hidden cause, hidden outcome probability, oracle action, future incident state, or a counterfactual outcome.

The selected action is executed against Simulator `0.3.0`'s frozen hidden response surface. Only that action's keyed outcome is observed. Failure updates observable episode state, advances the clock by the registered observation interval, and permits another decision if termination rules allow. Approximately balanced feasible exploration and a maximum of nine candidates keep propensities bounded below by `1/9`.

Each row contains an opaque grouping-only episode key, decision index/time, observable payment/customer/subscription state, elapsed episode time, prior action counters, last action/result, action candidate/timing, exact propensity, the current action outcome, and termination state. Raw IDs, seed, hidden traits/cause/incident/state, hidden effectiveness, oracle probabilities, and unselected outcomes are forbidden from the predictive frame.

## Action-level target and attribution

The frozen target is `action_recovered_before_next_decision`. It is positive only when the currently selected action recovers the payment at its execution before any subsequent autonomous decision. A later action can never relabel an earlier failed action. Each action row is finalized before another intervention is selected. Recovery records action ID/type, decision index, timestamp, and amount once; no episode can contain two positive action rows.

## Sequential policy V2 preregistration

Policy construction begins only after Model V2's held-out artifact is sealed. At each unresolved decision it generates feasible candidates, scores them with frozen calibrated primary Model V2, calculates exact incremental ERV, applies deterministic rules/support checks, and selects maximum positive ERV or ends in HUMAN_REVIEW/STOP. It uses greedy bounded replanning, not reinforcement learning, RNNs, LSTMs, Transformers, or an unbounded loop.

`Incremental ERV = round_half_up(P(action recovery) × payment amount minor) − incremental intervention cost − incremental friction cost`.

BALANCED synthetic costs are primary. Costs are charged once per executed intervention; payment value is credited once on recovery. LOW_FRICTION and HIGH_FRICTION remain sensitivity assumptions, not provider prices.

Frozen rule IDs include `MAX_INTERVENTIONS`, `MAX_RETRIES`, `MAX_CONTACTS`, `MIN_RETRY_INTERVAL`, `CUSTOMER_OPT_OUT`, `QUIET_HOURS_SCHEDULE`, `DUPLICATE_PAYMENT_LINK`, `RECOVERY_HORIZON`, `ACTION_FEASIBILITY`, `MODEL_SCHEMA_VALID`, `MODEL_SUPPORT`, `NON_POSITIVE_INCREMENTAL_ERV`, and `ATTRIBUTION_ONCE`. Detector state is absent.

Support requires at least 500 training examples for the action/decision-index cell and 100 examples in the selected calibration bin. Unsupported highest-ERV candidates end in HUMAN_REVIEW rather than silently falling through. Development studies normalized incremental-ERV margins `0`, `0.001`, `0.0025`, `0.005`, and `0.01`, selecting maximum mean net value subject to zero violations and at least 70% autonomous decision coverage; ties within one minor unit choose greater coverage, then the smaller threshold.

STOP occurs on horizon exhaustion, three interventions, exhausted retry/contact budgets with no other action, no feasible action, or no positive incremental ERV. HUMAN_REVIEW ends autonomous execution for invalid schema/input, unsupported action-stage/calibration region, critical missing observable data, or irreconcilable deterministic policy conflict.

## Full-horizon comparators

All primary policy-validation strategies receive the same hidden scenario, failed-payment cohort, observable starting state, 48-hour horizon, operational profile, keyed outcome surface, and attribution rules:

- existing Fixed Retry workflow adapted to the common episode evaluator;
- existing Reminder + Retry workflow adapted to the common episode evaluator;
- development-frozen observable failure-reason + decision-index + previous-result rule, minimum cell support 300, with stage-global fallback;
- development-frozen best stage-global sequence/action order, minimum action-stage support 500;
- sequential maximum calibrated-probability policy;
- RecoverIQ Sequential ERV Policy V2;
- evaluation-only bounded oracle using a finite maximum-three-action search where practical, otherwise a documented greedy hidden-oracle comparator.

The simple rule and global mappings use policy-development seeds only and are frozen before validation.

## Preregistered sequential validation claims

1. **Safety:** RecoverIQ must produce zero deterministic policy violations.
2. **Recovery:** positive paired mean recovery-rate and net-value differences versus Reminder + Retry are required to claim superior recovery.
3. **Strong recovery:** the paired 95% interval for net-value difference versus Reminder + Retry must exclude zero to claim statistically supported superiority.
4. **ML personalization:** RecoverIQ must beat the Simple Sequential Observable Rule on paired mean recovery or net value, or reduce bounded-oracle regret, without worsening safety.
5. **Friction efficiency:** similar value with fewer retries/contacts may be claimed only from explicitly reported paired counts and efficiency ratios.

No arbitrary percentage lift is required. Validation cannot change Model V2, candidates, costs, support, margins, stopping rules, limits, or baseline mappings.

## Required evidence and limitations

Reports include episode recovery/economics/action counts, paired seed intervals, friction-efficiency ratios, decision-index model quality, action sequences, transition matrices, personalization slices, bounded-oracle regret, a successful adaptive trace, and a three-intervention bounded failure trace. All evidence is synthetic. Human-review outcomes remain unknown, the hidden response surface is hand-designed, greedy replanning is not globally optimal, and no production side effect is authorized.

## Frozen policy and one-time validation results

Policy development selected the zero normalized-ERV margin. It maximized development simulated net value while retaining 99.93% autonomous decision coverage, 34 reviews, and zero violations. The policy froze as version `2.0.0` with config hash `ce7712b1ee4e800d54a875eb65a7bc826680e59faa465b54cbc1db7472010b25`, bound to Model V2 hash `60190d4c7c72dd2a482310d342131329673879137ce15be8e4451cb13dd2d898`, isotonic calibrator hash `1c5b13a613bf04f3c9015fbe43b27c7ac138c2346310dd346b6c32000c21f85e`, and the development baseline artifact hash. No policy field changed after validation.

The one-time validation ran 27,406 identical starting episodes per strategy. Every per-seed strategy cohort hash matched. Primary results were:

| Strategy | Recovered | Rate | Simulated gross minor | Simulated net minor | Retries | Contacts | Mean actions | Reviews | STOP/terminal | Violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed Retry | 11,440 | 41.74% | 2,572,104,700 | 2,553,198,950 | 48,103 | 0 | 1.755 | 0 | 15,966 | 0 |
| Reminder + Retry | 14,549 | 53.09% | 3,307,089,200 | 3,278,888,000 | 38,896 | 26,037 | 2.369 | 0 | 12,857 | 0 |
| Simple observable rule | 17,704 | 64.60% | 4,042,270,400 | 4,010,663,110 | 30,819 | 24,493 | 2.018 | 0 | 9,702 | 0 |
| Best global sequential | 18,774 | 68.50% | 4,270,825,600 | 4,239,971,500 | 37,154 | 18,851 | 2.044 | 0 | 8,632 | 0 |
| Probability policy | 20,878 | 76.18% | 4,754,648,200 | 4,726,961,640 | 28,610 | 20,010 | 1.774 | 0 | 6,528 | 0 |
| **RecoverIQ Sequential ERV V2** | **20,821** | **75.97%** | **4,747,032,700** | **4,719,632,070** | **28,829** | **19,519** | **1.764** | **35** | **6,550** | **0** |
| Greedy hidden oracle | 21,405 | 78.10% | 4,882,232,200 | 4,855,411,250 | 25,543 | 20,588 | 1.683 | 0 | 6,001 | 0 |

Per-seed paired RecoverIQ differences were:

| Comparator | Mean recovery-rate difference | Recovery 95% CI | Mean net minor difference | Net 95% CI | Mean retry difference | Mean contact difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed Retry | +0.34251 | [0.33253, 0.35250] | +216,643,312 | [180,330,276, 252,956,348] | -1,927.4 | +1,951.9 |
| Reminder + Retry | +0.22934 | [0.21771, 0.24096] | +144,074,407 | [120,300,796, 167,848,018] | -1,006.7 | -651.8 |
| Simple observable rule | +0.11370 | [0.10436, 0.12304] | +70,896,896 | [57,381,447, 84,412,345] | -199.0 | -497.4 |
| Best global sequential | +0.07476 | [0.06883, 0.08069] | +47,966,057 | [40,118,863, 55,813,251] | -832.5 | +66.8 |
| Probability policy | -0.00210 | [-0.00289, -0.00131] | -732,957 | [-1,429,259, -36,655] | +21.9 | -49.1 |

RecoverIQ's net value per intervention was 97,617.94 minor versus 50,496.48 for Reminder + Retry; contacts per recovered payment were 0.937 versus 1.790. It used fewer retries and contacts than Reminder + Retry while recovering materially more. Against the probability policy, it used 491 fewer contacts overall but recovered 57 fewer episodes and had 7,329,570 less total net value. ERV/support logic therefore did not improve validation recovery or net value over probability-only selection; this negative result is preserved.

There were 13,614 multi-action RecoverIQ episodes. Common adaptive paths included `RETRY_LATER_24H -> RETRY_LATER_12H`, `REQUEST_PAYMENT_METHOD_UPDATE -> OFFER_ALTERNATE_METHOD`, `RETRY_LATER_24H -> CREATE_PAYMENT_LINK`, and `RETRY_LATER_24H -> RETRY_LATER_6H`. The largest observed transition was `RETRY_LATER_24H -> CREATE_PAYMENT_LINK` at decision 2 (2,395 episodes). Observable failure-reason and payment-method slices used multiple sequences, supporting an adaptation claim without implying that ERV beat probability-only selection.

The greedy hidden oracle exceeded RecoverIQ by a paired mean 0.02149 recovery rate and 13,577,918 net minor per seed. Successful and bounded-failure traces are sealed at `artifacts/policy/recoveriq-sequential-v2/successful-adaptive-trace-v2.json` and `bounded-failure-trace-v2.json`; the latter records exactly three failed autonomous actions and no fourth action.

All registered claims passed: safety, recovery over Reminder + Retry, strong recovery with a positive net-value interval, ML personalization over the simple rule, and friction efficiency. These claims apply only to the frozen synthetic simulator protocol. The compact result source is `artifacts/policy/recoveriq-sequential-v2/validation-evaluation-v2.json`.
