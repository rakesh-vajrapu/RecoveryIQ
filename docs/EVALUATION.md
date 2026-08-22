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

### Detector v2 protocol

Detector v1 consumed `20261001`–`20261010`; those seeds are forbidden for v2 tuning. Phase 3.5 uses `20260901`–`20260910` for v2 architecture/selection and pre-registers a new one-time v2 validation group: `20261201`–`20261210`. The reserved final seeds `20261101`–`20261120` remain untouched. V2 retains the original eligibility definition and separately registers a high-evidence slice requiring 10 matching-scope observations within the first 24 hours after onset plus 100 prior 30-day matching-scope observations. The v2 hard-policy gate requires at least 70% confirmed-episode precision, at most 0.005 false confirmed episodes per issuer-scope-day, and at least 5 confirmed episodes on the new validation group.

The V2 configuration was frozen at hash `50f0ca055d561b447d1b2aa3769cf775917b9efbceb44c6934a8971c1585af8c` before the new group was generated. The group was executed exactly once. Held-out CONFIRMED precision was 3.70%, the false-confirmation rate was 0.005380 per issuer-scope-day, and 108 episodes satisfied the non-vacuity count. The gate therefore failed, the detector was not retuned, and the frozen CONFIRMED output is advisory-only. Full denominators and slices are in `artifacts/detector_v2/validation-evaluation-v2.json`; final seeds remain untouched.

### Recovery-model v1 protocol

Before any Phase 4 scenario generation, recovery-model v1 registers four new disjoint groups: training `20270101`–`20270120`, model development `20270201`–`20270210`, calibration `20270301`–`20270310`, and a one-time held-out model test `20270401`–`20270410`. The overall final seeds `20261101`–`20261120` remain untouched. Detector benchmark seeds are not ML training data.

Each initial failed payment contributes exactly one randomized logged action and one realized 48-hour outcome. Unselected counterfactual outcomes are absent from training and feature artifacts. Model architecture, feature allowlist/hash, LightGBM hyperparameters, and calibration method must freeze before the held-out command is enabled. The held-out command refuses overwrite. Counterfactual probabilities and hidden incident/cause fields may be joined only in evaluation after frozen predictions exist. Exact gates and feature boundaries are pre-registered in `docs/RECOVERY_MODEL.md`.

The registered stages completed in that order. The one-time held-out group produced 25,913 decisions. Isotonic-calibrated LightGBM achieved Brier 0.142495, log loss 0.439146, ECE 0.003721, ROC-AUC 0.786348, and PR-AUC 0.486602. Its top-1 oracle-action agreement was 68.44% versus 11.11% random and its pairwise ranking accuracy was 88.29%. Both preregistered gates passed. The matched model without health features was slightly better on Brier, log loss, ranking, and regret, so Phase 4 makes no claim that detector-health features improved prediction. No post-held-out tuning occurred and overall-final seeds remain untouched.

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

Phase 2 calculates no predictive metric. Phase 4 Recovery Model V1 reports Brier score, log loss, equal-width reliability bins and ECE, ROC-AUC, and PR-AUC overall and per action. It also reports simulator-only counterfactual ranking, a matched health-feature ablation, incident-adjacent slices, and hidden failure-family diagnostics. Calibration uses its distinct `20270301`–`20270310` group only after training/development freeze. The complete protocol and results are in `docs/RECOVERY_MODEL.md` and `artifacts/ml/reports/heldout-evaluation-v1.json`.

## Degradation quality

Phase 3 pre-registers incident observability and detector selection before held-out evaluation. Eligibility requires five scope-matching events observed during an incident and 50 matching-scope observations in the prior 30 days. Development seeds alone select statistical thresholds under a false-incident constraint. The frozen configuration is then run once on validation. Incident ground truth is joined only after observable replay. Reports always retain all incidents and separately report eligible incidents, exact-scope episode precision/recall, false incidents per scope-day, detection delay, delay after the fifth observable attempt, resolution delay, severity/volume slices, and false-positive causes. Final seeds remain reserved.

## Statistical reporting

Aggregate point estimates include mean, median, sample standard deviation, minimum, maximum, and a normal `1.96 × sample standard error` 95% interval across deterministic seeds. No seed is manually discarded. Results include scenario counts and denominators. These intervals measure simulator-seed variation, not production uncertainty. If a future RecoverIQ strategy underperforms a baseline, the result remains visible.

## Reproduction artifact

Single benchmarks write a manifest, separately rooted observable/ground-truth Parquet data, baseline outcomes, JSON analysis, and Markdown quality report under `artifacts/simulations/<experiment-id>/`. Multi-seed reports use `artifacts/benchmark_suites/<suite-id>/`; sensitivity reports use `artifacts/sensitivity/<report-id>/`. Generated artifacts and all displayed financial values must be labelled **SIMULATED**. Recovery-model artifacts add separated logged/feature tables, frozen joblib models and calibrators, schema/model hashes, registered seed manifests, full evaluation/SHAP reports, and `artifacts/ml/phase4-summary-v1.json`. Bulky Parquet data remains ignored while the compact manifests and frozen binaries are versioned.
