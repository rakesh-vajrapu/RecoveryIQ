export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export type HealthResponse = { service: string; status: "healthy"; environment: string; database: "sqlite" | "postgresql" | "other"; gemini_enabled: boolean; celery_eager: boolean };
export type RecoveryCaseSummary = { id: string; status: string; correlation_id: string; amount_minor: number; currency: string; source: string; synthetic: boolean; failure_type: string; payment_method: string; decision_kind: string | null; decision_reason: string | null; verified_recovery_minor: number; verified_recovery_at: string | null; created_at: string; last_activity_at: string };
export type DecisionRecord = { id: string; kind: string; selected_action: string | null; reason: string; model_version: string; policy_version: string; feature_schema_version: string; context_metadata: Record<string, unknown> };
export type ExecutionPlan = { id: string; action: string; capability: string; initiator: string; rationale: string };
export type ExternalExecution = { id: string; action: string; execution_mode: string; state: string; amount_minor: number; currency: string; payment_link_status: string | null; provider_url: string | null; failure_category: string | null; failure_reason: string | null };
export type ExternalOutcome = { id: string; status: string; verified: boolean; amount_minor: number; currency: string; occurred_at: string; created_at: string };
export type RecoveryAttribution = { execution_mode: string; amount_minor: number; currency: string; occurred_at: string; created_at: string; attribution_source: string };
export type RecoveryCaseDetail = { id: string; status: string; correlation_id: string; amount_minor: number; currency: string; subscription_status: string; source: string; synthetic: boolean; failure_type: string; payment_method: string; failure_description: string | null; decisions: DecisionRecord[]; plans: ExecutionPlan[]; executions: ExternalExecution[]; outcomes: ExternalOutcome[]; attribution: RecoveryAttribution | null };
export type AuditEvent = { id: string; created_at: string; actor: string; event_type: string; entity_type: string; event_metadata: Record<string, unknown> };
export type RazorpayStatus = { integration_version: string; execution_environment: string; provider_mode: "test"; api_configured: boolean; webhook_configured: boolean; live_mode_available: false; capabilities: Record<string, string> };
export type DecisionExplanation = { summary: string; factors: string[]; confidence: number; limitations: string[] };

export type CaseProof = { status: string; amount_minor: number; currency: string; created_at: string; recovered_at: string | null };
export type DecisionProof = { decision_id: string; decision_kind: string; selected_action: string | null; provenance_status: string; model_version: string | null; policy_version: string | null; policy_config_hash: string | null; decision_recorded_at: string };
export type AuthorizationProof = { initiator: string; provider_capability: string; execution_mode: string; autonomous: boolean };
export type ExecutionProof = { execution_id: string; provider: string; provider_entity_type: string; provider_entity_reference: string; execution_status: string; created_at: string };
export type ProviderEvidenceProof = { webhook_received: boolean; webhook_signature_verified: boolean; provider_event_id: string | null; provider_confirmation_status: string; provider_confirmation_method: string | null; provider_confirmed_at: string | null; amount_verified: boolean | null; currency_verified: boolean | null; reference_verified: boolean | null };
export type OutcomeProof = { external_outcome_id: string; provider_payment_reference: string | null; outcome: string; recorded_at: string };
export type AttributionProof = { attribution_id: string; attributed: boolean; amount_minor: number; currency: string; recorded_at: string; local_semantics: string };
export type IntegrityProof = { canonicalization_version: string; algorithm: string; fingerprint: string };

export type RecoveryProofRecord = {
  proof_version: string;
  case_id: string;
  evidence_lane: string;
  case: CaseProof;
  decision?: DecisionProof;
  authorization?: AuthorizationProof;
  execution?: ExecutionProof;
  provider_evidence?: ProviderEvidenceProof;
  outcome?: OutcomeProof;
  attribution?: AttributionProof;
  integrity: IntegrityProof;
  proof_completeness: string;
};

export type StrategyEvaluation = { id: string; name: string; recovered_count: number; recovery_rate: number; simulated_net_value_minor: number; contacts: number; retries: number; human_reviews: number; policy_violations: number };
export type EvaluationSummary = { evidence_type: string; evaluation_name: string; episodes: number; recoveryiq: StrategyEvaluation; primary_baseline: StrategyEvaluation; incremental: { recovery_rate_pp: number; simulated_net_value_minor: number }; strategies: StrategyEvaluation[] };

export type CohortItem = { value: string; episodes: number; recovery_rate: number; top_sequence?: string; top_sequence_share?: number; unique_sequences?: number };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type BatchExplorerData = any;

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); this.name = "ApiError"; }
}

const statusMessages: Record<number, string> = { 400: "The request was rejected because it was invalid.", 401: "This request is not authenticated.", 403: "This operation is not permitted.", 404: "The requested recovery record was not found.", 409: "The operation conflicts with the current recovery state.", 500: "The service encountered an internal error.", 503: "This integration is not currently available." };

async function request(path: string, init: RequestInit = {}): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store", ...init, headers: { Accept: "application/json", ...init.headers } });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") throw err;
    throw new ApiError(0, "The RecoveryIQ API is unavailable. Check the backend and try again.");
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
  if (!Array.isArray(payload) || !payload.every(isRecoveryCaseSummary)) throw invalidData("recovery case list");
  return payload;
}
export async function getRecoveryCase(id: string, signal?: AbortSignal): Promise<RecoveryCaseDetail> {
  const payload = await request(`/api/recovery-cases/${encodeURIComponent(id)}`, { signal });
  if (!isRecoveryCaseDetail(payload)) throw invalidData("recovery case detail");
  return payload;
}
export async function getRecoveryProof(id: string, signal?: AbortSignal): Promise<RecoveryProofRecord> {
  const payload = await request(`/api/recovery-cases/${encodeURIComponent(id)}/proof`, { signal });
  if (!isRecord(payload) || typeof payload.proof_version !== "string") throw invalidData("recovery proof record");
  return payload as RecoveryProofRecord;
}
export async function getSimulatedDecisionExample(signal?: AbortSignal): Promise<RecoveryCaseDetail> {
  const payload = await request("/api/evaluation/simulated-decision-example", { signal });
  if (!isRecoveryCaseDetail(payload)) throw invalidData("simulated decision example");
  return payload;
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getPaymentHealthSummary(signal?: AbortSignal): Promise<any> {
  const payload = await request("/api/payment-health/summary", { signal });
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
export async function getEvaluationSummary(signal?: AbortSignal): Promise<EvaluationSummary> {
  const payload = await request(`/api/evaluation/summary`, { signal });
  if (!isEvaluationSummary(payload)) throw invalidData("evaluation summary");
  return payload;
}
export async function getBatchExplorerData(signal?: AbortSignal): Promise<BatchExplorerData> {
  const payload = await request(`/api/evaluation/batch-explorer`, { signal });
  return payload;
}
export function errorMessage(error: unknown): string { return error instanceof Error ? error.message : "An unexpected error occurred."; }
function invalidData(label: string): ApiError { return new ApiError(0, `The API returned invalid ${label} data.`); }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function hasCoreCase(value: unknown): value is Record<string, unknown> { return isRecord(value) && typeof value.id === "string" && typeof value.status === "string" && typeof value.correlation_id === "string" && typeof value.amount_minor === "number" && typeof value.currency === "string"; }
function hasEvidenceFields(value: Record<string, unknown>): boolean { return typeof value.source === "string" && typeof value.synthetic === "boolean" && typeof value.failure_type === "string" && typeof value.payment_method === "string"; }
function isRecoveryCaseSummary(value: unknown): value is RecoveryCaseSummary { return hasCoreCase(value) && hasEvidenceFields(value) && (typeof value.decision_kind === "string" || value.decision_kind === null) && (typeof value.decision_reason === "string" || value.decision_reason === null) && typeof value.verified_recovery_minor === "number" && (typeof value.verified_recovery_at === "string" || value.verified_recovery_at === null) && typeof value.created_at === "string" && typeof value.last_activity_at === "string"; }
function isDecision(value: unknown): value is DecisionRecord { return isRecord(value) && typeof value.id === "string" && typeof value.kind === "string" && (typeof value.selected_action === "string" || value.selected_action === null) && typeof value.reason === "string" && isRecord(value.context_metadata); }
function isPlan(value: unknown): value is ExecutionPlan { return isRecord(value) && typeof value.id === "string" && typeof value.action === "string" && typeof value.capability === "string" && typeof value.rationale === "string"; }
function isExternalExecution(value: unknown): value is ExternalExecution { return isRecord(value) && typeof value.id === "string" && typeof value.action === "string" && typeof value.execution_mode === "string" && typeof value.state === "string" && typeof value.amount_minor === "number" && typeof value.currency === "string" && (typeof value.provider_url === "string" || value.provider_url === null); }
function isOutcome(value: unknown): value is ExternalOutcome { return isRecord(value) && typeof value.id === "string" && typeof value.status === "string" && typeof value.verified === "boolean" && typeof value.amount_minor === "number" && typeof value.occurred_at === "string" && typeof value.created_at === "string"; }
function isAttribution(value: unknown): value is RecoveryAttribution { return isRecord(value) && typeof value.amount_minor === "number" && typeof value.occurred_at === "string" && typeof value.created_at === "string" && typeof value.attribution_source === "string"; }
function isRecoveryCaseDetail(value: unknown): value is RecoveryCaseDetail { return hasCoreCase(value) && hasEvidenceFields(value) && (typeof value.failure_description === "string" || value.failure_description === null) && typeof value.subscription_status === "string" && Array.isArray(value.decisions) && value.decisions.every(isDecision) && Array.isArray(value.plans) && value.plans.every(isPlan) && Array.isArray(value.executions) && value.executions.every(isExternalExecution) && Array.isArray(value.outcomes) && value.outcomes.every(isOutcome) && (value.attribution === null || isAttribution(value.attribution)); }
function isAuditEvent(value: unknown): value is AuditEvent { return isRecord(value) && typeof value.id === "string" && typeof value.created_at === "string" && typeof value.actor === "string" && typeof value.event_type === "string" && typeof value.entity_type === "string" && isRecord(value.event_metadata); }
function isDecisionExplanation(value: unknown): value is DecisionExplanation { return isRecord(value) && typeof value.summary === "string" && Array.isArray(value.factors) && value.factors.every((item) => typeof item === "string") && typeof value.confidence === "number" && value.confidence >= 0 && value.confidence <= 1 && Array.isArray(value.limitations) && value.limitations.every((item) => typeof item === "string"); }
function isStrategyEvaluation(value: unknown): value is StrategyEvaluation { return isRecord(value) && typeof value.id === "string" && typeof value.name === "string" && typeof value.recovered_count === "number" && typeof value.recovery_rate === "number" && typeof value.simulated_net_value_minor === "number" && typeof value.contacts === "number" && typeof value.retries === "number" && typeof value.human_reviews === "number" && typeof value.policy_violations === "number"; }
function isEvaluationSummary(value: unknown): value is EvaluationSummary { return isRecord(value) && typeof value.evidence_type === "string" && typeof value.evaluation_name === "string" && typeof value.episodes === "number" && isStrategyEvaluation(value.recoveryiq) && isStrategyEvaluation(value.primary_baseline) && isRecord(value.incremental) && typeof value.incremental.recovery_rate_pp === "number" && typeof value.incremental.simulated_net_value_minor === "number" && Array.isArray(value.strategies) && value.strategies.every(isStrategyEvaluation); }

export type RazorpayEvidence = {
  evidence_type: string;
  no_real_money: boolean;
  all_time_recovered_minor: number;
  last_7_days_recovered_minor: number;
  selected_case: {
    case_id: string;
    status: string;
    amount_minor: number;
    currency: string;
    decision: string | null;
    decision_reason: string | null;
    execution_initiator: string;
    executions: Array<{
      id: string;
      action: string;
      state: string;
      provider_url: string | null;
      payment_link_status: string | null;
      created_at: string;
    }>;
    outcomes: Array<{
      id: string;
      status: string;
      verified: boolean;
      amount_minor: number;
      created_at: string;
    }>;
    attribution: {
      id: string;
      amount_minor: number;
      attribution_source: string;
      created_at: string;
    } | null;
    webhooks: Array<{
      id: string;
      event_type: string;
      provider_event_id: string;
      processing_state: string;
      created_at: string;
    }>;
    failed_attempts: Array<{
      event_type: string;
      provider_event_id: string;
      created_at: string;
    }>;
    provider_truth?: {
      webhook_authenticated: boolean;
      webhook_invariants_verified: boolean;
      provider_confirmation_status: string;
      provider_confirmation_method: string;
      provider_confirmed_at: string | null;
      external_outcome_count: number;
      recovery_attribution_count: number;
      recovered_transition_count: number;
    };
  } | null;
};

export async function getRazorpayEvidence(signal?: AbortSignal): Promise<RazorpayEvidence> {
  const data = await request("/api/integrations/razorpay/evidence", { signal });
  return data as RazorpayEvidence;
}

export type GovernanceLimits = {
  recovery_horizon_hours: number;
  max_autonomous_interventions: number;
  max_retries: number;
  max_contacts: number;
  minimum_retry_interval_hours: number;
};

export type GovernanceRule = {
  id: string;
  category: "AUTONOMY_BOUND" | "CUSTOMER_PROTECTION" | "ACTION_FEASIBILITY" | "EVIDENCE_GATE" | "ECONOMIC_STOP" | "ACCOUNTING_SAFETY";
  effect: string;
  enforcement: "STOP" | "HUMAN_REVIEW" | "FILTER_ACTION" | "SCHEDULE_ACTION" | "ACCOUNTING_INVARIANT";
  episode_termination: "YES" | "NO" | "CONDITIONAL";
};

export type GovernanceAuthority = {
  model: string;
  erv: string;
  policy: string;
  provider: string;
  llm: string;
};

export type GovernanceProfile = {
  profile_name: string;
  policy_version: string;
  model_version: string;
  config_hash: string;
  evidence_lane: string;
  limits: GovernanceLimits;
  rules: GovernanceRule[];
  authority: GovernanceAuthority;
};

export async function getGovernanceProfile(signal?: AbortSignal): Promise<GovernanceProfile> {
  const data = await request("/api/governance/profile", { signal });
  return data as GovernanceProfile;
}

export type ActionAdvantageDiagnostic = {
  artifact_type: string;
  limitations: string[];
  metrics: {
    total_decisions: number;
    eligible_paired_decisions: number;
    mean_feasible_alternatives: number;
    factual_recoveries: number;
    counterfactual_recoveries: number;
    selected_total_realized_net_value: number;
    best_feasible_total_realized_net_value: number;
    regret_minor: number;
    best_count: number;
    tied_count: number;
    suboptimal_count: number;
    advantage_vs_second_best_minor: number;
    counterfactual_value_capture: number | null;
    factual_recovery_rate: number;
    best_counterfactual_recovery_rate: number;
    mean_regret_minor: number;
    fraction_best: number;
    fraction_tied: number;
    fraction_suboptimal: number;
    mean_advantage_vs_second_best_minor: number;
  };
  breakdown: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    action: Record<string, any>;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    failure_reason: Record<string, any>;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    payment_method: Record<string, any>;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    decision_index: Record<string, any>;
  };
};

export async function getActionAdvantageDiagnostic(signal?: AbortSignal): Promise<ActionAdvantageDiagnostic> {
  const data = await request("/api/evaluation/action-advantage", { signal });
  return data as ActionAdvantageDiagnostic;
}
