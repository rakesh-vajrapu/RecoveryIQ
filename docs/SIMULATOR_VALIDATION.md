# Simulator Robustness and Benchmark Validation

## Scope and checkpoint

Phase 2.5 treats commit `cc8fe0b09877e83758e08eef8c6e1a2d940aa439` and simulator `0.2.0` as an immutable baseline. The hardened environment is version `0.3.0`; it produces different experiment IDs and never overwrites the ignored `0.2.0` artifact. A tracked summary fixture preserves the baseline experiment ID, configuration hash, scenario digest, and headline counts.

This phase is an adversarial simulator audit. It does not contain degradation detection, ML, a RecoverIQ policy, Gemini runtime work, Razorpay integration, or frontend work.

## Pre-registered seed protocol

- Development: `20260901`–`20260910`
- Validation: `20261001`–`20261010`
- Reserved final evaluation: `20261101`–`20261120`

Development and validation were executed without exclusions. Final seeds were not run. The CLI refuses `--group final` unless the caller also supplies `--acknowledge-final`.

## Multi-seed findings

Each run contains 20,000 attempts. Confidence intervals use `mean ± 1.96 × sample standard error`; they describe seed-to-seed simulation variability, not real-world uncertainty.

| Group | Policy | Mean recovery rate | 95% CI | Mean recovered count | 95% CI | Mean gross recovered (minor) | Mean net value (minor) |
|---|---|---:|---:|---:|---:|---:|---:|
| Development | Fixed Retry | 38.92% | 37.90–39.94% | 1,084.4 | 1,023.2–1,145.6 | 270,912,710 | 268,999,230 |
| Development | Reminder + Retry | 48.43% | 47.37–49.50% | 1,349.6 | 1,274.7–1,424.5 | 334,814,600 | 331,312,565 |
| Validation | Fixed Retry | 38.89% | 38.13–39.64% | 1,036.2 | 966.7–1,105.7 | 239,277,770 | 237,445,620 |
| Validation | Reminder + Retry | 48.42% | 47.65–49.18% | 1,290.0 | 1,206.1–1,373.9 | 296,509,460 | 293,153,860 |

The reminder baseline remains stronger in every development and validation seed. That is a property of these synthetic assumptions, not evidence of real recovery lift.

## Incident design and coverage

The old environment drew every incident from one 12–36-hour, 38–72% degradation range. Version `0.3.0` uses four classes and independent short/medium/long duration families. Severity class changes both the health reduction and the affected fraction of traffic. Error-shift strength, start time, method, issuer, dominant cause, and traffic exposure are also sampled. The ranges are synthetic and are not claims about Razorpay production incidents.

Across the 20 development and validation seeds (360 incidents):

| Severity | Count | Share |
|---|---:|---:|
| Mild | 157 | 43.61% |
| Moderate | 121 | 33.61% |
| Severe | 64 | 17.78% |
| Critical | 18 | 5.00% |

Incident durations ranged from 0.51 to 63.96 hours, with a 7.70-hour median and 12.00-hour mean. Attempt coverage averaged 0.280%; incident failures represented 0.748% of all failures. Mean observed success was 64.13% inside incidents and 86.45% outside. Low exposure is intentional: some incidents have little observable volume and should be difficult to detect. Incidents are generated independently of the 6/12-hour retry schedule.

## Nudge-effect audit

The following aggregation uses all 20 development and validation environments. “Direct” means `SEND_NUDGE` was the first attributed successful action. “Lift” is the paired difference between final Reminder + Retry and Fixed Retry recovery rates for that hidden cause.

| Hidden cause | Exposed | Direct nudge rate | Final recovery lift |
|---|---:|---:|---:|
| Authentication friction | 7,983 | 20.49% | 14.52% |
| Customer confirmation | 6,421 | 33.72% | 32.94% |
| Inactive mandate | 3,139 | 5.35% | 5.29% |
| Invalid instrument | 8,435 | 3.27% | 3.25% |
| Issuer degradation | 4,047 | 0.49% | 0.07% |
| Liquidity shortfall | 12,805 | 8.43% | 9.15% |
| Network instability | 8,386 | 0.57% | 0.16% |
| Unknown temporary | 3,224 | 10.58% | 8.93% |

Issuer and network effects are near zero and a prior contact does not improve their later retry probability. Customer confirmation and authentication effects increase with hidden responsiveness. Expired/inactive instruments receive only limited direct nudge probability; method-update or alternate-method actions are materially more useful in the hidden response model.

## Failure-reason triviality

Every suite report contains `P(hidden cause | observable failure reason)`, normalized entropy, normalized mutual information, and action success by observable reason. Some diagnostic provider responses—such as instrument expired or mandate inactive—intentionally reveal a narrow mechanical condition. They still do not reveal customer responsiveness, incident clearance, action randomness, or future outcome. Across the complete distribution, reasons remain overlapping; the single 20,000-attempt quality run had normalized mutual information `0.635`, well below a deterministic cause lookup.

The simulator sanity gate uses overall normalized mutual information rather than rejecting justified diagnostic reasons solely because their maximum posterior is high.

## Cost and friction sensitivity

Costs are synthetic accounting assumptions. The low, balanced, and high regimes vary retry, message, link, update, alternate-method, human-review, retry-friction, contact-friction, nonlinear growth, and a maximum contact-friction cap.

The three-seed, 5,000-attempt sweep confirmed that costs do not affect raw outcomes for the cost-insensitive baselines:

| Regime | Fixed gross | Fixed net | Reminder gross | Reminder net |
|---|---:|---:|---:|---:|
| Low friction | 71,205,833 | 71,140,403 | 89,427,267 | 89,328,605 |
| Balanced | 71,205,833 | 70,732,333 | 89,427,267 | 88,564,300 |
| High friction | 71,205,833 | 69,311,833 | 89,427,267 | 86,044,300 |

Repeated contact friction grows geometrically and is bounded by the regime cap. Arithmetic and counterfactual tests prove that gross recovery and recovery attribution remain identical while net value falls as costs increase.

## Sensitivity sweep

The bounded sweep varied incident severity profile, incident count, nudge strength, and cost regime across three development seeds. Reminder + Retry remained first for recovery rate, gross recovery, and net value in all cases. This means no ranking change was found in this sweep; it does not prove the ranking is universal.

Reminder recovery ranged from 43.86% under weak nudge response to 52.35% under strong response. Fixed Retry was invariant to nudge strength. Cost changes affected net value only. Incident severity/frequency changed population composition and both baselines without creating a designed crossover.

## Policy-independent counterfactual method

The hidden world is generated once before policy evaluation. Both policies share the same customer latent state, subscriptions, payment schedule, initial outcomes, and incidents. Recovery draws use SHA-256-derived uniforms keyed by simulator seed, payment ID, semantic action type, execution timestamp, semantic retry ordinal, and event type. Policy name, logging, action ID, evaluation order, cost, and unused post-`STOP` candidates are excluded.

Regression tests compare semantically identical retries across policies and prove that an unused candidate does not change any payment outcome.

## Observation, artifact, and temporal leakage audit

`PAYMENT_OBSERVATION_FIELD_ALLOWLIST` is an exact machine-checkable schema. Tests fail if a field is added or removed without an explicit allowlist review. It excludes latent customer state, true cause, incident membership/end time, initial success probability, future events, and counterfactual responses.

New artifacts use separate directories:

- `observable/`: events, payments, subscriptions, and failure observations;
- `ground_truth/`: incidents and outcome truth.

Future supervised datasets must deliberately join only approved labels; no convenient all-in-one hidden dataframe is emitted. Temporal tests reconstruct each observation from preceding delivered events and verify its customer/subscription aggregates exactly. Delayed events enter history only when observed.

## Action semantics matrix

This is hidden environment design documentation. It must not be exported as a policy feature or treated as causal evidence from real payments. `WAIT` has no direct recovery; its value is enabling later timing. `STOP` is terminal.

| Failure family | WAIT | RETRY_NOW | RETRY_LATER | SEND_NUDGE | PAYMENT_LINK | METHOD_UPDATE | ALTERNATE_METHOD | HUMAN | STOP |
|---|---|---|---|---|---|---|---|---|---|
| Insufficient funds | timing enabler | mostly friction | helpful later | sometimes helpful | sometimes helpful | mostly irrelevant | mostly irrelevant | sometimes helpful | terminal |
| Issuer unavailable | timing enabler | harmful during incident | helpful after clearance | friction-only | mostly irrelevant during incident | irrelevant | helpful via another rail | mostly irrelevant during incident | terminal |
| Authentication failure | timing enabler | sometimes helpful | sometimes helpful | helpful for responsive customers | helpful | mostly irrelevant | sometimes helpful | sometimes helpful | terminal |
| Instrument expired | no direct effect | harmful/friction-only | harmful/friction-only | limited | helpful | helpful | helpful | sometimes helpful | terminal |
| Mandate inactive | no direct effect | harmful/friction-only | harmful/friction-only | limited | helpful | helpful | helpful | sometimes helpful | terminal |
| Temporary network error | timing enabler | sometimes helpful | helpful after transience | friction-only | mostly irrelevant during incident | irrelevant | helpful via another rail | mostly irrelevant during incident | terminal |
| Customer action required | timing enabler | mostly irrelevant | mostly irrelevant | helpful when responsive | helpful | mostly irrelevant | sometimes helpful | helpful | terminal |
| Unknown transient error | timing enabler | sometimes helpful | sometimes helpful | sometimes helpful | sometimes helpful | mostly irrelevant | sometimes helpful | sometimes helpful | terminal |

## Remaining limitations

- Incident attempt coverage is intentionally low and some incidents have no useful sample; later detector evaluation must report per-severity recall and minimum-volume exclusions transparently.
- The response surface is hand-designed and not a causal model learned from real payments.
- Latent customer traits are mostly static within an experiment.
- Multi-seed confidence intervals quantify simulator-seed variation only.
- Baseline ranking did not change in the bounded sensitivity sweep, so future work should not assume the environment spans every plausible merchant regime.
- Diagnostic failure reasons still contain strong justified signal; their raw values must not be mistaken for hidden customer response or future outcome.
