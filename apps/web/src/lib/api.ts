export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type HealthResponse = { service: string; status: "healthy"; environment: string; database: "sqlite" | "postgresql" | "other"; gemini_enabled: boolean; celery_eager: boolean };
export type RecoveryCaseSummary = { id: string; status: string; correlation_id: string; amount_minor: number; currency: string; created_at: string; last_activity_at: string };
export type DecisionRecord = { id: string; kind: string; selected_action: string | null; reason: string; model_version: string; policy_version: string; feature_schema_version: string; context_metadata: Record<string, unknown> };
export type ExecutionPlan = { id: string; action: string; capability: string; initiator: string; rationale: string };
export type ExternalExecution = { id: string; action: string; execution_mode: string; state: string; amount_minor: number; currency: string; payment_link_status: string | null; provider_url: string | null; failure_category: string | null; failure_reason: string | null };
export type ExternalOutcome = { id: string; status: string; verified: boolean; amount_minor: number; currency: string; occurred_at: string; created_at: string };
export type RecoveryAttribution = { execution_mode: string; amount_minor: number; currency: string; occurred_at: string; created_at: string; attribution_source: string };
export type RecoveryCaseDetail = { id: string; status: string; correlation_id: string; amount_minor: number; currency: string; subscription_status: string; decisions: DecisionRecord[]; plans: ExecutionPlan[]; executions: ExternalExecution[]; outcomes: ExternalOutcome[]; attribution: RecoveryAttribution | null };
export type AuditEvent = { id: string; created_at: string; actor: string; event_type: string; entity_type: string; event_metadata: Record<string, unknown> };
export type RazorpayStatus = { integration_version: string; execution_environment: string; provider_mode: "test"; api_configured: boolean; webhook_configured: boolean; live_mode_available: false; capabilities: Record<string, string> };
export type DecisionExplanation = { summary: string; factors: string[]; confidence: number; limitations: string[] };

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); this.name = "ApiError"; }
}

const statusMessages: Record<number, string> = { 400: "The request was rejected because it was invalid.", 401: "This request is not authenticated.", 403: "This operation is not permitted.", 404: "The requested recovery record was not found.", 409: "The operation conflicts with the current recovery state.", 500: "The service encountered an internal error.", 503: "This integration is not currently available." };

async function request(path: string, init: RequestInit = {}): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store", ...init, headers: { Accept: "application/json", ...init.headers } });
  } catch {
    throw new ApiError(0, "The RecoverIQ API is unavailable. Check the backend and try again.");
  }
  let payload: unknown = null;
  try { payload = await response.json(); } catch { if (response.ok) throw new ApiError(response.status, "The API returned an invalid response."); }
  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : null;
    throw new ApiError(response.status, detail ?? statusMessages[response.status] ?? `Request failed with HTTP ${response.status}.`);
  }
  return payload;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const payload = await request("/health", { signal });
  if (!isRecord(payload) || payload.status !== "healthy" || typeof payload.service !== "string") throw invalidData("health");
  return payload as HealthResponse;
}
export async function getRecoveryCases(signal?: AbortSignal): Promise<RecoveryCaseSummary[]> {
  const payload = await request("/api/recovery-cases", { signal });
  if (!Array.isArray(payload) || !payload.every(isRecoveryCaseSummary)) throw invalidData("recovery cases");
  return payload;
}
export async function getRecoveryCase(id: string, signal?: AbortSignal): Promise<RecoveryCaseDetail> {
  const payload = await request(`/api/recovery-cases/${encodeURIComponent(id)}`, { signal });
  if (!isRecoveryCaseDetail(payload)) throw invalidData("recovery case detail");
  return payload;
}
export async function getRecoveryCaseAudit(id: string, signal?: AbortSignal): Promise<AuditEvent[]> {
  const payload = await request(`/api/recovery-cases/${encodeURIComponent(id)}/audit`, { signal });
  if (!Array.isArray(payload) || !payload.every(isAuditEvent)) throw invalidData("audit trail");
  return payload;
}
export async function getRazorpayStatus(signal?: AbortSignal): Promise<RazorpayStatus> {
  const payload = await request("/api/integrations/razorpay/status", { signal });
  if (!isRecord(payload) || payload.provider_mode !== "test" || payload.live_mode_available !== false) throw invalidData("Razorpay status");
  return payload as RazorpayStatus;
}
export async function createTestPaymentLink(id: string): Promise<ExternalExecution> {
  const payload = await request(`/api/recovery-cases/${encodeURIComponent(id)}/test-payment-link`, { method: "POST" });
  if (!isExternalExecution(payload)) throw invalidData("Payment Link execution");
  return payload;
}
export async function getCaseExplanation(id: string): Promise<DecisionExplanation> {
  const payload = await request(`/api/recovery-cases/${encodeURIComponent(id)}/explanation`, { method: "POST" });
  if (!isDecisionExplanation(payload)) throw invalidData("decision explanation");
  return payload;
}
export function errorMessage(error: unknown): string { return error instanceof Error ? error.message : "An unexpected error occurred."; }
function invalidData(label: string): ApiError { return new ApiError(0, `The API returned invalid ${label} data.`); }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function hasCoreCase(value: unknown): value is Record<string, unknown> { return isRecord(value) && typeof value.id === "string" && typeof value.status === "string" && typeof value.correlation_id === "string" && typeof value.amount_minor === "number" && typeof value.currency === "string"; }
function isRecoveryCaseSummary(value: unknown): value is RecoveryCaseSummary { return hasCoreCase(value) && typeof value.created_at === "string" && typeof value.last_activity_at === "string"; }
function isDecision(value: unknown): value is DecisionRecord { return isRecord(value) && typeof value.id === "string" && typeof value.kind === "string" && (typeof value.selected_action === "string" || value.selected_action === null) && typeof value.reason === "string" && isRecord(value.context_metadata); }
function isPlan(value: unknown): value is ExecutionPlan { return isRecord(value) && typeof value.id === "string" && typeof value.action === "string" && typeof value.capability === "string" && typeof value.rationale === "string"; }
function isExternalExecution(value: unknown): value is ExternalExecution { return isRecord(value) && typeof value.id === "string" && typeof value.action === "string" && typeof value.execution_mode === "string" && typeof value.state === "string" && typeof value.amount_minor === "number" && typeof value.currency === "string" && (typeof value.provider_url === "string" || value.provider_url === null); }
function isOutcome(value: unknown): value is ExternalOutcome { return isRecord(value) && typeof value.id === "string" && typeof value.status === "string" && typeof value.verified === "boolean" && typeof value.amount_minor === "number" && typeof value.occurred_at === "string" && typeof value.created_at === "string"; }
function isAttribution(value: unknown): value is RecoveryAttribution { return isRecord(value) && typeof value.amount_minor === "number" && typeof value.occurred_at === "string" && typeof value.created_at === "string" && typeof value.attribution_source === "string"; }
function isRecoveryCaseDetail(value: unknown): value is RecoveryCaseDetail { return hasCoreCase(value) && typeof value.subscription_status === "string" && Array.isArray(value.decisions) && value.decisions.every(isDecision) && Array.isArray(value.plans) && value.plans.every(isPlan) && Array.isArray(value.executions) && value.executions.every(isExternalExecution) && Array.isArray(value.outcomes) && value.outcomes.every(isOutcome) && (value.attribution === null || isAttribution(value.attribution)); }
function isAuditEvent(value: unknown): value is AuditEvent { return isRecord(value) && typeof value.id === "string" && typeof value.created_at === "string" && typeof value.actor === "string" && typeof value.event_type === "string" && typeof value.entity_type === "string" && isRecord(value.event_metadata); }
function isDecisionExplanation(value: unknown): value is DecisionExplanation { return isRecord(value) && typeof value.summary === "string" && Array.isArray(value.factors) && value.factors.every((item) => typeof item === "string") && typeof value.confidence === "number" && value.confidence >= 0 && value.confidence <= 1 && Array.isArray(value.limitations) && value.limitations.every((item) => typeof item === "string"); }
