# Operational Degradation Detector V2

## Status and objective

Detector v2 is a separate Phase 3.5 implementation. Detector v1 and its frozen artifacts remain the historical research/statistical baseline and are not rewritten. V1 is **not safe as autonomous payment-action authority**.

V2 separates advisory evidence from evidence that might eventually qualify as a deterministic policy safety input:

- `WATCH` is dashboard/investigation context and a future continuous ML feature. It is never authoritative and cannot independently authorize, suppress, or block a recovery action.
- `CONFIRMED` requires substantially stronger local support. The detector still performs no recovery action. It may become eligible for future hard-policy use only if the pre-registered held-out safety gate passes.

Evidence level and observable severity are independent dimensions.

## Pre-registered data protocol

- Architecture development and selection: existing development seeds `20260901`–`20260910` only.
- Detector-v1 validation seeds `20261001`–`20261010` are consumed historical data and are forbidden for v2 tuning.
- V2 one-time validation: new seeds `20261201`–`20261210`.
- Reserved final evaluation: `20261101`–`20261120`, untouched and inaccessible through normal v2 commands.

The original v1 eligibility rule remains unchanged for comparison: at least 5 matching method+issuer events observed during the hidden incident and at least 50 matching-scope events in the preceding 30 days.

The pre-registered **operationally high-evidence** slice requires at least 10 matching method+issuer events observed within the first 24 hours after hidden onset (bounded by incident end), plus at least 100 matching-scope observations in the preceding 30 days. It uses opportunity-to-detect quantities only; hidden severity, realized rate drop, detector score, and detection outcome are forbidden.

## Pre-registered hard-policy safety gate

`CONFIRMED` is eligible for consideration as a future hard-policy input only if the one-time v2 validation result simultaneously has:

- episode precision at least 70%;
- no more than 0.005 false confirmed episodes per issuer-scope-day;
- at least 5 confirmed issuer episodes, preventing a vacuous pass with no alerts.

Failure marks `CONFIRMED` **ADVISORY ONLY**. Validation performance is not a reason to retune.

## Sequential method

For each scope, the detector maintains a predictable Bernoulli generalized likelihood-ratio process. Before each event, an empirical-Bayes baseline probability `p0` is estimated only from preceding observations. Small method+issuer histories shrink toward method and then global history. Three alternative probabilities represent small, moderate, and large operational drops from `p0`.

For outcome `x ∈ {0,1}` and alternative `p1`, the event increment is:

`x log(p1/p0) + (1-x) log((1-p1)/(1-p0))`.

Each alternative uses a one-sided reset-at-zero likelihood CUSUM. Success therefore reduces degradation evidence when it is more likely under baseline health. The maximum alternative evidence is reported, while all three components remain structured output. Once WATCH begins, `p0`, alternatives, and historical failure distribution freeze for that episode so an outage cannot teach itself into the baseline.

## Baseline and failure-distribution evidence

While healthy, the baseline uses the trailing 14 days ending immediately before the current event; there is no v1-style 24-hour stale gap. Direct scope history is preferred, with method/global shrinkage or fallback where necessary. Parent evidence may corroborate but cannot create local issuer evidence.

Failure-reason evidence compares failures since WATCH with the frozen historical reason distribution. It uses Jensen–Shannon divergence with additive smoothing and minimum failure/support gates. Output includes current/baseline share, absolute increase, relative lift where defined, and support count. Two or three errors cannot confirm an incident.

## Multiple testing and lifecycle

V2 uses stricter likelihood boundaries for CONFIRMED, a three-alternative multiplicity allowance, one-sided evidence reset, explicit minimum volume, episode evidence reset, sustained recovery, and a per-scope confirmation cooldown. This is more appropriate for continuously arriving events than applying an offline false-discovery procedure to dependent repeated tests.

Lifecycle:

`HEALTHY → WATCH → CONFIRMED → RECOVERING → RESOLVED`

`WATCH → HEALTHY` is allowed when evidence dissipates. Recovery uses accumulated positive-health log likelihood rather than elapsed time alone. Continued deterioration updates the existing episode instead of creating duplicates.

## Pre-registered selection objective

A modest explicit candidate set is evaluated on development only.

1. Prefer candidates with at least 5 confirmed development episodes and no more than 0.005 false confirmed episodes per issuer-scope-day.
2. Maximize confirmed precision, then high-evidence confirmed recall, then minimize WATCH-to-CONFIRMED delay.
3. Break remaining ties using WATCH eligible recall and WATCH delay.
4. If no candidate satisfies the alert-rate constraint, minimize false confirmed rate before applying the same precision/recall ordering.

The chosen configuration is frozen as `degradation-detector-v2.json` before the new validation group is generated.

## Results

Development selected candidate 4 of the six pre-registered candidates and froze configuration hash
`50f0ca055d561b447d1b2aa3769cf775917b9efbceb44c6934a8971c1585af8c`. Its effective rules are:

- WATCH: a predictable baseline must exist, at least three local events must have been observed since reset, and the maximum one-sided likelihood CUSUM must reach `2.5`.
- CONFIRMED A: at least 10 events since WATCH and extreme local CUSUM `>= 10.0`.
- CONFIRMED B: at least 10 events since WATCH, local CUSUM `>= 7.0`, supported failure samples (at least 10 historical and 5 current failures), and Jensen–Shannon divergence `>= 0.18`.
- CONFIRMED C: issuer scope only, at least 10 events since WATCH, local CUSUM `>= 6.5`, and method or global scope at WATCH/CONFIRMED.
- A seven-day per-scope cooldown prevents repeated confirmations from consuming a fresh alert budget immediately.

The development audit contained 180 incidents: 66 original-eligible and 23 high-evidence. The one-time validation group contained 180 incidents: 78 original-eligible and 28 high-evidence.

| Group / tier | Episodes | All recall | Eligible recall | High-evidence recall | Precision | False / scope-day | Median raw delay | P90 raw delay |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Development WATCH | 1,750 | 12.22% | 24.24% | 30.43% | 1.26% | 0.089412 | 620.87 min | 1,415.35 min |
| Development CONFIRMED | 102 | 3.33% | 6.06% | 17.39% | 5.88% | 0.004967 | 999.94 min | 2,269.39 min |
| Validation WATCH | 1,888 | 17.22% | 28.21% | 39.29% | 1.64% | 0.096058 | 274.24 min | 1,306.04 min |
| Validation CONFIRMED | 108 | 2.22% | 5.13% | 7.14% | 3.70% | 0.005380 | 1,064.80 min | 1,508.58 min |

The validation hard-policy gate is **FAIL**. Precision was `3.70% < 70%`, and false confirmations were `0.005380 > 0.005` per issuer-scope-day; the non-vacuity count passed with 108 episodes. CONFIRMED is therefore **ADVISORY ONLY** and `PaymentHealthContextV2.confirmed_hard_policy_gate_passed` remains false. No threshold was changed after validation.

### Validation latency

| Tier / reference | Mean | Median | P90 |
|---|---:|---:|---:|
| WATCH from hidden onset | 550.36 min | 274.24 min | 1,306.04 min |
| WATCH after first relevant event | 451.34 min | 239.91 min | 1,165.75 min |
| WATCH after minimum evidence | 221.96 min | 0.00 min | 989.05 min |
| CONFIRMED from hidden onset | 932.24 min | 1,064.80 min | 1,508.58 min |
| CONFIRMED after first relevant event | 878.04 min | 1,001.94 min | 1,508.28 min |
| CONFIRMED relative to minimum evidence | -244.48 min | 100.96 min | 222.04 min |
| WATCH to CONFIRMED | 3,605.61 min | 1,958.37 min | 9,220.55 min |
| Resolution relative to hidden end | 7,997.51 min | 7,727.69 min | 13,194.21 min |

The minimum-evidence statistic is a signed lead/lag against the incident-local Nth relevant event. A negative mean for CONFIRMED means one matched detector episode had accumulated qualifying local evidence before the hidden incident reached its tenth in-incident event; it is not clamped into a flattering zero.

### Validation slices

| Slice | Incidents | WATCH recall | CONFIRMED recall |
|---|---:|---:|---:|
| Severity: MILD | 91 | 13.19% | 0.00% |
| Severity: MODERATE | 57 | 14.04% | 3.51% |
| Severity: SEVERE | 26 | 26.92% | 3.85% |
| Severity: CRITICAL | 6 | 66.67% | 16.67% |
| Traffic: 0–2 events | 67 | 1.49% | 0.00% |
| Traffic: 3–4 events | 30 | 16.67% | 0.00% |
| Traffic: 5–9 events | 44 | 20.45% | 0.00% |
| Traffic: 10+ events | 39 | 41.03% | 10.26% |

### Comparators on the same new validation group

| Detector / tier | Episodes | Precision | All recall | Eligible recall | False / scope-day | Median delay |
|---|---:|---:|---:|---:|---:|---:|
| Static threshold | 1,891 | 1.32% | 13.89% | 24.36% | 0.096524 | 578.92 min |
| Relative drop | 1,695 | 1.18% | 11.11% | 21.79% | 0.086644 | 470.00 min |
| Detector v1 | 337 | 2.37% | 4.44% | 10.26% | 0.017018 | 716.71 min |
| Detector v2 WATCH | 1,888 | 1.64% | 17.22% | 28.21% | 0.096058 | 274.24 min |
| Detector v2 CONFIRMED | 108 | 3.70% | 2.22% | 5.13% | 0.005380 | 1,064.80 min |

V2 WATCH improves warning recall and median delay relative to the comparators but has a very high advisory alert volume. V2 CONFIRMED reduces false-alert rate and improves episode precision, but sacrifices recall and remains far below the safety target.

### Safety exposure, explanation quality, and performance

The 104 false CONFIRMED issuer episodes contained 824 observable failed payments during their confirmed-to-resolved scope intervals. This is potential exposure if a future policy incorrectly treated every false confirmation as a hard retry gate; no recovery action was simulated. Of the 104 false confirmations, 102 used parent corroboration and 2 used failure-distribution corroboration. This concentration is a genuine limitation of the frozen design, not grounds for post-validation retuning.

Failure-shift explanation was available for all four matched CONFIRMED incidents; top-1 agreement with the simulator's expected shifted reason was 75%, with support mean 9.25, median 9.5, and P90 13 failures. These denominators are too small for a broad root-cause claim.

Validation replay sustained 5,524.34 observable events/second with mean detector update latency of 0.181 ms. The simulator's approximately 20,000-event seed replay remains practical without distributed infrastructure.

### Known limitations

- Both tiers have low episode precision, and CONFIRMED failed both substantive safety thresholds.
- CONFIRMED recall is only 2.22% overall and 7.14% in the high-evidence slice; sparse and mild incidents are especially difficult.
- Parent corroboration dominates confirmation and false-confirmation paths, so broad WATCH evidence is not selective enough to serve as hard issuer-level authority.
- Detection and resolution delays remain long at low-traffic scopes; the frozen sequential design does not solve observability scarcity.
- Simulator validation measures controlled synthetic behavior and does not establish production calibration.

## Phase 4 boundary

Future recovery prediction may consume numeric health evidence and WATCH state as non-authoritative features. WATCH must never be encoded as an outage boolean with policy authority. Because the held-out gate failed, this frozen CONFIRMED signal is also advisory-only and cannot be a hard safety constraint. No recovery model or policy is implemented in Phase 3.5.
