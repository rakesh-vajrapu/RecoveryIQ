# Deployment

[Back to README](../README.md)

---

## Architecture Overview

```
Push to main
  → GitHub CI (Simulator + Backend + Frontend quality gates)
  → Only successful CI triggers Azure deployment
  → GitHub OIDC login → Azure App Service deployment
  → Post-deploy /health verification
  → Post-deploy Replay API verification
```

**Frontend:** Next.js on Vercel (automatic Vercel deployment on push).

**Backend:** FastAPI on Microsoft Azure App Service (deployed via GitHub Actions after CI passes).

---

## GitHub CI Pipeline

The CI workflow (`ci.yml`) runs on every push to `main` and on pull requests. It consists of three independent quality gates:

### 1. Simulator Quality
- Ruff lint
- mypy type checking across all simulator packages
- Full pytest suite

### 2. Backend Quality
- Ruff lint
- mypy type checking (`app` and `tests`)
- **Critical Financial Path Gate** (`scripts/run_critical_financial_gate.py`) — verifies 12 named financial invariants
- Full pytest suite

### 3. Frontend Quality
- ESLint
- TypeScript type checking
- Production build verification

All three gates must pass before the Azure deployment workflow is triggered.

---

## Azure App Service Deployment

The deployment workflow (`main_recoveryiq-api-rakesh-2026.yml`) is triggered only when:

1. The CI workflow completes **successfully** on the `main` branch, **or**
2. A manual `workflow_dispatch` is invoked.

### Authentication

Azure authentication uses **GitHub OIDC (OpenID Connect)** with a managed identity scoped to the App Service. This means:

- No publish-profile or Basic Auth credentials are stored in GitHub.
- Basic authentication remains **disabled** on the App Service.
- The deployment identity is scoped to the specific App Service resource.
- Credentials are abstracted through GitHub repository secrets referencing Azure service principal identifiers.

### Deployment Package

The workflow constructs a minimal deployment package containing only:

- `apps/api/` (backend source)
- `artifacts/` (frozen evaluation/policy artifacts)
- `requirements/backend.txt` (Python dependencies)

The package explicitly **excludes**:

- `apps/web/` (frontend — deployed separately via Vercel)
- `simulator/` (evaluation-only)
- `ml/` (training-only)
- `.env` files (secrets — configured via Azure App Settings)

### Package Assertions

Before deployment, the workflow verifies:

- Required files exist (main.py, requirements.txt, frozen policy traces).
- Forbidden directories do not exist (web, simulator, ml, .env).

### Concurrency Suppression

```yaml
concurrency:
  group: recoveryiq-azure-production
  cancel-in-progress: true
```

If a newer verified commit is pushed while an older deployment is running, the older deployment is cancelled. This is intentional stale-deployment protection — the latest verified commit always wins.

### Post-Deploy Verification

After deployment, the workflow automatically verifies:

1. **Health check:** Polls `GET /health` up to 18 times (10-second intervals) until a `200` response is received.
2. **Replay API check:** Verifies that `GET /api/evaluation/replay/presets` returns the expected frozen policy traces (`successful-adaptive-trace-v2` and `bounded-failure-trace-v2`).

If either verification fails, the deployment is marked as failed in GitHub Actions.

---

## Database

| Environment | Database | Notes |
|---|---|---|
| Local development | SQLite | File-based, created by Alembic migrations |
| Automated tests | SQLite | In-memory isolated databases |
| Azure reviewer deployment | SQLite | Persisted under App Service local storage |

SQLAlchemy 2 models use portable types and avoid database-specific syntax. PostgreSQL is a compatible target via SQLAlchemy but has not been used or tested in the current RecoveryIQ deployment.

---

## Environment Variables

Backend configuration is managed through Azure App Service Application Settings. Required settings for Razorpay Test Mode include:

- `EXECUTION_ENVIRONMENT=RAZORPAY_TEST`
- `RAZORPAY_MODE=test`
- Razorpay Test Mode API credentials
- Razorpay webhook secret

No credentials, tenant IDs, subscription IDs, client IDs, or secret values are documented here. See the [Razorpay Test Mode Runbook](runbooks/razorpay_test_mode.md) for the judge demo configuration.

---

## Reviewer URLs

| Surface | URL |
|---|---|
| Frontend (Vercel) | https://recoveryiq-ai.vercel.app |
| Backend API (Azure) | `https://recoveryiq-api-rakesh-2026.azurewebsites.net` |
| Health check | `GET /health` |
| Razorpay webhook | `POST /webhooks/razorpay` |
