# Recovery Model V2

## Frozen research hypothesis and stage protocol

This document preregisters trajectory-aware Recovery Model V2 before sequential data generation. The primary model is deterministic tabular LightGBM trained **without all Detector V2/payment-health features**. A same-boundary logistic regression is the baseline. This choice is fixed because both previous independent held-out phases found no health-feature benefit. A health-inclusive V2 comparator is optional only after the primary is frozen and cannot replace it post hoc.

Registered groups are training `20270801`-`20270820`, development `20270901`-`20270910`, calibration `20271001`-`20271010`, and one-time held-out test `20271101`-`20271110`. Policy groups and overall-final seeds cannot enter model selection.

## Feature schema V2

`RecoveryFeatureSnapshotV2` is a typed action-conditioned state summary. Predictive features are:

- payment: amount, method, issuer or `UNKNOWN`, observable failure reason/source, attempt number, cyclical decision hour/day, and elapsed hours since original failure;
- customer/subscription: prior attempts/successes/failures/rates, subscription tenure, time since last successful payment, and preceding observable recovery-history counts;
- current episode: one-based decision index, prior autonomous interventions, retry/contact/link/method-update/alternate counts, active-link and method-update state, last action, hours since last action, and previous intervention result;
- candidate action: action type, delay, contact flag, method-change flag, and observation-window hours.

Forbidden predictive inputs include raw entity IDs, episode ID, seed, hidden customer traits, true cause, hidden incident membership/state, hidden effectiveness, oracle probability/action, counterfactual outcomes, future events, and every `health_*` field. The episode key is retained only for grouping and split diagnostics.

The feature schema version, ordered allowlist, annotations, and no-health requirement produce a frozen SHA-256 schema hash before training. Decision-index and previous-action fields are constructed only from interventions whose outcomes were already observed.

## Target and model families

The binary target is `action_recovered_before_next_decision`. One logged row corresponds to one selected action. Later recovery cannot modify an earlier row.

The logistic baseline and LightGBM primary consume the same feature boundary. Development tests four modest deterministic LightGBM candidates inherited in spirit from V1: 15 or 31 leaves, depth 5 or 8, learning rate 0.05 with 200 trees or 0.03 with 350 trees, minimum child samples 40 or 80, fixed regularization, one CPU model thread, and fixed random state `20270800`. Selection minimizes development Brier, then log loss, then ECE. No AutoML or sequence model is used.

## Calibration freeze

Calibration seeds alone compare sigmoid and isotonic mappings for the selected LightGBM and logistic baseline. The primary method minimizes calibrated Brier, then log loss, then ECE and is applied separately to both models. Model files, hyperparameters, feature hash, raw/calibrated metrics, calibrator files/hashes, support counts by action/decision index, and package versions freeze before held-out execution.

## One-time held-out evaluation

The held-out command writes a durable attempt marker and refuses rerun. It reports Brier, log loss, ECE, ROC-AUC, and PR-AUC overall, per action, and for decision indexes 1/2/3. Hidden counterfactual probabilities are joined only after frozen predictions and report top-1/top-2 action agreement, pairwise accuracy, and mean/median/P90 probability regret by decision index.

The preregistered Model V2 quality gate is:

1. no forbidden feature or target leakage and exact frozen schema/hash;
2. calibrated LightGBM overall Brier no worse than calibrated logistic regression;
3. calibrated LightGBM overall ECE at most 0.05;
4. decision indexes 2 and 3 each have at least 500 held-out rows, Brier at most 0.30, and ECE at most 0.10;
5. pairwise oracle-probability ranking accuracy at least 0.55 for each supported decision index.

Every condition must pass for the overall gate. A failed gate remains visible and may restrict the sequential policy to simple fallback/review on unsupported stages; it does not authorize retraining after held-out inspection.

## Why tabular state, not reinforcement learning

The simulator supplies a bounded three-step supervised trajectory with explicit action-level attribution. A tabular state model is easier to calibrate, audit, reproduce, and compare than RL or a neural sequence model. Greedy policy evaluation is direct, while logged propensities remain available for later off-policy research. More complex sequence methods require future evidence that the explicit state summary is insufficient.

## Frozen artifacts and results

The registered protocol completed without post-held-out tuning. The trajectory logger produced 125,942 training decisions across 54,785 episodes. Decision indexes 1/2/3 contributed 54,785, 41,670, and 29,487 rows. The action distribution ranged from 12,559 `OFFER_ALTERNATE_METHOD` rows to 14,794 `SEND_NUDGE` rows, and exact logged propensities remained between `1/9` and `1/2` as feasibility narrowed.

Development selected LightGBM candidate 1: 31 leaves, maximum depth 8, 200 estimators, learning rate 0.05, minimum child samples 80, column fraction 0.8, L1 0.1, and L2 1.0. Isotonic calibration then won the registered calibration comparison. Model V2 is version `2.0.0`; feature schema `2.0` has SHA-256 `d3e87a20f104fac0b860ae71a2c583a3a922209b5ef10b0eac5c7f1213601cc5`. The LightGBM artifact hash is `60190d4c7c72dd2a482310d342131329673879137ce15be8e4451cb13dd2d898`; its calibrator hash is `1c5b13a613bf04f3c9015fbe43b27c7ac138c2346310dd346b6c32000c21f85e`.

The one-time held-out run contained 62,918 decisions across 27,451 episodes and passed the full gate. The calibrated logistic baseline had Brier 0.176440, log loss 0.534610, ECE 0.005272, ROC-AUC 0.670779, and PR-AUC 0.404170. Calibrated primary LightGBM had Brier 0.151320, log loss 0.456991, ECE 0.004226, ROC-AUC 0.793268, and PR-AUC 0.531004.

| Decision index | Rows | Positive rate | Brier | ECE | ROC-AUC | PR-AUC | Top-1 | Top-2 | Pairwise | Mean regret | P90 regret |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 27,451 | 0.2436 | 0.144929 | 0.005137 | 0.799647 | 0.530877 | 0.6142 | 0.8038 | 0.8979 | 0.03698 | 0.15950 |
| 2 | 20,763 | 0.2527 | 0.149324 | 0.006311 | 0.796646 | 0.529664 | 0.6102 | 0.7007 | 0.8643 | 0.03738 | 0.13200 |
| 3 | 14,704 | 0.2860 | 0.166069 | 0.005541 | 0.773320 | 0.532955 | 0.6450 | 0.7477 | 0.8518 | 0.02421 | 0.03903 |

Decision 3 discrimination weakened modestly but did not collapse, and every stage retained ample support and passed its ranking gate. The optional health-feature research comparator was not run; the primary remains preregistered no-health Model V2. The compact source of truth is `artifacts/ml/reports_v2/heldout-evaluation-v2.json`.
