# Action-Conditioned Recovery Model V1

## Phase boundary and status

This document was committed to the working tree as the Phase 4 pre-registration before any Phase 4 seed was generated. The registered stages have now completed in order: feature and protocol freeze, training/development, model freeze, calibration freeze, then exactly one held-out execution. Recovery Model V1 is frozen at version `1.0.0` with feature schema `1.0` and schema hash `b2cb0d026f0f625128a320122ba90a31cf4f0acdab729f3c5bfb429bdd74b559`.

Detector V2 remains frozen at version `2.0.0` and configuration hash `50f0ca055d561b447d1b2aa3769cf775917b9efbceb44c6934a8971c1585af8c`. Its validation hard-policy gate failed. WATCH, CONFIRMED, and continuous health values are **advisory feature sources only**. Neither state may authorize, block, stop, or execute recovery activity, and CONFIRMED is not ground truth.

Phase 4 estimates:

`P(recovered_within_48h | observable context at T, candidate action, action timing)`

It evaluates probability and action-ranking quality only. It does not implement expected recovery value, action selection policy, financial authorization, side effects, Gemini, Razorpay, or frontend work.

## Pre-registered seed protocol

- Training: `20270101`–`20270120`.
- Model development and modest hyperparameter selection: `20270201`–`20270210`.
- Calibration-method selection and fitting: `20270301`–`20270310`.
- One-time held-out model test: `20270401`–`20270410`.
- Overall final Buildathon evaluation: `20261101`–`20261120`, untouched.

The model-test command must refuse to run until the feature schema, model family, hyperparameters, and calibration artifact are frozen. It must refuse to overwrite an existing held-out result. Calibration and held-out groups are forbidden to normal logging/training/development commands.

## Logged exploration protocol

Each eligible initial failed payment creates one decision at its observable failure-delivery timestamp `T`. The logging policy receives only the public `PaymentObservation`, observable history through `T`, prior logged-action history whose execution time is no later than `T`, and frozen detector-V2 output through the current event.

The six action types are:

- `RETRY_NOW`, delay 0 hours;
- `RETRY_LATER`, delay chosen from 2, 6, 12, or 24 hours;
- `SEND_NUDGE`, delay 0 hours;
- `CREATE_PAYMENT_LINK`, delay 0 hours;
- `REQUEST_PAYMENT_METHOD_UPDATE`, delay 0 hours;
- `OFFER_ALTERNATE_METHOD`, delay 0 hours.

All six types are feasible in the current simulator. Exploration first selects an action type uniformly with probability `1/6`. Conditional on `RETRY_LATER`, it selects one of the four delays uniformly, so each delayed-retry candidate has propensity `1/24`; every other candidate has propensity `1/6`. Hidden response probabilities, true cause, instrument state, incident state, and unselected outcomes cannot influence selection.

Only the selected action executes. A row records the selected action, delay, propensity, candidate count, decision timestamp, observable feature snapshot, and its one realized `recovered_within_48h` outcome. No unselected counterfactual outcome or probability is present in logged or feature artifacts. Approximately uniform action-type coverage makes propensity weighting unnecessary for the primary conditional models; propensities remain available for audit and future estimands.

## Target and action timing

`recovered_within_48h` is true only when the selected action executes no later than 48 hours after `T` and produces the simulator's single realized recovery outcome. The maximum action delay is 24 hours, leaving 24 hours inside the target window. The target is not eventual recovery.

## Frozen feature boundary

`RecoveryFeatureSnapshot` version `1.0` is the inference boundary. Raw customer, payment, subscription, event, merchant, experiment, and seed identifiers are forbidden predictive columns. A non-predictive SHA-256 decision key may exist only in the logged-record envelope for deterministic joins and audit.

Categorical model features are:

- `payment_method`, `issuer`, `failure_reason`, `failure_source`, `action_type`.

Numeric and Boolean model features are:

- payment/action: `amount_minor`, `attempt_number`, cyclical hour/day components, `failure_to_decision_hours`, `time_since_previous_payment_attempt_hours`, `delay_hours`, `customer_contact_action`, `payment_method_change_action`, `current_contact_count`, `current_retry_count`;
- observable history: subscription/customer prior attempts, successes and rates, prior failed renewals, prior logged recovery attempts/successes/nudges/retries/payment links, subscription tenure, and time since last observable successful payment;
- issuer, method, and global health: baseline success and support, 5m/15m/60m rates and volumes, baseline-to-window deltas, maximum degradation CUSUM, recovery likelihood evidence, Jensen–Shannon divergence, dominant-reason increase/lift/support, WATCH and CONFIRMED indicators, time since WATCH/CONFIRMED, and issuer parent method/global WATCH indicators.

Missing sparse health values remain explicit missing numeric values and separate availability indicators where needed; they are imputed inside the model pipeline. Health-free ablation removes every feature with the `health_` prefix while preserving identical rows, target, action features, training seeds, and development procedure.

An exact allowlist and schema hash are code-enforced at training and inference. Hidden incident fields, hidden severity, true cause, incident end time, instrument state, latent customer traits, counterfactual probabilities/outcomes, and future health are forbidden.

## Model and development selection

The interpretable baseline is one shared action-conditioned logistic-regression pipeline with median numeric imputation, most-frequent categorical imputation, standardization, and one-hot encoding.

The primary candidate is one shared LightGBM binary classifier using the same feature snapshot, action type, and timing. Training is deterministic with fixed random seeds, `deterministic=true`, forced column-wise construction, and one thread. No class balancing or outcome resampling is applied.

The modest development search contains four predeclared configurations spanning 15/31 leaves, depth 5/8, learning rates 0.03/0.05, 200/350 estimators, minimum child samples 40/80, column fractions 0.8/1.0, and L1/L2 regularization. Development selection minimizes Brier score, then log loss, then ECE. Both health-inclusive and health-free models use the same chosen configuration to keep the ablation interpretable.

## Calibration protocol

After hyperparameters and features freeze, calibration seeds evaluate Platt/sigmoid and isotonic mappings fitted only to frozen-model predictions. Selection minimizes calibration Brier score, then log loss, then ECE. The selected method and fitted mapping freeze before held-out evaluation.

The pre-registered held-out calibration safety gate passes only if all are true:

- calibrated Brier score is lower than the held-out constant-training-prevalence baseline;
- 10-bin equal-width ECE is at most `0.05`;
- for every reliability bin with at least 100 samples, absolute prediction/outcome gap is at most `0.15`.

Failure means Phase 5 may use bands/advisory confidence only, not economically precise probabilities. Held-out results cannot trigger recalibration or threshold changes.

## Model quality gate

On the one-time held-out group, LightGBM passes the model-quality gate only if:

- its calibrated Brier score or log loss improves on calibrated logistic regression by at least `0.0001` absolute; and
- pairwise oracle-ranking accuracy is greater than `0.50`; and
- top-1 oracle agreement exceeds the mean random agreement `mean(1 / feasible_candidate_count)`.

If this gate fails, the simpler logistic model remains the recommended prediction artifact. Disappointing held-out performance is not an implementation bug.

## Held-out evaluation

Logged held-out rows report Brier score, log loss, ECE, ROC-AUC, PR-AUC, reliability bins, and the same metrics by selected action where support permits. Ground truth may be joined only after prediction for incident adjacency, hidden cause-family diagnostics, and simulator-only counterfactual ranking.

Ranking evaluates every feasible candidate without executing an intelligent policy. The frozen model scores observable context plus each candidate; the evaluation layer alone obtains hidden simulator probabilities. It reports top-1 oracle agreement, top-2 coverage, pairwise ranking accuracy, and mean/median/P90 probability regret. No oracle field may enter a model snapshot.

The health-feature ablation compares otherwise equivalent frozen LightGBM models on probability and ranking metrics, including during/outside hidden incidents, near onset or clearance, and high/low observable health-evidence slices. A non-improvement remains visible.

SHAP produces structured global and local evidence from model features only. It cannot mutate state, select an action, authorize policy, or generate Gemini prose.

## Results

### Logged data and model selection

The deterministic logger produced 53,790 training examples (12,293 positive; 22.85%), 27,444 development examples, 26,730 calibration examples, and 25,913 held-out examples. Training action coverage was approximately uniform:

| Selected action | Training examples |
| --- | ---: |
| `CREATE_PAYMENT_LINK` | 8,849 |
| `OFFER_ALTERNATE_METHOD` | 9,049 |
| `REQUEST_PAYMENT_METHOD_UPDATE` | 8,943 |
| `RETRY_LATER` | 9,009 |
| `RETRY_NOW` | 8,953 |
| `SEND_NUDGE` | 8,987 |

No inverse-propensity weighting, class balancing, or outcome resampling was used. Every row contains one selected action and its one realized outcome. The training logged-data digest is `36bdbdb2039cd1d763aa8669ecd432842b7820149068ea23bccec5a6b2f853fa`.

On development, logistic regression achieved Brier `0.166045`, log loss `0.508425`, ECE `0.029496`, ROC-AUC `0.670818`, and PR-AUC `0.358930`. Candidate 1 won the predeclared LightGBM selection rule with Brier `0.145030`, log loss `0.445178`, ECE `0.014440`, ROC-AUC `0.783680`, and PR-AUC `0.495599`. Its frozen configuration is 31 leaves, depth 8, learning rate 0.05, 200 estimators, 80 minimum child samples, 0.8 column sampling, L1 0.1, L2 1.0, and full row sampling.

Isotonic calibration beat sigmoid on the calibration group by the frozen selection rule: Brier `0.142130` versus `0.142639`, and log loss `0.437027` versus `0.439364`. Calibration was fitted after model freeze and before the held-out command.

### One-time held-out probability results

The guarded held-out command ran once on `20270401`–`20270410`, producing 25,913 randomized-action outcomes with a 22.61% positive rate. No held-out result was used to alter features, model parameters, calibration, or gates.

| Model/state | Brier | Log loss | ECE | ROC-AUC | PR-AUC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Constant training-prevalence baseline | 0.174986 | 0.534541 | 0.002434 | 0.500000 | 0.226103 |
| Logistic, raw | 0.164016 | 0.503789 | 0.033588 | 0.670578 | 0.358493 |
| Logistic, calibrated | 0.162131 | 0.497230 | 0.005000 | 0.676688 | 0.343624 |
| LightGBM, raw | 0.142618 | 0.438980 | 0.014310 | 0.786739 | 0.494436 |
| LightGBM, isotonic calibrated | **0.142495** | **0.439146** | **0.003721** | **0.786348** | **0.486602** |

Calibration improved LightGBM Brier and ECE while slightly worsening log loss and discrimination metrics, which an outcome-monotone calibration mapping is not optimized to improve. Among reliability bins with at least 100 examples, the maximum absolute predicted-versus-observed gap was `0.010106`; sparse upper-tail bins remain visible in the machine-readable report but do not satisfy the preregistered support threshold.

### Per-action held-out results

| Logged action | N | Positive rate | Brier | Log loss | ECE | ROC-AUC | PR-AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `CREATE_PAYMENT_LINK` | 4,258 | 0.2795 | 0.1981 | 0.5835 | 0.0291 | 0.5980 | 0.3347 |
| `OFFER_ALTERNATE_METHOD` | 4,286 | 0.3542 | 0.2050 | 0.5949 | 0.0229 | 0.6923 | 0.4979 |
| `REQUEST_PAYMENT_METHOD_UPDATE` | 4,417 | 0.2149 | 0.1153 | 0.3814 | 0.0191 | 0.7974 | 0.5484 |
| `RETRY_LATER` | 4,313 | 0.2574 | 0.1481 | 0.4495 | 0.0259 | 0.8077 | 0.5338 |
| `RETRY_NOW` | 4,323 | 0.1478 | 0.1051 | 0.3421 | 0.0136 | 0.7984 | 0.3762 |
| `SEND_NUDGE` | 4,316 | 0.1050 | 0.0852 | 0.2881 | 0.0084 | 0.7765 | 0.2269 |

All action types have more than 4,200 held-out logged examples. Per-action reliability bins with small support must still be interpreted cautiously.

### Simulator-only candidate ranking

The frozen calibrated LightGBM was applied to all nine candidates before the evaluation layer joined simulator counterfactual probabilities. Top-1 oracle agreement was `0.684406` versus random `0.111111`; top-2 oracle coverage was `0.831745`; pairwise ranking accuracy was `0.882866`. Probability regret was mean `0.046950`, median `0.000000`, and P90 `0.197862`. These are simulator-only diagnostics, not an executed policy or a claim of real-world causal identification.

### Health-feature ablation

Payment-health features did **not** improve held-out predictive or ranking quality. The health-free LightGBM had Brier `0.142368` versus `0.142495`, log loss `0.437969` versus `0.439146`, top-1 agreement `0.697835` versus `0.684406`, pairwise accuracy `0.885950` versus `0.882866`, and mean regret `0.041564` versus `0.046950`. The health-inclusive model had better ECE (`0.003721` versus `0.006999`) only. The primary health-inclusive artifact remains the pre-registered model under test; no post-test model switch or detector change was made.

Incident-adjacent diagnostics were:

| Slice | N | Brier | Log loss | ECE | ROC-AUC | PR-AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| During hidden incident | 176 | 0.1322 | 0.4091 | 0.0999 | 0.7635 | 0.3339 |
| Outside hidden incident | 25,737 | 0.1426 | 0.4394 | 0.0038 | 0.7867 | 0.4881 |
| Near incident boundary, 6h | 267 | 0.1440 | 0.4360 | 0.0529 | 0.7791 | 0.4231 |
| Not near incident boundary, 6h | 25,646 | 0.1425 | 0.4392 | 0.0033 | 0.7864 | 0.4875 |
| High observable health evidence | 19,666 | 0.1422 | 0.4384 | 0.0048 | 0.7870 | 0.4849 |
| Low observable health evidence | 6,247 | 0.1433 | 0.4414 | 0.0078 | 0.7842 | 0.4933 |

The incident and boundary slices are small and are diagnostic only. They do not establish a positive health-feature contribution.

### Failure-family diagnostics

| Hidden evaluation-only family | N | Brier | Log loss | ECE | ROC-AUC | PR-AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Authentication friction | 3,757 | 0.1732 | 0.5264 | 0.0373 | 0.6457 | 0.3196 |
| Customer confirmation | 2,991 | 0.1556 | 0.4795 | 0.0229 | 0.6864 | 0.3310 |
| Inactive mandate | 1,682 | 0.1301 | 0.3897 | 0.0314 | 0.8508 | 0.5769 |
| Invalid instrument | 4,225 | 0.1293 | 0.3831 | 0.0235 | 0.8585 | 0.5933 |
| Issuer degradation | 1,985 | 0.1772 | 0.5167 | 0.0494 | 0.7848 | 0.5742 |
| Liquidity shortfall | 6,093 | 0.1102 | 0.3728 | 0.0241 | 0.6576 | 0.2465 |
| Network instability | 3,705 | 0.1579 | 0.4710 | 0.0122 | 0.7948 | 0.5322 |
| Unknown temporary | 1,475 | 0.1376 | 0.4413 | 0.0302 | 0.6568 | 0.2748 |

Hidden families are used only after prediction for diagnosis and never enter the feature snapshot.

### SHAP evidence

The leading global mean-absolute SHAP features were `action_type_SEND_NUDGE`, `failure_source_CUSTOMER`, `action_type_RETRY_NOW`, `action_type_OFFER_ALTERNATE_METHOD`, `action_type_REQUEST_PAYMENT_METHOD_UPDATE`, `failure_source_INSTRUMENT`, `delay_hours`, `action_type_CREATE_PAYMENT_LINK`, `customer_contact_action`, and `failure_reason_INSUFFICIENT_FUNDS`.

In one persisted local comparison for the same observable decision, `RETRY_LATER` at 24 hours scored `0.564460` after calibration while `SEND_NUDGE` scored `0.059946`. The largest retry-later contribution was `delay_hours` (`+0.861695` raw-score SHAP); the largest nudge contribution was the nudge action indicator (`-0.745924`). Health evidence appeared lower in the contribution ranking. These values explain the frozen tree score; they do not prove causality or authorize the action.

### Gates, artifacts, and runtime

The calibration safety gate **PASSED**: Brier beat the constant baseline, ECE was below 0.05, and every supported reliability-bin gap was below 0.15. The model quality gate **PASSED**: calibrated LightGBM improved Brier by `0.019637` and log loss by `0.058084` over calibrated logistic, while both ranking checks beat random. The registered recommended artifact is calibrated LightGBM.

Frozen binaries, calibration mappings, manifests, hashes, compact evidence, full reliability bins, per-action results, ranking diagnostics, slices, and SHAP values are under `artifacts/ml/`. Registered-stage runtime was approximately 549.59 seconds: training logging 147.53s, development logging 72.01s, model selection 21.76s, calibration logging 72.17s, calibration fit 1.31s, held-out logging/evaluation-truth generation 206.22s, and held-out evaluation 28.58s.

## Reproduction commands

From the repository root, a clean artifact directory can be built in the registered order:

```powershell
uv sync --project simulator --dev --locked
uv run --project simulator recovery-model generate-logged --group training
uv run --project simulator recovery-model generate-logged --group development
uv run --project simulator recovery-model train
uv run --project simulator recovery-model calibrate
uv run --project simulator recovery-model evaluate-heldout
uv run --project simulator recovery-model shap-report
uv run --project simulator recovery-model phase4-summary
```

The held-out command refuses a second run in the same artifact root. `shap-report` and `phase4-summary` read existing frozen evidence without replaying seeds. Calibration, held-out, and overall-final seeds are rejected by the normal replay command.

## Known limitations

- All outcomes and counterfactual rankings are synthetic and depend on the current simulator response model; no production causal or calibration claim follows.
- Uniform randomized exploration supports the six action types, but the four delayed-retry candidates individually have lower `1/24` propensity.
- The current simulator exposes no separate observable failure-step field, so V1 cannot include it.
- Health-inclusive V1 did not beat the matched health-free ablation on Brier, log loss, or ranking; detector V2 remains advisory-only and its failed hard-policy gate is unchanged.
- Isotonic calibration creates sparse extreme-probability bins. Overall supported bins passed, while small per-action and incident-adjacent slices need wider uncertainty treatment before economic use.
- SHAP explains model behavior, not intervention causality, policy safety, or authorization.
- No intelligent policy, ERV optimizer, autonomous execution, Gemini feature, Razorpay integration, frontend ML dashboard, or final overall benchmark was implemented.
