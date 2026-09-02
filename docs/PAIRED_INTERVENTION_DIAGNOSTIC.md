# Paired Intervention Value Diagnostic: Preregistration

**Version**: 1.0.0
**Date**: 2026-09-02

## 1. Goal

Measure the simulated incremental value of an intervention chosen by RecoveryIQ compared to a paired no-immediate-intervention counterfactual (WAIT), evaluated inside the exact same simulated hidden world. 

## 2. Methodology

For every eligible sequential decision state where RecoveryIQ (Model V2 + Sequential Policy V2) selects a valid intervention A:
- We execute A in the `SequentialScenarioOracle`.
- We execute a counterfactual `WAIT` intervention in the same `SequentialScenarioOracle`, using the exact same pre-decision state, identical seed, and identical hidden customer/incident properties. The counterfactual `WAIT` observation window is perfectly symmetric to A's observation window.

## 3. Simulator Semantics: "No Immediate Intervention"

In the current `RecoveryProbabilityModel`, `ActionType.WAIT` deterministically yields a 0.0 probability of recovery. Thus, the matched "no-immediate-intervention" comparator will honestly simulate a 0% recovery rate and incur 0 intervention/friction cost.

## 4. Frozen Assets

This diagnostic evaluates the frozen, committed policy system without modifying it.
- **Simulator Version**: `0.1.0` (implied by repository HEAD)
- **Model V2 Version**: `2.0.0`
- **Model SHA256**: `60190d4c7c72dd2a482310d342131329673879137ce15be8e4451cb13dd2d898`
- **Calibrator SHA256**: `1c5b13a613bf04f3c9015fbe43b27c7ac138c2346310dd346b6c32000c21f85e`
- **Policy Version**: `2.0.0`
- **Policy Config Hash**: `ce7712b1ee4e800d54a875eb65a7bc826680e59faa465b54cbc1db7472010b25`

## 5. Seed Registration

To prevent data contamination and ensure this diagnostic does not overlap with any training, calibration, or primary validation sets, we register a NEW diagnostic seed group:
- **Diagnostic Seeds**: `20261201` through `20261210` (10 seeds)

## 6. Eligibility Definition

A decision is eligible for the paired diagnostic if and only if:
1. The policy selects a valid intervention candidate (not `STOP` or `HUMAN_REVIEW`).
2. The selected candidate is fully supported by the schema and valid to execute.

## 7. Metrics

The artifact will compute and freeze the following headline metrics:
- Total decisions & eligible paired decisions
- Factual intervention recovery rate
- No-immediate-intervention recovery rate (expected to be 0%)
- Paired difference in recovery rate
- Factual simulated recovered value
- Counterfactual simulated recovered value (expected to be 0)
- Intervention & friction cost
- Paired incremental simulated net value
- Breakdown by Action, Failure Reason, Payment Method, and Decision Index

## 8. Limitations

1. **Simulated Only**: The matched outcomes are generated inside RecoveryIQ's frozen simulator. This is an evaluation artifact against a hand-designed hidden response surface, not production causal evidence.
2. **Not an Uplift Model**: This diagnostic is a post-hoc evaluation of a deterministic policy, not a trained CATE/T-Learner model.
3. **No Retuning**: The diagnostic results must not be used to tune the `SequentialPolicyEngine` or Model V2 parameters.
