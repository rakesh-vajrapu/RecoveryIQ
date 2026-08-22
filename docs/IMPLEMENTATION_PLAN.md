# RecoverIQ Implementation Plan

Each milestone ends with runnable verification and a review checkpoint. A later milestone may refine earlier architecture, but should not silently broaden scope.

## 1. Foundation — complete

- [x] Define product, architecture, safety, Gemini, and evaluation boundaries.
- [x] Scaffold FastAPI, typed settings, SQLAlchemy, Alembic, Celery, and structured logging.
- [x] Add initial domain models and migration.
- [x] Prove fake/fallback/Gemini provider abstraction.
- [x] Build a Next.js operational shell and runtime health connection.
- [x] Configure Docker Compose, CI, lint, types, and tests.

Exit: all feasible local checks pass without Docker or external credentials.

## 2. Seeded simulator

- [x] Define observed context separately from hidden environment state.
- [x] Generate reproducible merchants, renewals, attempts, failures, actions, and incidents.
- [x] Implement fixed-retry and retry-plus-reminder baselines.
- [x] Produce a versioned first experiment artifact without ML.

Exit: same seed/config produces the same dataset and baseline outcomes.

## 2.5. Simulator robustness — complete

- [x] Pre-register development, validation, and reserved final seed groups.
- [x] Run multi-seed baselines with distribution summaries and confidence intervals.
- [x] Add heterogeneous incident severity, duration, traffic exposure, and error shifts.
- [x] Audit nudge causality, failure-reason triviality, counterfactual randomness, costs, artifacts, and temporal leakage.
- [x] Run bounded configuration sensitivity and publish machine-readable/Markdown reports.

Exit: development and validation findings reproduce without using final seeds.

## 3. Degradation detection — complete

- [x] Implement rolling health aggregates, historical baselines, scope selection, and incident lifecycle.
- [x] Pre-register observability eligibility and tune only on development seeds.
- [x] Freeze detector configuration and run one validation evaluation.
- [x] Evaluate episode precision, recall, false incidents, delay, severity, volume, and diagnostics against simulator ground truth.

Exit: held-out incident metrics and threshold rationale are reproducible; final seeds remain untouched.

## 3.5. Operational degradation detector v2 — complete

- [x] Preserve detector v1 code and frozen benchmark artifacts.
- [x] Separate advisory WATCH evidence from strict CONFIRMED evidence.
- [x] Add sequential likelihood evidence, adaptive frozen baselines, reason-shift evidence, and hierarchical corroboration.
- [x] Select on development, freeze v2, and run the new `20261201`–`20261210` validation group exactly once.

Exit: WATCH and CONFIRMED metrics are separate, the hard-policy safety gate is explicit and failed (therefore both signals are advisory-only), and final seeds remain untouched.

## 4. Recovery ML — complete

- [x] Pre-register new training, development, calibration, and one-time model-test groups.
- [x] Generate one-action randomized exploration logs with explicit propensities.
- [x] Build leakage-safe temporal feature snapshots and action-conditioned 48-hour labels.
- [x] Compare logistic regression and a modest deterministic LightGBM search.
- [x] Freeze features/hyperparameters, select calibration on calibration seeds, and run held-out once.
- [x] Evaluate action ranking, health ablation, incident/cause slices, and structured SHAP evidence.
- [x] Persist versioned model/schema/calibration/report artifacts.

Exit: held-out Brier/calibration and action-level performance are reported honestly; both gates passed, the non-improving health-feature ablation remains visible, and final seeds remain untouched.

## 5. Decision and policy engine — complete

- [x] Pre-register policy development/validation seeds, ERV, candidates, costs, rules, margin selection, and validation gates.
- [x] Audit personalization and freeze global/simple observable baselines on policy development only.
- [x] Score exact-minor-unit ERV and implement typed feasibility, safety, abstention, STOP, and human-review decisions.
- [x] Freeze Policy V1 and execute the one-time policy-validation group.
- [x] Report paired strategy economics, oracle regret, ablations, slices, block analysis, and decision traces.
- [x] Preserve the detector's advisory-only boundary and enforce single-attribution invariants.

Detector V2 cannot provide a degradation-aware hard block in V1 because its safety gate failed; its fields remain advisory model inputs only. Policy V1 passed all four frozen validation gates with zero violations, but the no-health comparator again outperformed the primary and the legacy multi-action Reminder + Retry workflow remained stronger than the first-action policy. Exit: invariant tests prove the registered deterministic rules cannot be bypassed, policy validation is reported without retuning, and final seeds remain untouched.

## 6. Bounded sequential recovery and Recovery Model V2 — complete

- [x] Pre-register trajectory/model/policy seed groups, target, feature boundary, limits, and validation claims.
- [x] Generate observable randomized maximum-three-intervention trajectories with exact propensities and action-level attribution.
- [x] Train/freeze no-health tabular Model V2, calibrate once, and execute its held-out group once.
- [x] Implement bounded greedy Sequential Policy V2 and strong transparent full-horizon comparators.
- [x] Freeze policy rules/baselines on development and execute sequential validation once.
- [x] Report friction efficiency, sequences/transitions, personalization, bounded-oracle regret, and success/failure traces.

Exit achieved: Model V2 passed its frozen quality gate; all Phase 6 strategies received identical initial cohorts and 48-hour semantics; RecoverIQ passed every registered claim with zero violations; no episode exceeded three interventions; the probability-only comparator's small advantage remained visible; final seeds remain untouched.

## 7. Gemini enrichment

- [ ] Add versioned prompts and remaining structured schemas.
- [ ] Implement allowlisting, retries/backoff, concurrency, circuit breaking, caching, and metrics.
- [ ] Add injection, invalid-output, timeout, 429, and fallback tests.

Exit: all core decisions complete with Gemini disabled or failing.

## 8. Recovery execution

- [ ] Implement idempotent scheduling, simulated retries/nudges, observation, stopping rules, and attribution.

Exit: duplicate delivery and worker retry cannot duplicate side effects or revenue.

## 9. Razorpay Test Mode

- [ ] Validate webhook signatures and event idempotency.
- [ ] Add Test Mode payment/subscription handling and Payment Links where policy permits.

Exit: a credential-gated Test Mode demonstration succeeds; Live Mode is impossible.

## 10. Operational UI

- [ ] Implement Command Center, Payment Health, Recovery Queue, Decision Trace, and Evaluation Lab.
- [ ] Distinguish model evidence, policy decision, Gemini explanation, and authoritative outcome.

Exit: UI renders only persisted or reproducible data and clearly labels its mode.

## 11. Reliability

- [ ] Execute duplicate/out-of-order/provider/worker/Gemini/low-confidence/outage scenarios.
- [ ] Add regression tests and record real failures.

Exit: injected failures stop safely and leave complete audit evidence.

## 12. Final evaluation

- [ ] Freeze strategies and test interval, run multi-seed held-out benchmark, and publish immutable artifacts.

Exit: every displayed result traces to a reproducible artifact.

## 13. Submission

- [ ] Finalize README, diagrams, limitations, safety review, screenshots, demo script, and approximately five-minute video.

Exit: a reviewer can reproduce the demo from a clean clone and optional Test Mode credentials.
