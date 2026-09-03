# RecoveryIQ Evaluation Evidence

> **SEALED · SIMULATED**
> These monetary results are simulation outputs and are not Razorpay revenue.

[Back to README](../README.md)

---

## Headline Economic Results

The sealed simulated evaluation of RecoveryIQ's Sequential Policy V2 completed with the following headline metrics across **27,406 episodes**:

| Metric | Value | Evidence |
| :--- | :--- | :--- |
| **Sealed episodes** | 27,406 | SIMULATED |
| **Recovered episodes** | 20,821 | SIMULATED |
| **Recovery rate** | 75.97% | SIMULATED |
| **Simulated net recovery value** | ₹4,71,96,320.70 | SIMULATED |
| **Incremental simulated value vs Reminder + Retry** | +₹1,44,07,440.70 | SIMULATED |
| **Policy violations** | 0 | SIMULATED |

<br/>

> **SIMULATED — NOT PROVIDER REVENUE**

---

## Recovery Strategy Benchmark

RecoveryIQ was evaluated against legitimate, version-controlled baseline strategies on identical hidden episodes.

| Strategy | Recovered | Rate | Simulated Net Value | Retries | Contacts | Violations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Greedy Hidden Oracle | 21,405 | 78.10% | ₹4,85,54,112.50 | 25,543 | 20,588 | 0 |
| Probability Policy | 20,878 | 76.18% | ₹4,72,69,616.40 | 28,610 | 20,010 | 0 |
| **RecoveryIQ Sequential ERV V2** | **20,821** | **75.97%** | **₹4,71,96,320.70** | **28,829** | **19,519** | **0** |
| Best Global Sequential | 18,774 | 68.50% | ₹4,23,99,715.00 | 37,154 | 18,851 | 0 |
| Simple Observable Rule | 17,704 | 64.60% | ₹4,01,06,631.10 | 30,819 | 24,493 | 0 |
| Reminder + Retry | 14,549 | 53.09% | ₹3,27,88,880.00 | 38,896 | 26,037 | 0 |
| Fixed Retry | 11,440 | 41.74% | ₹2,55,31,989.50 | 48,103 | 0 | 0 |

### Expected Recovery Value (ERV) Tradeoff

The *Probability Policy* achieved a slightly higher raw recovery rate (76.18% vs 75.97%). However, this is an intentional, supported outcome: **RecoveryIQ optimizes bounded sequential Expected Recovery Value (ERV)**. By accounting for intervention and contact burden, RecoveryIQ achieved near-parity economic value while utilizing almost 500 fewer customer contacts across the cohort rather than maximizing raw probability alone.

---

## Claims to Evidence

| Claim | Evidence artifact / source |
| :--- | :--- |
| **27,406 sealed episodes** | `artifacts/policy/recoveriq-sequential-v2/validation-evaluation-v2.json` |
| **75.97% simulated recovery** | Sequential Policy V2 evaluation endpoint |
| **₹1.44 Cr incremental simulated net value** | Sequential Policy V2 evaluation endpoint |
| **0 policy violations** | Policy evaluation endpoint |
| **Action-Conditioned ML** | LightGBM V2 models (`artifacts/ml/models/recovery-model-v2`) |
| **Expected Recovery Value** | `recoveriq_sequential_policy` calculation |

---

## Decision Quality and Model Calibration

Model V2 uses LightGBM to predict action-level recovery probabilities prior to decisions. The model was held out during tuning and scored exactly once. Isotonic calibration ensured decision reliability:

- **Brier Score:** 0.151320
- **Log Loss:** 0.456991
- **ROC-AUC:** 0.793268
- **PR-AUC:** 0.531004

## Hidden-Truth Isolation

To ensure scientifically honest results, hidden simulator ground truth (such as true causes, customer patience, and latent responses) is absolutely isolated from the policy and model execution. The evaluation oracle joins this hidden state only *after* deterministic policy decisions are completed to calculate exactly-once outcome mapping.

## Scope & Limitations

- The batch evaluation and all figures in this document are entirely simulated.
- ₹4.72 Cr does not represent Razorpay production revenue.
- Payment Health signals are derived from simulated events, not real live-mode issuer telemetry.
- No production deployment is claimed.


## Post-Hoc Counterfactual Action Advantage

Evidence status: **POST-HOC · SIMULATED**

**Metrics**:
- 48,405 eligible paired decisions
- 43.99% selected best/tied
- 52.29% counterfactual value capture

This evaluates the same simulated decision state where the selected action is compared with other feasible actions using an evaluation-only hidden-world realization. The comparator is a hindsight/reference diagnostic that identifies action-selection headroom.

> **LIMITATION**: Simulator 0.3.0 does not model direct natural recovery during WAIT.

**Explicitly Note**: This is NOT sealed evidence, causal uplift, treatment effect, or production causal evidence.
