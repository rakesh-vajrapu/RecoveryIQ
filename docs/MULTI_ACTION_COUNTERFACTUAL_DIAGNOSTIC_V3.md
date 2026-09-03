# MULTI-ACTION COUNTERFACTUAL DIAGNOSTIC V3 (SEALED)

## Artifact Status
`SEALED_POST_HOC_SIMULATED_COUNTERFACTUAL_DIAGNOSTIC`

## Methodology
Post-hoc counterfactual diagnostic that tests the exact sequence of actions chosen by the frozen policy against all other feasible alternatives *at the time of the decision*.

## Freeze Hashes
- **Implementation Freeze SHA**: `303763f6c63d486bd74697d73da15fbda2ff8497`
- **Simulator Version**: `0.3.0`
- **Model Version**: `2.0.0`
- **Model SHA256**: `60190d4c7c72dd2a482310d342131329673879137ce15be8e4451cb13dd2d898`
- **Calibration SHA256**: `1c5b13a613bf04f3c9015fbe43b27c7ac138c2346310dd346b6c32000c21f85e`
- **Policy Version**: `2.0.0`
- **Policy Config Hash**: `ce7712b1ee4e800d54a875eb65a7bc826680e59faa465b54cbc1db7472010b25`

## Execution Protocol
- **Diagnostic Seeds**: Exactly 10 seeds: `20261401` through `20261410` inclusive.
- **Shared Hidden World**: The factual and counterfactual outcomes for any given decision share the exact same random state, incident timeline, payment truth, and failure reason.
- **Eligibility**: Decisions where `SequentialDecisionKind.ACTION` was selected AND there were at least 2 feasible modeled candidates available.
- **Candidate Timing**: The immediate evaluation assumes the alternative action replaces the selected action precisely at the same timestamp in the episode.

## Metrics
- **Realized Net Value**: `recovered_amount_minor - (intervention_cost_minor + friction_cost_minor)`.
- **Selected Total Realized Net Value**: Sum of realized net value for the factual selected action across all eligible decisions.
- **Best Feasible Total Realized Net Value**: Sum of realized net value for the best feasible action (including the selected action) across all eligible decisions.
- **Counterfactual Value Capture**: `Selected Total Realized Net Value / Best Feasible Total Realized Net Value` (computed as a single global ratio, NOT an average of ratios). Only valid if denominator > 0.
- **Regret**: `max(0, best_feasible - selected)` per decision.
- **Best Alternative**: Maximum realized net value among feasible candidates *excluding* the selected action.
- **Advantage vs Best Alternative**: `selected - best_alternative` per decision.

## Attempt Marker Semantics
The execution script will write a sealed `.attempt_sealed` marker file to the exact canonical artifact output directory before generating any scenarios or loading any seeds. 
If the marker or the output artifact exists at the absolute canonical path, the script will refuse to run.

## Limitations
- Matched outcomes are generated inside RecoveryIQ's frozen simulator.
- This is not production causal evidence.
- Simulator 0.3.0 does not model direct natural recovery during WAIT.
- This measures policy action quality inside the hand-designed simulator.

## No Retuning Rule
After the implementation freeze, no diagnostic code, simulator behavior, candidate semantics, or metric definitions may be changed based on the V3 results.
