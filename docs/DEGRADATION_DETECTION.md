# Statistical Payment Degradation Detection

## Objective and boundary

Phase 3 detects deterioration in observable payment success rates. The online detector receives only an immutable payment-result event containing event ID, observation timestamp, merchant ID, payment method, optional issuer, outcome, and optional failure reason/source. It never imports or accepts incident membership, hidden severity, incident end time, hidden success probability, true cause, future events, or future outcomes.

`recoveriq_detector.detector` is a simulator-independent package boundary intended for later invocation by an API worker. `recoveriq_detector.replay`, `audit`, and `evaluation` are offline adapters: replay converts public simulator events, then evaluation joins completed predictions to hidden truth. The detector implementation itself is not coupled to simulator ground-truth classes.

## Development observability audit and pre-registered eligibility

The eligibility rule was selected from an observability audit of development seeds `20260901`–`20260910`, before detector threshold selection:

- at least **5 matching payment-method + issuer events observed between hidden incident onset and end**;
- at least **50 matching-scope observable events in the 30 days before onset**.

No minimum hidden severity, realized rate drop, hidden probability, detector score, or successful detection is part of eligibility. Duration is reported but is not an eligibility gate. Every report retains both all-incident and eligible-incident metrics.

The initial development audit contained 180 hidden incidents. Median matching-scope traffic was 3 attempts, 24 incidents had no observable attempt, and 167 had no attempt in the first 15 minutes. This makes low-volume all-incident recall intrinsically difficult and motivates a separate opportunity-to-detect denominator without removing those incidents from the report.

## Scope hierarchy

The detector independently updates three explicit levels:

1. `ISSUER`: payment method + issuer;
2. `PAYMENT_METHOD`: method only, including missing-issuer traffic;
3. `GLOBAL`.

An issuer alert can be opened only by evidence in that issuer's current window. Method/global history may supply a baseline prior when direct historical volume is insufficient, but a broad alert never creates a narrower issuer incident. Missing issuer values update method and global scopes only.

Volume gates increase with scope breadth: the frozen configuration requires 8 events for issuer scopes, at least 24 for method scopes, and at least 64 for global scope. This prevents broad aggregates from becoming noisier merely because they are evaluated more frequently.

## Windows and baseline

Analysis windows are 5, 15, 60, 360, and 1,440 minutes. The development observability audit justified the longer windows: matching-scope arrivals are usually too sparse for an hour-scale decision, while eligible incidents often last long enough to accumulate five events over a day. At time `T`, a window contains only events already delivered with observation timestamps at or before `T`.

The historical baseline is the trailing 30 days ending 24 hours before `T`. Excluding the maximum current window prevents the active anomaly from immediately teaching the baseline that degraded behavior is normal. Direct scope history is preferred; method and then global history are explicit fallback levels.

Historical and current success rates use Beta pseudo-count smoothing. The historical prior has mean 0.88 and configurable strength. The current posterior is shrunk toward the contemporaneous historical posterior mean. This protects small samples while allowing sustained evidence to dominate.

## Statistical and change signals

For every adequately populated window, the detector approximates the two independent Beta posteriors by their analytic means and variances and calculates:

`P(current_rate < baseline_rate - meaningful_drop)`

with a normal approximation to their difference. This probability is statistical evidence, not an AI confidence number.

An event-level EWMA of success outcomes supplies a complementary abrupt-change signal. Opening requires posterior confidence, a minimum posterior effect size, and an EWMA drop. Windows are ranked by posterior evidence. A strong decision additionally requires corroboration across nested windows, double the minimum volume, or overwhelming probability and effect size; the windows are not blindly ORed.

When current or historical volume is inadequate, status is `INSUFFICIENT_EVIDENCE`, distinct from `HEALTHY`.

## Lifecycle, severity, and health score

Each scope has a deterministic state machine:

`HEALTHY → SUSPECTED → OPEN → RECOVERING → RESOLVED`

Opening and recovery have independent persistence counts. Continued degradation updates the active incident rather than opening duplicates. Recovery must be sustained; renewed weak/degraded evidence moves a recovering incident back to open.

Predicted severity uses observable posterior effect size, probability, and volume. The 0–100 health score is `100 × current success rate / historical success rate`, bounded to 0–100. Neither copies hidden simulator severity. Opening uses the selected strong threshold; recovery instead requires a rate drop no greater than 6 points, an EWMA drop no greater than half the opening EWMA threshold, posterior probability below the suspected threshold, and four consecutive qualifying evaluations. Middle-band evidence holds state rather than forcing recovery.

## Dominant failure shifts

For open incidents, current-window failure-reason shares are compared with the same-scope historical failure distribution. Structured evidence reports current share, historical share, absolute change, relative lift, and support. No reason is emitted unless both distributions have enough failures and the current reason meets minimum support.

## Development selection protocol

Six explicit configurations vary minimum volume, meaningful drop, posterior probability, EWMA threshold, and opening persistence. No broad brute-force search is used.

The pre-registered objective is:

> Among configurations with no more than 0.02 false issuer incidents per scope-day, maximize eligible-incident recall; break ties by precision, then lower median delay after the fifth observable attempt. If none satisfy the constraint, minimize false incidents per scope-day before applying the same tie-breakers.

The selected configuration is written to `artifacts/detector/degradation-detector-v1.json`. Validation must load that artifact, refuses to run if it is absent, and refuses to overwrite an existing validation result.

## Episode evaluation

A correct detection is a one-to-one, exact method+issuer prediction opened no earlier than hidden onset and no later than 30 minutes after hidden end. The grace covers simulator delivery delay; it does not grant early overlapping false alerts credit. Reports include all/eligible recall, predicted-episode precision, false incidents per scope-day, raw delay, time to fifth observable attempt, delay after that attempt, resolution delay, hidden-severity recall, volume-bucket recall, severity confusion, supported root-cause evidence quality, and classified false positives.

Simple `STATIC_THRESHOLD` and `RELATIVE_DROP` episode detectors use the same 24-hour maximum current window, volume requirement, and recovery hysteresis for comparison.

## Development and validation results

Configuration candidate 1 was selected and frozen with hash `886c9eb4c45b7b3a2f88b30ff3d6b0356190a039135d989ee65497504e48fbcb`:

- minimum current issuer volume: 8;
- minimum baseline volume: 50;
- meaningful posterior drop: 0.08;
- posterior suspected/open probabilities: 0.60 / 0.75;
- EWMA alpha/drop threshold: 0.12 / 0.04;
- historical/current pseudo-count strengths: 12 / 4;
- opening/recovery persistence: 1 / 4.

The selected candidate maximized eligible recall among candidates satisfying the 0.02 false-incident constraint. Results are episode-level exact issuer-scope metrics:

| Metric | Development | One-time validation |
|---|---:|---:|
| Hidden incidents | 180 | 180 |
| Eligible incidents | 66 | 53 |
| All-incident recall | 5.56% | 4.44% |
| Eligible-incident recall | 12.12% | 13.21% |
| Predicted-episode precision | 2.83% | 2.85% |
| False issuer incidents | 343 | 273 |
| False incidents / scope-day | 0.01775 | 0.01412 |
| Mean detection delay | 704.88m | 692.35m |
| Median detection delay | 590.10m | 547.58m |
| P90 detection delay | 1455.38m | 952.59m |
| Median delay after fifth attempt | 405.03m | 288.61m |
| Median resolution delay | 1740.99m | 1663.08m |

The weak precision is not hidden: incidents are rare, while naturally occurring 24-hour scope fluctuations are common. False-positive classification on validation found 236 random fluctuations, 28 sparse-sample episodes, and 9 baseline-instability episodes. Method/global operational context produced another 49 validation episodes and is reported separately rather than treated as exact issuer predictions.

Validation recall by hidden severity was 0% mild, 3.17% moderate, 7.14% severe, and 40% critical. Recall by matching-scope traffic was 0% for 0–2 attempts, 3.45% for 3–4, 0% for 5–9, and 29.17% for 10+ attempts. The non-monotonic small buckets reflect tiny realized samples; no seed or incident was removed.

Supported dominant failure shifts were available for 5 of 8 validation detections (62.5% coverage), with the top observable reason agreeing with the simulator's expected reason in 40% of supported cases. Severity agreement is intentionally conservative: six of eight validation detections ended as mild and two as moderate despite more severe hidden labels.

The static threshold baseline reached 24.53% eligible validation recall but only 1.03% precision and 0.09462 false incidents per scope-day. Relative drop also reached 24.53% recall with 1.00% precision and 0.08707 false incidents per scope-day. The primary detector trades recall for approximately six-fold fewer false incidents.

Observable replay processed 20,000-event environments at 7,178 events/second in development and 7,349 events/second in validation, with mean update latency of 0.139ms and 0.136ms respectively.

The separate `DEMO SCENARIO — NOT BENCHMARK DATA` replays 996 deterministic events. The frozen detector opens 10 minutes after the visible degradation begins, escalates through moderate, severe, and critical observable states, identifies `ISSUER_UNAVAILABLE` with 44-event support and 7.81× relative lift, enters recovery, resolves after sustained recovery, and finishes healthy. It was not used for threshold selection or benchmark metrics.

Reserved final seeds `20261101`–`20261120` are not accessible through normal detector commands and remain untouched.

## Limitations

- The simulator produces very sparse incident-scope traffic, so most incidents are not quickly observable.
- The Beta-difference probability uses a normal approximation rather than numerical integration.
- Evaluation matching uses simulator incident intervals only after replay and includes a documented 30-minute delivery grace.
- Method and global alerts are operational context; exact issuer-episode precision evaluates issuer alerts only.
- Offline replay is single-process and does not yet persist production worker state.
- Eligible recall and precision remain too weak for autonomous operational decisions; this detector is evidence/context, not a payment-action authority.
