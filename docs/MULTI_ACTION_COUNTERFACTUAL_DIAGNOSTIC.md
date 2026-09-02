# Paired Multi-Action Counterfactual Diagnostic V1

**Version**: 1.0.0
**Date**: 2026-09-02

## 1. Scientific Question

For the SAME eligible RecoveryIQ decision state where action $A^*$ is selected, how does the realized simulated outcome of $A^*$ compare with the realized outcomes of the other feasible actions ($A_1, A_2, \dots A_n$) available in the same state and hidden world?

This diagnostic evaluates the frozen, committed policy system inside Simulator 0.3.0.

## 2. Pairing and Hidden World

Every action branch shares exactly the same:
- Generated scenario (payment, customer, incidents, failure cause)
- Pre-decision observable state and history
- Decision timestamp and index
- Randomness architecture (keyed identically by the candidate's action type and execution time, not by policy name)

## 3. Comparison Window

For each candidate action, the Oracle evaluates the outcome respecting that candidate's existing registered execution timing and observation window. We do not force actions to share an artificial identical clock duration.

## 4. Frozen Assets and Integrity

- **Diagnostic Seeds**: `20261201` through `20261210` (10 seeds)
- **Simulator Version**: `0.3.0` (implied by repository HEAD)
- **Model V2 Version**: `2.0.0`
- **Model SHA256**: `60190d4c7c72dd2a482310d342131329673879137ce15be8e4451cb13dd2d898`
- **Calibrator SHA256**: `1c5b13a613bf04f3c9015fbe43b27c7ac138c2346310dd346b6c32000c21f85e`
- **Policy Version**: `2.0.0`
- **Policy Config Hash**: `ce7712b1ee4e800d54a875eb65a7bc826680e59faa465b54cbc1db7472010b25`

**No Retuning**: Regardless of the results, Model V2, Policy V2, ERV calculation, and the simulator response surface will remain unchanged.

## 5. Eligibility

A decision state is evaluated if and only if:
1. The policy selects an `ACTION` candidate (not `STOP` or `HUMAN_REVIEW`).
2. There are at least two feasible modelled candidates available.
3. The selected candidate is fully supported by the schema.

## 6. Metrics and Artifact Schema

The generated artifact `artifacts/evaluation/multi-action-counterfactual-v1/multi-action-counterfactual-summary-v1.json` will report:
- Eligible decisions & mean feasible candidates
- Selected action recovery rate & simulated net value
- Best-counterfactual recovery rate & simulated net value
- Realized regret (Best Counterfactual Net Value - Selected Net Value)
- Fraction of decisions where selected action was Best, Tied for Best, or Suboptimal
- Selected action advantage vs second-best alternative
- Counterfactual value capture (Selected Net Value / Best Feasible Net Value, where Best > 0)
- Breakdowns by selected action, failure reason, payment method, and decision index

## 7. Limitations

Simulator 0.3.0 does not model natural recovery during `WAIT`. Therefore, RecoveryIQ does not claim intervention-vs-natural-recovery causal uplift. This diagnostic measures policy action quality (intervention choice) inside the hand-designed simulator.
