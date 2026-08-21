# Evaluation Methodology

## Objective

RecoverIQ will be evaluated as a recovery policy, not merely as a classifier. Every strategy must run on the same held-out payment scenarios and hidden environment outcomes. Reported values will be generated artifacts from versioned code, configuration, data seed, and model artifacts. No benchmark numbers exist in Phase 1.

## Data split and leakage controls

Simulation will generate timestamped recurring-payment histories and degradation incidents from a hidden environment. Observed features available to a decision at time `t` will be separated from the hidden probability that generates its later outcome. Training, validation, calibration, threshold selection, and test data will use temporal boundaries. Random row splits are forbidden because they leak customer history, future issuer health, and incident outcomes.

The final test interval remains untouched until the strategy and policy configuration are frozen. Seeds, scenario configuration, package lockfiles, code revision, and generated artifacts will be recorded.

## Strategies

All strategies receive identical cases and outcome randomness:

1. **Fixed Retry:** retry after one predetermined delay.
2. **Retry + Generic Reminder:** the same retry policy plus a basic policy-permitted contact.
3. **RecoverIQ:** customer and payment context, degradation evidence, action-conditioned recovery prediction, calibrated probabilities, ERV scoring, deterministic policy, confidence gating, and abstention.

The evaluator, not the strategy, owns hidden ground truth and outcome generation. This prevents RecoverIQ from selecting actions using the exact hidden probability it is meant to estimate.

## Financial measures

- **Failed payments:** eligible initial failures in the test interval.
- **Recovered payments:** distinct cases with an authoritative success after an attributable recovery action.
- **Recovery rate:** recovered payments divided by eligible failures.
- **SIMULATED gross recovered amount:** sum of attributed payment amounts, clearly labelled.
- **Net recovery value:** recovered amount minus configured retry, contact, incentive, and operational costs.

Attribution is at most once per payment/case. Values use integer minor currency units internally; display conversion is presentation only.

## Operational and safety measures

The report also includes unnecessary retries, customer-contact count, actions by type, average actions per case, human-review rate, abstention rate, policy violations, decision latency, throughput, Gemini calls, and fallback rate. A strategy that increases gross recovery while violating policy or dramatically increasing contacts is not considered superior.

## Predictive quality

Action-conditioned predictions will be reported with Brier score, reliability curves, expected calibration error, and discrimination metrics where useful. Calibration is fit only on validation data. SHAP may explain LightGBM feature contributions but will not be treated as causal evidence.

## Degradation quality

Incident evaluation uses simulator ground truth to measure precision, recall, false-positive rate, and detection delay at the payment-method and issuer scope. Thresholds and minimum sample sizes are chosen on validation incidents, not the held-out test interval.

## Statistical reporting

Aggregate point estimates will be accompanied by uncertainty across multiple deterministic seeds or bootstrap intervals where appropriate. Results will include scenario counts and denominators. If RecoverIQ underperforms a baseline, the result remains visible and prompts investigation rather than manual alteration.

## Reproduction artifact

The future benchmark command will write a machine-readable result containing schema version, timestamp, git revision, seed/config hash, split boundaries, strategy configuration, model artifact hashes, and every displayed metric. The UI will consume that artifact and label it **SIMULATED**. Phase 1 creates no performance artifact and makes no performance claim.

