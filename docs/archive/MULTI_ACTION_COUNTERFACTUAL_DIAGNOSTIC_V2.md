# Sealed Multi-Action Counterfactual Diagnostic V2

**Version**: 2.0.0
**Date**: 2026-09-03
**Status**: SEALED_POST_HOC_SIMULATED_COUNTERFACTUAL_DIAGNOSTIC

## 1. Scientific Question

For the SAME eligible RecoveryIQ decision state where action $A^*$ is selected, how does the realized simulated outcome of $A^*$ compare with the realized outcomes of the other feasible actions ($A_1, A_2, \dots A_n$) available in the same state and shared hidden world?

This diagnostic evaluates the frozen, committed policy system inside Simulator 0.3.0.

## 2. Shared Hidden World

All factual and counterfactual candidate branches for one decision MUST share the EXACT same frozen hidden world identity:
- Generated scenario
- Simulator seed
- Payment ground truth
- Customer/subscription latent traits
- Hidden failure cause
- Incident/degradation environment
- Pre-decision observable state
- Decision index/timestamp

Candidate branches are evaluated independently to prevent mutation interference, but they operate over the same hidden world variables.

## 3. Candidate Timing

For each candidate action, the Oracle evaluates the outcome respecting that candidate's existing registered execution timing and observation window. We do not force actions to share an artificial identical clock duration.

## 4. Frozen Assets and Integrity

- **Diagnostic Seeds**: Exactly 10 seeds: `20261301` through `20261310` inclusive.
- **Simulator Version**: `0.3.0` (implied by repository HEAD)
- **Model V2 Version**: `2.0.0`
- **Model SHA256**: `60190d4c7c72dd2a482310d342131329673879137ce15be8e4451cb13dd2d898`
- **Calibrator SHA256**: `1c5b13a613bf04f3c9015fbe43b27c7ac138c2346310dd346b6c32000c21f85e`
- **Policy Version**: `2.0.0`
- **Policy Config Hash**: `ce7712b1ee4e800d54a875eb65a7bc826680e59faa465b54cbc1db7472010b25`

**No Retuning**: Regardless of the results, Model V2, Policy V2, ERV calculation, and the simulator response surface will remain unchanged.

## 5. Eligibility

A decision is eligible when:
- RecoveryIQ decision kind is `ACTION`
- Selected candidate is supported
- At least TWO feasible modeled candidates exist INCLUDING the selected candidate
- Therefore at least one genuine alternative exists
- State is not terminal

## 6. Definitions

- **Best Feasible Action**: Highest realized simulated net value among ALL feasible candidates, including the selected candidate.
- **Best Alternative**: Highest realized simulated net value among feasible candidates EXCLUDING the selected candidate.
- **Selected Best/Tied**: Selected candidate's realized net value equals the maximum realized net value among all feasible candidates.
- **Realized Counterfactual Regret**: `max(0, best_feasible_realized_net_value - selected_realized_net_value)`.
- **Selected Action Advantage vs Best Alternative**: `selected_realized_net_value - best_alternative_realized_net_value`.

## 7. Counterfactual Value Capture
Defined as: `selected_total_realized_net_value / best_feasible_total_realized_net_value`. Only reported when denominator > 0. It is computed as a portfolio aggregate across all decisions, not averaged per decision.

## 8. Realized Net Value Definition
Uses current simulator accounting:
- If recovery: `amount_minor - intervention_cost_minor - friction_cost_minor`
- If no recovery: `0 - intervention_cost_minor - friction_cost_minor`

## 9. One-Time Execution Guard
The final execution uses a durable attempt marker and artifact overwrite refusal. Execution refuses to run if an attempt is detected, requiring a formal, documented invalidation record and a new set of seeds for any reruns due to defects.

## 10. Limitations
Simulator 0.3.0 does not model natural recovery during WAIT. This diagnostic does not estimate intervention vs natural recovery causal uplift, treatment effect, or production incrementality. It compares the selected action vs alternative feasible interventions inside the frozen simulated hidden world.
