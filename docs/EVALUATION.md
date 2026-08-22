# Evaluation Methodology

## Objective

RecoverIQ will be evaluated as a recovery policy, not merely as a classifier. Every strategy must run on the same held-out payment scenarios and hidden environment outcomes. Reported values are generated artifacts from versioned code, configuration, seed, and later model artifacts. Phase 2.5 validates simulator and baseline methodology only; it makes no model-performance claim.

## Data split and leakage controls

Simulation generates timestamped recurring-payment histories and degradation incidents from a hidden environment. Observed features available to a decision at time `t` are separated from the hidden state that generates later outcomes. Event delivery order, explicit observation schemas, and leakage tests prevent future events, incident truth, true causes, latent customer state, and response probabilities from reaching policies. Future training, validation, calibration, threshold selection, and test data will use temporal boundaries. Random row splits are forbidden because they leak customer history, future issuer health, and incident outcomes.

The final test interval remains untouched until the strategy and policy configuration are frozen. Seeds, scenario configuration, package lockfiles, code revision, and generated artifacts will be recorded.

## Pre-registered seed groups

- **Development:** `20260901`–`20260910`, available during implementation.
- **Validation:** `20261001`–`20261010`, used for threshold or model selection after development choices exist.
- **Final evaluation:** `20261101`–`20261120`, reserved for final reporting and not run during normal development.

The groups are stable, explicit, and non-overlapping. The `robustness` CLI group is the development-plus-validation union (20 seeds). The `final` CLI path emits a prominent warning and requires `--acknowledge-final`. This is methodological discipline, not an access-control mechanism. Phase 2.5 executed development and validation only.

## Strategies

Phase 2 strategies receive identical cases and paired outcome randomness:

1. **Fixed Retry:** retry after one predetermined delay.
2. **Retry + Generic Reminder:** the same retry policy plus a basic policy-permitted contact.

RecoverIQ is intentionally absent until a later milestone. The evaluator, not the strategy, owns hidden ground truth. Deterministic outcome draws omit policy identity, so equivalent actions at the same time share a draw; differing prior interventions may still change their response probability. The initial benchmark command writes one experiment containing both policies and never regenerates customer or incident state between them.

## Financial measures

- **Failed payments:** eligible initial failures in the test interval.
- **Recovered payments:** distinct cases with an authoritative success after an attributable recovery action.
- **Recovery rate:** recovered payments divided by eligible failures.
- **SIMULATED gross recovered amount:** sum of attributed payment amounts, clearly labelled.
- **Net recovery value:** recovered amount minus configured retry, contact, incentive, and operational costs.

Attribution is at most once per payment/case. Values use integer minor currency units internally; display conversion is presentation only.

## Operational and safety measures

The Phase 2 report includes retries, customer contacts, payment links, human reviews, actions by type, average actions per failed/recovered case, time to recovery, intervention cost, and friction cost. A strategy that increases gross recovery while dramatically increasing interventions is not automatically superior.

## Predictive quality

No predictive metric is calculated in Phase 2 because no model exists. A future action-conditioned model will be reported with Brier score, reliability curves, expected calibration error, and discrimination metrics where useful. Calibration will be fit only on validation data.

## Degradation quality

Phase 3 pre-registers incident observability and detector selection before held-out evaluation. Eligibility requires five scope-matching events observed during an incident and 50 matching-scope observations in the prior 30 days. Development seeds alone select statistical thresholds under a false-incident constraint. The frozen configuration is then run once on validation. Incident ground truth is joined only after observable replay. Reports always retain all incidents and separately report eligible incidents, exact-scope episode precision/recall, false incidents per scope-day, detection delay, delay after the fifth observable attempt, resolution delay, severity/volume slices, and false-positive causes. Final seeds remain reserved.

## Statistical reporting

Aggregate point estimates include mean, median, sample standard deviation, minimum, maximum, and a normal `1.96 × sample standard error` 95% interval across deterministic seeds. No seed is manually discarded. Results include scenario counts and denominators. These intervals measure simulator-seed variation, not production uncertainty. If a future RecoverIQ strategy underperforms a baseline, the result remains visible.

## Reproduction artifact

Single benchmarks write a manifest, separately rooted observable/ground-truth Parquet data, baseline outcomes, JSON analysis, and Markdown quality report under `artifacts/simulations/<experiment-id>/`. Multi-seed reports use `artifacts/benchmark_suites/<suite-id>/`; sensitivity reports use `artifacts/sensitivity/<report-id>/`. Generated artifacts and all displayed financial values must be labelled **SIMULATED**. Later model benchmarks will add code revision, temporal splits, and model hashes through a controlled label-join step.
