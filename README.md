# RecoveryIQ

**Razorpay Buildathon 2026 · Track 03 — AI Revenue Recovery**

### Autonomous Revenue Recovery Control Plane for Razorpay-style payment workflows

**🌐 Live Demo:** https://recoveryiq-ai.vercel.app

Try RecoveryIQ — interactive replay of frozen Model V2 → ERV → Policy V2 decisions using sealed simulated evidence.

**RecoveryIQ is an AI Revenue Recovery Agent and bounded control plane that detects revenue at risk, estimates action-conditioned recovery probability, selects the highest-value safe intervention using Expected Recovery Value, executes supported recovery workflows under deterministic policy guardrails, verifies provider outcomes, and attributes recovered revenue exactly once locally.** **Live reviewer deployment: Next.js on Vercel with the FastAPI control plane hosted on Microsoft Azure App Service.**

> **Evidence note:** All portfolio evaluation results are **simulated** and do not represent Razorpay production revenue. Razorpay integration evidence uses **Test Mode only**. **No real money is moved.**

[![Live Demo](https://img.shields.io/badge/Live_Demo-Vercel-000000?style=flat-square&logo=vercel)](https://recoveryiq-ai.vercel.app/demo)
![Azure App Service](https://img.shields.io/badge/Backend_Cloud-Microsoft_Azure_App_Service-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)
![FastAPI · Python 3.12](https://img.shields.io/badge/Backend-FastAPI_·_Python_3.12-009688?style=flat-square&logo=fastapi)
![Next.js 16 · React 19](https://img.shields.io/badge/Frontend-Next.js_16_·_React_19-000000?style=flat-square&logo=nextdotjs)
![LightGBM V2 · Calibrated](https://img.shields.io/badge/ML-LightGBM_V2_·_Calibrated-FF9900?style=flat-square)
![Optimization](https://img.shields.io/badge/Optimization-Expected_Recovery_Value-0052CC?style=flat-square)
![Policy](https://img.shields.io/badge/Policy-Sequential_Policy_V2-0052CC?style=flat-square)
![Razorpay Test Mode](https://img.shields.io/badge/Provider-Razorpay_Test_Mode-0B58C6?style=flat-square)
![Critical Financial Path Gate](https://img.shields.io/badge/Verification-Critical_Financial_Path_Gate-2EA043?style=flat-square)
![27,406 SEALED · SIMULATED Episodes](https://img.shields.io/badge/Evaluation-27,406_SEALED_·_SIMULATED_Episodes-2EA043?style=flat-square)


## 🎯 Judge & Reviewer Snapshot

| Pillar | RecoveryIQ |
|---|---|
| **Live Deployment** | Next.js on Vercel → FastAPI on Microsoft Azure App Service; public reviewer runtime remains simulation-only. |
| **Core Value Proposition** | Recovers failed recurring payments by choosing the highest-value safe intervention rather than blindly retrying. |
| **Decision Intelligence** | Action-conditioned LightGBM V2 estimates calibrated `P(recovery | action, context)` for feasible interventions. |
| **Economic Optimization** | Expected Recovery Value balances recovery probability, payment value, intervention cost, and customer friction. |
| **Financial Authority** | Deterministic Sequential Policy V2 — not the LLM — authorizes, schedules, escalates, filters, or stops recovery actions. |
| **Provider Verification** | Signed Razorpay Test Mode webhooks authenticate incoming provider events; Provider Truth Triangulation independently checks Payment Link state before a newly triangulated paid event is confirmed. |
| **Accounting Safety** | Exactly-once LOCAL outcome and recovery attribution semantics backed by durable idempotency/uniqueness protections. |
| **Evidence** | 27,406 SEALED · SIMULATED episodes; 75.97% recovery; ₹4.71 Cr simulated net recovery; 0 policy violations. |
| **AI Boundary** | LLM is explanation-only and has zero financial execution authority. |

**MODEL PREDICTS → ERV OPTIMIZES → POLICY AUTHORIZES → PROVIDER VERIFIES → AI EXPLAINS**

---

## 🔎 Reviewer Evidence Map

| Proof | Where to inspect |
|---|---|
| Recovery control plane | [Command Center](https://recoveryiq-ai.vercel.app/) |
| Deterministic decision authority | [Decision Trace](https://recoveryiq-ai.vercel.app/decision-trace) |
| Idempotency / concurrency evidence | [Safety Lab](https://recoveryiq-ai.vercel.app/safety-lab) |
| Razorpay Test Mode integration | [Razorpay Evidence](https://recoveryiq-ai.vercel.app/integrations/razorpay) |
| Sealed performance evidence | [Evaluation Lab](https://recoveryiq-ai.vercel.app/evaluation) |

---

## 💸 The Business Problem

A failed payment does not automatically mean **"retry it now."**

Failures can come from customer liquidity, expired instruments, mandate issues, transient network errors, or broader issuer/payment-method degradation. Blind retries can waste attempts, increase customer friction, and optimize for recovery probability instead of economic value.

RecoveryIQ separates intelligence from financial authority:

**Detect → Predict → Optimize → Guard → Execute → Verify → Attribute**

---

## ⚡ RecoveryIQ in 60 Seconds

RecoveryIQ is an autonomous revenue recovery control plane built to avoid naive payment retries and unsafe AI execution.

**RecoveryIQ is not simply a payment-failure classifier. Its core thesis is adaptive multi-step recovery over a bounded episode, where the next action can change after observing previous outcomes, while deterministic constraints limit retries, contacts, horizon, and total interventions.**

It uses event-driven payment-failure correlation and an **Action-Conditioned LightGBM V2 Probability Engine** to estimate `P(recovery | action, context)` under candidate actions. **Expected Recovery Value (ERV) Optimization** ranks interventions by balancing calibrated recovery probability, recoverable payment value, intervention cost, and customer friction cost.

Every recommendation passes through **Deterministic Sequential Policy Guardrails**, which enforces limits on retries, contacts, interventions, and recovery horizon. Supported actions execute through Razorpay Test Mode, where **Signed HMAC Webhook Verification** (raw-body HMAC SHA-256) authenticates the webhook; Provider Truth Triangulation independently fetches provider state before a triangulated Payment Link recovery is confirmed. **Idempotency Guardrails** and **Exactly-Once local outcome and recovery attribution semantics** ensure database uniqueness constraints protect local outcomes and attribution from duplication.

The LLM remains strictly **explanation-only** and has **NO FINANCIAL EXECUTION AUTHORITY**.

---

## 🧠 Core Engineering Signals

| Engineering Capability | RecoveryIQ Implementation |
| --- | --- |
| **AI Revenue Recovery Agent** | Bounded control plane integrating ML, economics, policy, and execution |
| **Action-Conditioned LightGBM V2 Probability Engine** | Estimates calibrated `P(recovery | action, context)` for feasible recovery actions |
| **Expected Recovery Value (ERV) Optimization** | Ranks interventions using expected recovered value minus intervention and friction costs |
| **Deterministic Sequential Policy Guardrails** | Enforces recovery horizon, intervention, retry, contact, support, and stopping limits |
| **Idempotency Guardrails** | Durable execution reservations and database `UNIQUE` constraints prevent duplicate local financial effects |
| **Signed HMAC Webhook Verification** | Razorpay Test Mode webhook signatures are validated against the raw request body before processing |
| **Exactly-Once local outcome and recovery attribution semantics** | Verified provider outcomes map to at most one local `RecoveryAttribution` |
| **Human-in-the-Loop Escalation** | Insufficient model support or missing context safely routes to `HUMAN_REVIEW` |
| **Adversarial Concurrency Verification** | Isolated 10-way webhook, executor, and success races verify duplicate protection |
| **Auditable Decision Trace** | Decision → execution plan → execution → provider outcome → attribution are separately persisted and auditable |

---

## ⚖️ AI Judgment — Right Tool, Right Place

| Problem / Responsibility | Tool | Why |
|---|---|---|
| Action-conditioned recovery probability | LightGBM + isotonic calibration | Structured nonlinear tabular prediction under uncertainty |
| Economic action ranking | Deterministic Expected Recovery Value (ERV) | Arithmetic/business economics does not require generative AI |
| Financial authorization | Deterministic Sequential Policy V2 | Financial decisions need reproducible, auditable limits and abstention |
| Payment degradation detection | Statistical Detector V2 | Population-level observability; explicitly ADVISORY ONLY because it did not pass the hard-policy authority gate |
| Provider truth | Razorpay signed evidence + independent provider verification where persisted | Payment truth must come from provider evidence, not AI inference |
| Human-readable explanation | Optional Groq LLM + deterministic fallback | Language generation is appropriate here; LLM has ZERO financial execution authority |
| Causal incremental lift | Not claimed from this simulator | Requires randomized holdouts / controlled treatment evidence |

[Read the Evaluation Results →](docs/EVALUATION_RESULTS.md)

---

## 🔧 What Broke — and What Changed

This section directly answers Razorpay’s: **“What broke, and what did you do about it?”**

1. **Detector V2 authority gate:** Detector V2 did not pass the hard-policy safety/authority gate. As a result, the detector remains advisory-only for observability/context and has zero policy overrides / execution authority.
2. **Real provider context vs frozen Model V2:** During Razorpay integration, real provider events did not necessarily contain enough historical context to safely reconstruct the frozen Model V2 feature contract. Instead of inventing or zero-filling features, the system fails closed and routes to `HUMAN_REVIEW` rather than fabricating historical or provider context.
3. **Probability Policy negative result:** Frozen validation showed Probability Policy slightly beat RecoveryIQ Sequential ERV V2 in raw recovery (76.18% vs 75.97%). However, RecoveryIQ used 491 fewer customer contacts across the cohort. This negative raw-recovery result was preserved rather than tuning against protected validation.
4. **Distributed provider ambiguity:** Stale external execution reservations are now deterministically recovered without blind provider replay; CFP-03 is PROVEN, while unknown provider outcome/crash ambiguity remains PARTIALLY_PROTECTED. Distributed-system guarantees are deliberately scoped to local outcome/attribution semantics.

[Safety & Reliability](docs/SAFETY_AND_RELIABILITY.md)

---

## 🧭 Explore RecoveryIQ

| Document | Why It Matters |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | ML → ERV → deterministic policy → execution → provider verification → attribution |
| [Evaluation Results](docs/EVALUATION_RESULTS.md) | Sealed benchmark, methodology, baselines, and economic evidence |
| [Safety & Reliability](docs/SAFETY_AND_RELIABILITY.md) | Idempotency, concurrency verification, and reliability boundaries |
| [Razorpay Evidence](docs/RAZORPAY_EVIDENCE.md) | Test Mode Payment Link → signed webhook → outcome → attribution lifecycle |
| [Degradation Detection V2](docs/DEGRADATION_DETECTION_V2.md) | Advisory degradation intelligence across supported scopes |

---

## 🎯 Track 03 Control Loop

RecoveryIQ directly addresses Razorpay Track 03 by implementing:
**Detect → Decide → Guard → Execute → Verify → Attribute → Measure**

| Track Stage | RecoveryIQ |
| --- | --- |
| **DETECT** | Event-driven revenue-at-risk correlation + advisory degradation context |
| **DECIDE** | Action-conditioned Recovery Model V2 + Expected Recovery Value optimization |
| **GUARD** | Deterministic Sequential Policy V2 bounds retries, contacts, interventions, and horizon |
| **EXECUTE** | Executes supported actions or safely defers to `HUMAN_REVIEW` / `STOP` |
| **VERIFY** | Authenticates Razorpay Test Mode evidence through signed webhooks |
| **ATTRIBUTE** | Maps verified `ExternalOutcome` → `RecoveryAttribution` with exactly-once local semantics |
| **MEASURE** | Evaluates performance across 27,406 sealed simulated episodes |

---

## 📊 Headline Evidence

The sealed evaluation of RecoveryIQ Sequential Policy V2 produced the following results.

> **All SEALED · SIMULATED values are simulation outputs and are NOT provider revenue.**

| Metric | Value | Evidence Lane |
| --- | ---: | --- |
| **Sealed Episodes** | 27,406 | SEALED · SIMULATED |
| **Recovered Episodes** | 20,821 | SEALED · SIMULATED |
| **Recovery Rate** | 75.97% | SEALED · SIMULATED |
| **Simulated Net Recovery Value** | ₹4,71,96,320.70 | SEALED · SIMULATED |
| **Incremental Simulated Value vs Reminder + Retry** | +₹1,44,07,440.70 | SEALED · SIMULATED |
| **Policy Violations** | 0 | SEALED · SIMULATED |
| **Razorpay Test Mode** | Historical recovery: ₹2.00 (Provider Fetch: NOT CAPTURED) | RAZORPAY · TEST MODE |
| **10-way Webhook Race** | 10 → 1 logical event | ISOLATED LOCAL VERIFICATION |
| **10-way Execution Race** | 10 → 1 fake-provider call | ISOLATED LOCAL VERIFICATION |

---

## 📈 Full Recovery Strategy Benchmark

RecoveryIQ was evaluated against version-controlled strategies on the same sealed simulated evaluation set.

| Strategy | Recovered | Rate | Simulated Net Value | Retries | Contacts | Violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Greedy Hidden Oracle | 21,405 | 78.10% | ₹4,85,54,112.50 | 25,543 | 20,588 | 0 |
| Probability Policy | 20,878 | 76.18% | ₹4,72,69,616.40 | 28,610 | 20,010 | 0 |
| **RecoveryIQ Sequential ERV V2** | **20,821** | **75.97%** | **₹4,71,96,320.70** | **28,829** | **19,519** | **0** |
| Best Global Sequential | 18,774 | 68.50% | ₹4,23,99,715.00 | 37,154 | 18,851 | 0 |
| Simple Observable Rule | 17,704 | 64.60% | ₹4,01,06,631.10 | 30,819 | 24,493 | 0 |
| Reminder + Retry | 14,549 | 53.09% | ₹3,27,88,880.00 | 38,896 | 26,037 | 0 |
| Fixed Retry | 11,440 | 41.74% | ₹2,55,31,989.50 | 48,103 | 0 | 0 |

> **Trade-off:** Probability Policy achieves a slightly higher raw recovery rate (**76.18% vs 75.97%**), while RecoveryIQ Sequential ERV V2 uses fewer customer contacts and optimizes a bounded economic objective rather than raw recovery probability alone.

---

## 🏗️ Architecture

RecoveryIQ relies on three layers: **probabilistic intelligence**, **deterministic financial boundaries**, and **verified execution**.

![RecoveryIQ Architecture](docs/assets/architecture.png)

[Read the full Architecture Deep Dive →](docs/ARCHITECTURE.md)

### The Execution Flow

1. **ML:** Predicts recovery probability for feasible candidate actions.
2. **ERV:** Evaluates economic value using probability, revenue, cost, and friction.
3. **Policy:** Deterministic boundaries authorize, block, escalate, or stop.
4. **Execution:** Supported actions run through the appropriate execution path.
5. **Provider:** Razorpay Test Mode verifies external payment outcomes through authenticated events.
6. **Attribution:** Verified outcomes are mapped once locally to recovery attribution.

### Recovery Governance Profile

The frozen Sequential Policy V2 remains deterministic financial authority.

- **Autonomy Bounds:** 48-hour horizon, max 3 interventions, max 2 retries, max 2 contacts, 2-hour minimum retry interval.
- **STOP:** MAX_INTERVENTIONS, RECOVERY_HORIZON, BUDGETS_EXHAUSTED, NO_FEASIBLE_ACTION, NON_POSITIVE_INCREMENTAL_ERV.
- **HUMAN_REVIEW:** insufficient MODEL_SUPPORT, insufficient CALIBRATION_SUPPORT, LOW_DECISION_MARGIN.
- **FILTER / SCHEDULE:** retry/contact caps constrain candidates; customer opt-out constrains contact actions; quiet hours schedule contact actions; duplicate Payment Links filter that candidate; minimum retry interval filters/schedules retry candidates.
- **PRE-ENGINE:** MODEL_SCHEMA_VALID.
- **ACCOUNTING:** ATTRIBUTION_ONCE.

### LLM Authority Boundary

> **MODEL PREDICTS → ERV OPTIMIZES → POLICY AUTHORIZES → PROVIDER VERIFIES → AI EXPLAINS**

The LLM is **explanation-only**. It cannot authorize payment execution, change frozen deterministic policy limits, mark a payment recovered, or modify recovery attribution.

---

## 🚀 What Makes RecoveryIQ Different

| Differentiator | Why It Matters |
| --- | --- |
| **Action-Conditioned LightGBM V2 Probability Engine** | Evaluates recovery probability under each candidate action |
| **ERV Optimization** | Optimizes economic value instead of maximizing raw probability alone |
| **Degradation awareness** | Adds issuer, payment-method, and global context before blindly retrying |
| **Deterministic Sequential Policy Guardrails** | Keeps financial authorization outside generative AI |
| **Bounded Sequential Recovery** | Controls retries, contacts, interventions, and recovery horizon |
| **Safe Human-in-the-Loop Escalation** | Insufficient context can safely escalate to `HUMAN_REVIEW` |
| **Signed HMAC Webhook Verification** | Authenticates Razorpay Test Mode webhook provenance and exact raw-body integrity before processing. |
| **Idempotency Guardrails** | Protects execution and accounting from race conditions |
| **Exactly-Once Local Attribution** | Prevents duplicate local recovery accounting |
| **Adversarial Concurrency Verification** | Demonstrates concurrency and idempotency defenses |

---


## 🔎 Trust, Auditability & Financial Safety

RecoveryIQ does not ask judges to trust an AI decision merely because the model produced a score. It separates prediction, financial authorization, provider verification, attribution, and audit evidence, then verifies the highest-risk financial paths independently.

| Capability | What it adds | Evidence / boundary | Learn more |
|---|---|---|---|
| **Provider Truth Triangulation** | Signed webhook authenticates the event. The current Test Mode integration requires an independent Payment Link fetch before a newly triangulated paid event can become CONFIRMED; MISMATCH fails closed. | Implementation: **RAZORPAY · TEST MODE**.<br>Triangulation regression evidence: **ISOLATED LOCAL VERIFICATION**.<br>Historical ₹2 Test Mode evidence predates persisted triangulation and remains Provider Fetch: NOT CAPTURED. | [Razorpay Evidence](docs/RAZORPAY_EVIDENCE.md) |
| **Recovery Governance Profile** | Frozen Sequential Policy V2 limits exposed as inspectable governance. Distinguishes STOP, HUMAN_REVIEW, FILTER_ACTION, SCHEDULE_ACTION, and ACCOUNTING_INVARIANT. Deterministic policy retains financial authority; AI does not authorize execution. | **ISOLATED LOCAL VERIFICATION** & **SEALED · SIMULATED** | [Sequential Recovery](docs/SEQUENTIAL_RECOVERY.md) |
| **Counterfactual Action Advantage** | Compares selected action with feasible alternative actions under matched simulated hidden-world conditions. Measures action-selection headroom. | **POST-HOC · SIMULATED**. (48,405 eligible paired decisions, 43.99% selected best/tied, 52.29% counterfactual value capture). Simulator 0.3.0 does not model direct natural recovery during WAIT. | [Evaluation Results](docs/EVALUATION_RESULTS.md) |
| **Recovery Proof Record** | Deterministic read-only projection of decision, execution, provider-outcome, and attribution. The SHA-256 fingerprint changes when included canonical evidence fields change. Detecting a change requires comparison with a previously recorded fingerprint. | **ISOLATED LOCAL VERIFICATION** (It does not execute, create attribution, independently query Razorpay, provide immutable storage, or act as a digital signature). | [Architecture](docs/ARCHITECTURE.md) |
| **Critical Financial Path Gate** | Enforces 12 named financial invariants mapped to 20 unique pytest selectors (24/24 tests passed). Protects webhook authenticity, idempotency, execution reservations, outcome uniqueness, and crash ambiguity. | **ISOLATED LOCAL VERIFICATION**. (Provider crash ambiguity = PARTIALLY_PROTECTED, stale reservation sweeper = NOT_IMPLEMENTED). | [Critical Financial Path Gate](docs/CRITICAL_FINANCIAL_PATH_GATE.md) |

---

## 📚 Reviewer Deep Dives

- [Architecture](docs/ARCHITECTURE.md)
- [Evaluation Results](docs/EVALUATION_RESULTS.md)
- [Razorpay / Provider Evidence](docs/RAZORPAY_EVIDENCE.md)
- [Safety & Reliability](docs/SAFETY_AND_RELIABILITY.md)
- [Recovery Governance](docs/SEQUENTIAL_RECOVERY.md)
- [Critical Financial Path Gate](docs/CRITICAL_FINANCIAL_PATH_GATE.md)
- [Counterfactual Evaluation](docs/EVALUATION_RESULTS.md)
- [Degradation Detector](docs/DEGRADATION_DETECTION_V2.md)

---

## 🔬 The Four Evidence Lanes

RecoveryIQ separates evidence categories so simulated performance is never confused with provider execution evidence.

| Evidence Lane | Purpose | Current Proof |
| --- | --- | --- |
| **DEMO · SYNTHETIC** | Judge-facing operational opportunities | 5 cases / ₹2,75,999 at risk |
| **SEALED · SIMULATED** | Recovery-performance evaluation | 27,406 episodes / 75.97% recovery / ₹4.71 Cr+ simulated net value |
| **RAZORPAY · TEST MODE** | Provider lifecycle verification | ₹2.00 Test recovery / **No real money moved** |
| **ISOLATED LOCAL VERIFICATION** | Reliability evidence | 10-way concurrency and idempotency verification |

> These evidence lanes are intentionally isolated and must not be financially combined.

---

## 🛡️ Safety & Reliability Highlights

RecoveryIQ verifies critical financial-state invariants under concurrent and duplicate requests using **Idempotency Guardrails**.

- **10-way Webhook Race:** 10 concurrent identical webhook requests reduce to **1 logical provider event** and 9 duplicates.
- **10-way Executor Race:** 10 concurrent execution attempts result in **1 logical execution** and **1 fake-provider call**.
- **Exactly-Once Local Attribution:** Duplicate success processing creates only **1 `ExternalOutcome`** and **1 `RecoveryAttribution`** locally.
- **Bounded Policy:** Sequential Policy V2 enforces a **48-hour horizon**, maximum **3 interventions**, **2 retries**, and **2 contacts**.

### Reliability Boundary

These Idempotency Guardrails consist of provider event deduplication, durable execution reservation, database `UNIQUE` constraints, unique external outcomes, and unique recovery attribution.

The provider-accepted-but-local-process-crashes-before-persistence window is only **partially protected** through provider references and reconciliation. An automatic stale execution-reservation reaper is **not implemented**.

[Read the full Safety & Reliability evidence →](docs/SAFETY_AND_RELIABILITY.md)

---

## 💳 Razorpay Test Mode Lifecycle

RecoveryIQ includes provider-facing Test Mode verification in addition to simulated evaluation.

`Payment Failure` → `RecoveryCase` → `HUMAN_REVIEW` → `OPERATOR_INITIATED` Payment Link → mapped recovery attempt → successful Test Mode payment → signed webhook → `ExternalOutcome` → `RecoveryAttribution` → `RECOVERED`

### Why the Test Mode Case Uses Human Review

RecoveryIQ intentionally refuses to fabricate missing Model V2 history from a first provider event. When the frozen feature requirements cannot be constructed from verified Razorpay Test Mode evidence, the system safely returns `HUMAN_REVIEW / INSUFFICIENT_CONTEXT`. The operator-initiated Payment Link therefore demonstrates safe abstention, authenticated provider execution, outcome verification, and exactly-once local attribution rather than pretending that incomplete provider context supports autonomous ML execution.

Autonomous Sequential Policy V2 behavior is evaluated on complete sealed simulated trajectories; Razorpay Test Mode evidence validates the provider integration and financial-state boundaries.

### What This Proves

- **Razorpay Test Mode Integration**,
- Payment Link creation/fetch where supported,
- **Signed HMAC Webhook Verification** (raw-body HMAC SHA-256 signature verification),
- provider-event deduplication,
- order-ID correlation fallback,
- external outcome persistence,
- **Exactly-Once local outcome and recovery attribution semantics**.

**Historical recovery evidence: ₹2.00. Provider Fetch: NOT CAPTURED. No real money moved.**

[Read the complete provider evidence →](docs/RAZORPAY_EVIDENCE.md)

---

## 📡 Degradation Intelligence

RecoveryIQ includes an advisory degradation-intelligence layer for distinguishing isolated payment failures from broader simulated payment-system issues.

Detector V2 analyzes:

- **Global**
- **Issuer**
- **Payment Method**

with evidence states such as:

`HEALTHY` → `WATCH` → `CONFIRMED`

Detector V2 remains **advisory only**. It cannot authorize execution or override Sequential Policy V2.

[Read the Detector V2 design →](docs/DEGRADATION_DETECTION_V2.md)

---

## 🖥️ Product Surfaces

- **Command Center:** Headline economic and operational evidence.
- **Payment Health:** Advisory simulated degradation intelligence.
- **Recovery Queue:** Operational recovery-case review.
- **Decision Trace:** ML, ERV, policy, and explanation trace.
- **Safety Lab:** Isolated adversarial verification.
- **Batch Explorer:** Sealed portfolio cohort analysis.
- **Razorpay:** Provider Test Mode evidence.
- **Evaluation Lab:** Sealed recovery benchmark.

---

## 🧰 Technology Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite
- **Intelligence:** LightGBM V2, scikit-learn, isotonic calibration, SHAP
- **Frontend:** Next.js App Router, React, Tailwind CSS, TypeScript
- **Provider:** Razorpay Test Mode
- **LLM:** Groq explanation layer with deterministic fallback
- **Testing:** pytest, Hypothesis, concurrency verification
- **CI:** GitHub Actions

---

## 🛠️ Installation & Local Setup

### Prerequisites
Before running RecoveryIQ on a new machine, ensure you have the following installed:
- **Git** (v2.30+)
- **Node.js** (v20.0.0 or higher) for the frontend
- **Python** (v3.12+) for the backend
- **uv** package manager (`pip install uv`) for Python dependencies

### 1. Download the Repository

```bash
git clone https://github.com/rakesh-vajrapu/RecoveryIQ.git
cd RecoveryIQ
```

### 2. Environment Configuration

Create local environment files by copying the provided examples:

```bash
# Backend configuration
cp .env.example apps/api/.env

# Frontend configuration
cp .env.example apps/web/.env.local
```
Update `apps/api/.env` with your Razorpay **Test Mode** credentials and Groq API key (optional). Never commit secrets.

### 3. Backend Setup

```bash
cd apps/api
uv sync --dev --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8000 --reload
```

### 4. Frontend Setup

In a new terminal window:
```bash
cd apps/web
npm ci
npm run dev
```

The Command Center will be available at `http://localhost:3000`.

---

## 🧪 Verification

The current release passes GitHub Actions across:

- ✅ **Simulator quality**
- ✅ **Backend quality**
- ✅ **Frontend quality**

### Backend

```bash
cd apps/api
uv run ruff check .
uv run mypy app tests
uv run pytest
```

Current backend suite: **97 tests passed**.

### Frontend

```bash
cd apps/web
npm run lint
npm run typecheck
npm run build
```

---

## ⚠️ Scope & Limitations

- Razorpay integration is **Test Mode only**; no real money is moved.
- The sealed 27,406-episode benchmark and associated monetary values are **simulated**.
- Demo Synthetic opportunities are not provider revenue.
- Payment Health evidence is simulated and Detector V2 is advisory only.
- Safety Lab concurrency verification uses a fake provider and isolated local database.
- Persistence: SQLite via SQLAlchemy 2 and Alembic.
- Automatic stale execution-reservation cleanup is not implemented.
- Some actions remain recommendation-only or internal scheduling.
- The LLM is strictly explanation-only.
- No production deployment is claimed.
- Simulated values such as ₹4.71 Cr+ must not be interpreted as Razorpay revenue.

---


## License

MIT
