# Engineering Failure Log

This file records failures actually observed while building or running RecoverIQ. Do not add hypothetical incidents as if they occurred. Planned failure-injection scenarios belong in test plans until executed.

## Entry template

### YYYY-MM-DD — Component: concise symptom

- **Context:** command or workflow being executed
- **Symptom:** observable failure
- **Root cause:** evidence-supported cause
- **Investigation:** checks that distinguished the cause
- **Fix/adaptation:** change made
- **Regression coverage:** automated check added, or reason none is applicable
- **Lesson:** reusable engineering conclusion

## 2026-08-21 — Environment: local Docker daemon unavailable

- **Context:** Phase 0 environment inspection before repository scaffolding.
- **Symptom:** Docker CLI and Compose were installable, but `docker info` could not connect to `//./pipe/docker_engine`.
- **Root cause:** the workspace runs on Windows Server in an Azure VM without exposed nested virtualization. Docker Desktop is unsupported on Windows Server, and no Linux container daemon is present.
- **Investigation:** checked Windows optional features, WSL status, `VirtualizationFirmwareEnabled`, Docker client output, and current Docker/Microsoft support documentation.
- **Fix/adaptation:** selected portable SQLAlchemy models with SQLite as the verified local database and retained Celery with configurable eager execution and in-memory transport when Redis is unavailable. The unused Docker Compose manifest was later removed from the final submission so the shipped runtime matches the verified demo.
- **Regression coverage:** backend tests must run with SQLite, eager Celery, and no external services; CI has no Docker dependency.
- **Lesson:** development fallbacks should preserve architectural boundaries rather than replacing production technologies or blocking foundation work.

## 2026-08-21 — Tooling: installed commands missing from inherited PATH

- **Context:** first parallel backend quality run and first Create Next App invocation after installing uv and Node.js.
- **Symptom:** child PowerShell processes reported that `uv` was unknown; `npx.cmd` then reported that `node` was unknown even though both installations had already been version-checked successfully.
- **Root cause:** the long-running Codex desktop process retained the PATH it inherited before Winget updated the user and machine environment. Newly opened system shells would receive the update, but task subprocesses inherited the stale parent value.
- **Investigation:** direct executable paths worked, and reconstructing PATH from the machine/user registry made the same versions resolve.
- **Fix/adaptation:** foundation commands use project virtual-environment executables or verified absolute paths during this run; developer instructions note that existing terminals must be restarted after tool installation. CI installs tools within each fresh job.
- **Regression coverage:** CI uses `astral-sh/setup-uv` and `actions/setup-node`; local verification was rerun through the project environments.
- **Lesson:** successful installation and PATH visibility are separate checks in long-lived automation hosts.

## 2026-08-21 — Frontend: health effect failed React lint rule

- **Context:** first `npm run lint` after implementing the client-side API health card.
- **Symptom:** `react-hooks/set-state-in-effect` rejected a health function invoked by `useEffect` because it synchronously changed state before beginning the network request.
- **Root cause:** the shared request helper set the `checking` state even though the component's initial state already represented that condition, creating an unnecessary render at effect startup.
- **Investigation:** strict TypeScript passed; ESLint pinpointed the effect call and explained the cascading-render risk.
- **Fix/adaptation:** made the fetch helper return data without changing React state, handled asynchronous completion in promise callbacks, and moved the explicit `checking` transition to the user-triggered Retry handler.
- **Regression coverage:** `npm run lint`, `npm run typecheck`, the production build, and live browser connectivity all pass.
- **Lesson:** keep network helpers state-free and let lifecycle subscriptions or event handlers own UI transitions.

## 2026-08-21 — Git: foundation checkpoint lacked author identity

- **Context:** creating the required local foundation checkpoint before Phase 2 changes.
- **Symptom:** `git commit` refused to create the commit because `user.name` and `user.email` were unset.
- **Root cause:** the fresh workspace had no global or repository-local Git author configuration.
- **Investigation:** the commit error named both missing identity keys; repository configuration confirmed neither was set.
- **Fix/adaptation:** configured the repository-local synthetic build identity `RecoverIQ Builder <recoveriq@local.invalid>` and reran the commit successfully. No global Git configuration was changed.
- **Regression coverage:** no automated test applies; the resulting commit hash proves the checkpoint completed.
- **Lesson:** validate repository-local author identity before an automated checkpoint without assuming a host-wide Git profile.

## 2026-08-22 — Simulator: scaled run missed degradation windows

- **Context:** running a 1,000-attempt benchmark smoke test against the default 120-day horizon.
- **Symptom:** the incident-deterioration sanity check failed because none of the selected attempts occurred during a hidden incident.
- **Root cause:** scaled generation sorted all renewal candidates and selected the first `N`, which compressed smaller runs into the earliest portion of the horizon instead of preserving temporal coverage.
- **Investigation:** the analysis reported zero incident-overlapping payments; inspecting candidate selection showed deterministic prefix truncation.
- **Fix/adaptation:** select evenly spaced candidate indexes across the complete configured horizon. The same 1,000-attempt command then covered incident windows and passed all sanity checks.
- **Regression coverage:** simulator tests require incident-overlapping payments and lower mean initial success probability during incidents; artifact analysis must pass the deterioration assertion.
- **Lesson:** scale controls for temporal simulations must preserve the time distribution, not only the row count.

## 2026-08-22 — Simulator validation: sparse incident samples broke realized-rate gates

- **Context:** first Phase 2.5 test and small multi-seed runs after adding variable traffic exposure and short incidents.
- **Symptom:** a valid scenario failed the incident-deterioration gate when a small realized Bernoulli sample happened not to deteriorate; another tiny suite had no incident-overlapping payment and rejected a `null` inside-incident rate.
- **Root cause:** validation conflated the configured probability response with noisy realized rates and assumed every scaled environment contained an exposed incident payment.
- **Investigation:** hidden initial success probabilities were lower during incidents even when the small realized success fraction was not; coverage counts confirmed zero overlap in the second case.
- **Fix/adaptation:** gate incident mechanics on the mean hidden initial probability while continuing to report realized rates, and represent unavailable coverage rates explicitly as `null` in small reports. Full 20,000-attempt suites retain populated realized-rate aggregates.
- **Regression coverage:** tests cover severity/duration diversity, incident probability deterioration, small multi-seed execution, and optional coverage metrics.
- **Lesson:** simulator integrity assertions should test the response mechanism; empirical realization belongs in adequately powered reports with explicit denominators.

## 2026-08-22 — Detector selection: first replay exhausted practical memory and time

- **Context:** first Phase 3 six-candidate replay over all ten development seeds.
- **Symptom:** the process exceeded five minutes, retained about 1.1 GB, and had not completed, so it was interrupted before producing a frozen configuration.
- **Root cause:** selection retained ten complete Pydantic scenarios simultaneously, and dominant failure-distribution shifts were recomputed for almost every otherwise healthy event rather than only for opening or active incidents.
- **Investigation:** a single-seed trace separated replay from episode evaluation, showed replay as the dominant cost, and measured roughly 2.9k events/second before the change. Process working-set inspection confirmed retained-scenario memory growth.
- **Fix/adaptation:** process one seed at a time, retain only compact replay/evaluation results, and calculate reason shifts only when an incident is opening or active. Replay increased to roughly 7.2k–7.3k events/second with bounded memory.
- **Regression coverage:** detector tests exercise deterministic replay and supported failure-shift creation; final reports persist throughput and mean update latency.
- **Lesson:** diagnostic enrichment belongs on exceptional lifecycle paths, and multi-seed harnesses should stream large immutable scenarios when cross-seed random access is unnecessary.

## 2026-08-22 — Detector lifecycle: neutral evidence bypassed configured recovery threshold

- **Context:** inspection of the first completed development-selection artifact before validation.
- **Symptom:** incident resolution was using any non-suspected evidence, even though `recovery_drop` existed in configuration; this could fragment ongoing episodes and shorten resolution delay artificially.
- **Root cause:** the state-machine implementation branched on strong/weak evidence but treated the remaining middle band as recovered without applying the separate recovery threshold.
- **Investigation:** code-path review showed `recovery_drop` was never referenced by lifecycle advancement. Development predicted-episode output contained avoidable fragmentation. Validation had not been invoked.
- **Fix/adaptation:** require rate drop at or below the recovery threshold, EWMA drop at or below half its opening threshold, posterior evidence below suspected, and four consecutive recovery evaluations. Ambiguous middle-band evidence now holds state. Development selection was rerun and the same configuration hash was frozen; validation remained valid for a single later run.
- **Regression coverage:** tests require one healthy observation not to resolve an incident, sustained recovery to resolve it, and continued degradation to update rather than duplicate the active episode.
- **Lesson:** opening, neutral, and recovery bands must be explicit; merely configuring hysteresis is insufficient unless every lifecycle transition consumes it.

## 2026-08-22 — Detector demo: warm-up could not supply frozen historical baseline

- **Context:** first execution of the separate controlled demo after the one-time validation run.
- **Symptom:** all 600 demo events completed with no incident and final status `INSUFFICIENT_EVIDENCE`.
- **Root cause:** the ten-hour warm-up was entirely inside the frozen detector's 24-hour baseline-exclusion interval, leaving no eligible historical observations.
- **Investigation:** the demo output reported no historical baseline and no predicted incidents while benchmark artifacts remained unchanged.
- **Fix/adaptation:** extend only the labelled non-benchmark demo to a two-day healthy warm-up, a two-hour degradation, and more than 24 hours of recovery. The frozen detector then opened, escalated, recovered, and resolved without threshold changes.
- **Regression coverage:** the controlled-demo test requires the non-benchmark label, one deduplicated incident, a resolved lifecycle, and a final healthy state.
- **Lesson:** demos must respect production-style warm-up requirements and should visibly show insufficient evidence when they do not.

## 2026-08-22 — Detector v2 lifecycle: confirmation emitted a duplicate severity transition

- **Context:** controlled detector-v2 lifecycle smoke before development selection, configuration freeze, or validation.
- **Symptom:** the CONFIRMED event could contain two identical same-timestamp severity transitions.
- **Root cause:** `_confirm` appended the correctly classified transition but did not synchronize the mutable episode's cached severity; the subsequent active-episode refresh interpreted the same classification as a new change.
- **Investigation:** the deterministic smoke reached the expected full lifecycle, but transition inspection showed the duplicate at confirmation and traced both writes through `_confirm` and `_refresh_active`.
- **Fix/adaptation:** synchronize the active episode severity inside `_confirm` before the refresh path runs.
- **Regression coverage:** the deterministic full-lifecycle demo test now rejects duplicate `(timestamp, evidence level, severity)` transitions and requires identical output across two replays.
- **Lesson:** state-transition emission and cached presentation state must update atomically when a single event drives both.

## 2026-08-22 — Phase 4 quality: strict mypy exposed legacy test annotation debt

- **Context:** final full-scope strict-mypy verification across simulator, both detector packages, Recovery ML, and all simulator tests.
- **Symptom:** mypy reported 22 errors in four pre-existing test-support files even though runtime tests passed.
- **Root cause:** fixture parameters and helper functions lacked explicit types, and `GeneratedScenario` was imported through a module that did not explicitly re-export it.
- **Investigation:** the errors were confined to tests; the frozen detector implementations, thresholds, and Phase 4 production packages were clean.
- **Fix/adaptation:** annotate the affected fixtures/helpers with their existing domain types and import `GeneratedScenario` from its defining ground-truth module. No detector logic or artifact changed.
- **Regression coverage:** strict mypy now passes all 73 simulator/detector/ML/test source files; all 88 runtime tests also pass.
- **Lesson:** run the repository's complete strict type-check scope, because runtime coverage alone does not validate typed test infrastructure.

## 2026-08-22 — Policy development: first freeze failed after redundant threshold evaluation

- **Context:** first `recovery-policy develop-policy` execution over all ten registered development seeds after the personalization audit.
- **Symptom:** after roughly 13 minutes, frozen-artifact construction raised `TypeError: FrozenPolicyArtifact got multiple values for normalized_erv_margin_threshold`; no policy artifact was written and validation had not started.
- **Root cause:** the serialized config payload already contained the threshold string while the constructor also supplied an explicit `Decimal` threshold. The threshold sweep also repeated the complete typed engine evaluation five times even though only the final margin decision changed.
- **Investigation:** confirmed both policy output paths were absent, traced the duplicate keyword to config assembly, and checked that every registered threshold shared identical candidate economics and hard/support evaluations.
- **Fix/adaptation:** build one explicit policy payload with a single Decimal threshold, execute the engine once at threshold zero, and apply each registered margin threshold as a deterministic transformation of those base decisions. A 200-decision parity check matched direct engine decisions at threshold `0.005` before the corrected full development freeze.
- **Regression coverage:** focused policy tests cover deterministic decisions, margin review behavior, config-hash reproduction, and the frozen policy artifact; Ruff and strict mypy cover the split implementation.
- **Lesson:** expensive threshold sweeps should cache invariant scoring/rule work, and artifact constructors should receive one canonical typed representation per field.

## 2026-08-22 — Policy validation reporting: abstention counterfactual and oracle STOP regret were misderived

- **Context:** audit of the compact report immediately after the single registered Policy V1 validation completed successfully.
- **Symptom:** all review cases appeared to have zero top-model oracle agreement because the analysis joined the probability policy's HUMAN_REVIEW outcome rather than its underlying top action; the oracle upper bound also showed a small negative mean regret when every feasible action had negative ERV and rationally selected STOP.
- **Root cause:** the abstention join reused post-policy records that intentionally removed autonomous selection on low support, and oracle regret did not include STOP's zero ERV when flooring the best/second-best oracle alternatives.
- **Investigation:** compared the 186 review records with their sealed candidate rows and found 122 underlying top-probability actions matched oracle-best; inspected the 675 oracle STOP cases and confirmed negative candidate ERV caused the impossible negative-regret result.
- **Fix/adaptation:** derive the top-model abstention counterfactual directly from sealed feasible candidate scores, include realized recovery and oracle regret only as evaluation diagnostics, and floor oracle best/second ERV at the rational STOP value of zero. Rebuilt derived JSON/Markdown metrics from the sealed candidate and decision Parquets; registered worlds, model scores, strategy decisions, outcomes, policy config, and gates were not rerun or changed. The validation artifact records this analysis-only correction and its refreshed digest.
- **Regression coverage:** the validation harness smoke verifies first-action attribution, trace outcomes, safety gates, and no-side-effect review/STOP records; oracle STOP normalization and abstention analysis run in the typed report path under Ruff and strict mypy.
- **Lesson:** counterfactual diagnostics must join pre-abstention candidate evidence, and any policy with STOP requires zero to be part of the oracle value set.
