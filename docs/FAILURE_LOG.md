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
- **Fix/adaptation:** retained PostgreSQL and Redis in Docker Compose for supported full environments; selected portable SQLAlchemy models with SQLite as the default local database; retained Celery with configurable eager execution and in-memory transport when Redis is unavailable. Docker Compose syntax is validated without starting containers.
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
