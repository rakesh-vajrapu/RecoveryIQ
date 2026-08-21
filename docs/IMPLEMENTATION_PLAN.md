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

## 3. Degradation detection

- [ ] Implement rolling health aggregates, historical baselines, scope selection, and incident lifecycle.
- [ ] Evaluate precision, recall, and delay against simulator ground truth.

Exit: held-out incident metrics and threshold rationale are reproducible.

## 4. Recovery ML

- [ ] Build leakage-safe temporal features and action-conditioned labels.
- [ ] Compare simple classifier and LightGBM; calibrate on validation only.
- [ ] Add SHAP evidence and model artifact/version tracking.

Exit: held-out Brier/calibration and action-level performance are reported honestly.

## 5. Decision and policy engine

- [ ] Score ERV, implement executable state transitions, confidence gates, limits, abstention, and human review.
- [ ] Enforce degradation-aware blocks and single-attribution invariants.

Exit: property/invariant tests prove policies cannot be bypassed.

## 6. Gemini enrichment

- [ ] Add versioned prompts and remaining structured schemas.
- [ ] Implement allowlisting, retries/backoff, concurrency, circuit breaking, caching, and metrics.
- [ ] Add injection, invalid-output, timeout, 429, and fallback tests.

Exit: all core decisions complete with Gemini disabled or failing.

## 7. Recovery execution

- [ ] Implement idempotent scheduling, simulated retries/nudges, observation, stopping rules, and attribution.

Exit: duplicate delivery and worker retry cannot duplicate side effects or revenue.

## 8. Razorpay Test Mode

- [ ] Validate webhook signatures and event idempotency.
- [ ] Add Test Mode payment/subscription handling and Payment Links where policy permits.

Exit: a credential-gated Test Mode demonstration succeeds; Live Mode is impossible.

## 9. Operational UI

- [ ] Implement Command Center, Payment Health, Recovery Queue, Decision Trace, and Evaluation Lab.
- [ ] Distinguish model evidence, policy decision, Gemini explanation, and authoritative outcome.

Exit: UI renders only persisted or reproducible data and clearly labels its mode.

## 10. Reliability

- [ ] Execute duplicate/out-of-order/provider/worker/Gemini/low-confidence/outage scenarios.
- [ ] Add regression tests and record real failures.

Exit: injected failures stop safely and leave complete audit evidence.

## 11. Final evaluation

- [ ] Freeze strategies and test interval, run multi-seed held-out benchmark, and publish immutable artifacts.

Exit: every displayed result traces to a reproducible artifact.

## 12. Submission

- [ ] Finalize README, diagrams, limitations, safety review, screenshots, demo script, and approximately five-minute video.

Exit: a reviewer can reproduce the demo from a clean clone and optional Test Mode credentials.
