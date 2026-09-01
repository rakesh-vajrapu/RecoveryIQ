"use client";

import { ArrowLeft, ArrowRight, Ban, Bot, BrainCircuit, CheckCircle2, CircleDollarSign, ExternalLink, FileClock, Link2, LoaderCircle, LockKeyhole, RefreshCw, ShieldCheck, Sparkles, X, ShieldAlert, BarChart3, DatabaseZap, Activity, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { createTestPaymentLink, errorMessage, getCaseExplanation, getRecoveryCase, type DecisionExplanation, type ExternalExecution, type RecoveryCaseDetail } from "@/lib/api";
import { formatDate, formatMoney, shortId, titleCase } from "@/lib/format";

export function RecoveryCaseDetailView({ id, simulatedCase }: { id?: string; simulatedCase?: RecoveryCaseDetail }) {
  const load = useCallback(async (signal: AbortSignal) => {
    if (simulatedCase) return simulatedCase;
    if (id) return getRecoveryCase(id, signal);
    throw new Error("No ID or simulated case provided");
  }, [id, simulatedCase]);
  
  const resource = useApiResource(load);
  
  return (
    <>
      <PageHeader 
        eyebrow="Decision Intelligence" 
        title={resource.data ? `Case ${shortId(resource.data.id, 12)}` : "Recovery case detail"} 
        description="Inspect the predicted recovery probability, action alternatives, economic value, and deterministic policy." 
        icon={BrainCircuit} 
        actions={
          <>
            {!simulatedCase && <Button variant="outline" nativeButton={false} render={<Link href="/recovery-cases" />}><ArrowLeft className="size-4" />Queue</Button>}
            {resource.data && !simulatedCase && <Button variant="outline" nativeButton={false} render={<Link href={`/recovery-cases/${resource.data.id}/audit`} />}><FileClock className="size-4" />Audit timeline</Button>}
            {!simulatedCase && <Button variant="ghost" onClick={resource.retry} disabled={resource.loading} aria-label="Refresh case"><RefreshCw className={resource.loading ? "animate-spin" : ""} /></Button>}
          </>
        } 
      />
      {resource.loading && <LoadingPanel label="Loading decision intelligence" />}
      {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
      {resource.data && <CaseContent recoveryCase={resource.data} onRefresh={resource.retry} isSimulated={!!simulatedCase} />}
    </>
  );
}

function CaseContent({ recoveryCase, onRefresh, isSimulated }: { recoveryCase: RecoveryCaseDetail; onRefresh: () => void; isSimulated: boolean }) {
  const latestDecision = recoveryCase.decisions.at(-1) ?? null;
  const latestOutcome = recoveryCase.outcomes.at(-1) ?? null;
  
  const meta = latestDecision?.context_metadata || {};
  const missingRequirements = Array.isArray(meta.missing_requirements) ? meta.missing_requirements : [];
  const observableFields = meta.observable_context || meta.observable_fields || {};
  const candidates = Array.isArray(meta.candidates) ? meta.candidates : [];
  const policyChecks = (meta.policy_checks || {}) as Record<string, string>;
  const isHumanReview = latestDecision?.reason === "INSUFFICIENT_CONTEXT" || recoveryCase.status === "HUMAN_REVIEW";
  
  return (
    <div className="space-y-8">
      {/* SECTION A: CASE SUMMARY */}
      <EvidenceBanner recoveryCase={recoveryCase} isSimulated={isSimulated} />
      
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Recovery state" value={<StatusBadge status={recoveryCase.status} />} detail={titleCase(recoveryCase.status)} icon={ShieldCheck} />
        <SummaryCard label="Amount at risk" value={formatMoney(recoveryCase.amount_minor, recoveryCase.currency)} detail={`${recoveryCase.currency} · minor-unit safe`} icon={CircleDollarSign} />
        <SummaryCard label="Payment method" value={titleCase(recoveryCase.payment_method)} detail={recoveryCase.failure_type ? titleCase(recoveryCase.failure_type) : "Unknown failure"} icon={Activity} />
        <SummaryCard label="Reference" value={shortId(recoveryCase.correlation_id, 12)} detail="Anonymous correlation ID" icon={LockKeyhole} mono />
      </section>

      {/* AUTHORITY BOUNDARY PANEL */}
      <div className="mb-6 flex overflow-x-auto rounded-xl border border-violet-500/20 bg-violet-500/[0.05] px-5 py-4 text-[10px] font-bold tracking-widest text-muted-foreground uppercase shadow-sm">
        <div className="flex items-center gap-4 whitespace-nowrap" title="ML predicts · Policy decides · Razorpay verifies · AI explains">
          <span className="flex items-center gap-2"><BarChart3 className="size-3.5 text-blue-400" /> <span className="text-blue-400">MODEL PREDICTS</span></span>
          <ArrowRight className="size-3 text-muted-foreground/30" />
          <span className="flex items-center gap-2"><ShieldCheck className="size-3.5 text-violet-400" /> <span className="text-violet-400">POLICY DECIDES</span></span>
          <ArrowRight className="size-3 text-muted-foreground/30" />
          <span className="flex items-center gap-2"><DatabaseZap className="size-3.5 text-emerald-400" /> <span className="text-emerald-400">RAZORPAY VERIFIES</span></span>
          <ArrowRight className="size-3 text-muted-foreground/30" />
          <span className="flex items-center gap-2"><Bot className="size-3.5 text-cyan-400" /> <span className="text-cyan-400">AI EXPLAINS</span></span>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        {/* SECTION B: EVIDENCE */}
        <article className="surface-panel rounded-2xl p-5 sm:p-6">
          <div className="flex items-start justify-between">
            <div><p className="eyebrow">Available Evidence</p><h2 className="mt-2 text-lg font-semibold">Context provided to model</h2></div>
            <DatabaseZap className="size-5 text-amber-500" />
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <InfoDatum label="Failure type" value={titleCase(recoveryCase.failure_type)} />
            <InfoDatum label="Payment method" value={titleCase(recoveryCase.payment_method)} />
            <InfoDatum label="Subscription state" value={titleCase(recoveryCase.subscription_status)} />
            {Object.entries(observableFields).slice(0, 4).map(([k, v]) => (
                <InfoDatum key={k} label={k.replace(/_/g, " ")} value={String(v)} />
            ))}
          </div>
        </article>

        {/* SECTION C & E: AUTONOMY GATE / HUMAN REVIEW */}
        {isHumanReview ? (
          <article className="surface-panel rounded-2xl p-5 sm:p-6 border border-amber-500/30 bg-amber-500/[0.05]">
            <div className="flex items-start justify-between">
              <div><p className="eyebrow text-amber-500">Autonomy Gate</p><h2 className="mt-2 text-lg font-semibold text-amber-500">HUMAN REVIEW</h2></div>
              <ShieldAlert className="size-5 text-amber-500" />
            </div>
            <p className="mt-4 text-sm leading-6 text-foreground">
              <strong>Reason: INSUFFICIENT CONTEXT.</strong><br/>
              RecoveryIQ did not fabricate a recovery probability or execute an unsupported financial action. 
              The frozen ML feature contract cannot be completed from the evidence without inventing history.
            </p>
            {missingRequirements.length > 0 && (
                <div className="mt-4 p-4 rounded-xl border bg-amber-500/10">
                  <p className="text-xs font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wider mb-2">Unsatisfied requirements:</p>
                  <ul className="list-disc list-inside text-xs space-y-1 text-amber-700/80 dark:text-amber-300/80">
                    {missingRequirements.map((req: string) => (
                        <li key={req}>{titleCase(req.replace(/_/g, " "))}</li>
                    ))}
                  </ul>
                </div>
            )}
          </article>
        ) : (
          <article className="surface-panel rounded-2xl p-5 sm:p-6">
            <div className="flex items-start justify-between">
              <div><p className="eyebrow">Deterministic decision</p><h2 className="mt-2 text-lg font-semibold">Policy trace</h2></div>
              <ShieldCheck className="size-5 text-violet-500" />
            </div>
            {!latestDecision ? (
              <div className="mt-5"><EmptyPanel title="No decision record" description="This case does not contain a persisted model or policy decision." /></div>
            ) : (
              <div className="mt-5 space-y-5">
                <div className="grid gap-3 sm:grid-cols-2">
                  <InfoDatum label="Selected action" value={latestDecision.selected_action ? titleCase(latestDecision.selected_action) : titleCase(latestDecision.kind)} />
                  <InfoDatum label="Decision reason" value={titleCase(latestDecision.reason)} />
                  <InfoDatum label="Model version" value={latestDecision.model_version} mono />
                  <InfoDatum label="Policy version" value={latestDecision.policy_version} mono />
                </div>
                {policyChecks.reason && (
                  <div className="mt-2 text-xs p-3 rounded-lg bg-violet-500/10 text-violet-300 border border-violet-500/20">
                    <span className="font-semibold uppercase tracking-wider">Policy Enforcement: </span> 
                    {policyChecks.reason.replace(/_/g, " ")}
                  </div>
                )}
              </div>
            )}
          </article>
        )}
      </div>

      {/* SECTION D: ECONOMIC VALUE & ACTION ALTERNATIVES */}
      {!isHumanReview && candidates.length > 0 && (
        <section className="space-y-5">
          <div className="surface-panel rounded-2xl p-5 sm:p-6">
            <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-4">
              <CircleDollarSign className="size-5 text-emerald-400" />
              <h2 className="text-lg font-semibold">Economic Decision Alternatives</h2>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-white/70">
                <thead className="bg-white/5 text-white/50 font-medium text-xs uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Action Candidate</th>
                    <th className="px-4 py-3">Capability</th>
                    <th className="px-4 py-3 text-right">Probability</th>
                    <th className="px-4 py-3 text-right">Est. Cost</th>
                    <th className="px-4 py-3 text-right">ERV</th>
                    <th className="px-4 py-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {candidates.map((cand: { label: string; probability: number; incremental_erv_minor: number; supported: boolean }) => {
                    const isSelected = latestDecision?.selected_action === cand.label;
                    const expectedRecovery = cand.probability * recoveryCase.amount_minor;
                    const cost = expectedRecovery - cand.incremental_erv_minor;
                    
                    return (
                      <tr key={cand.label} className={`hover:bg-white/[0.02] transition-colors ${isSelected ? "bg-emerald-500/10 text-white" : ""}`}>
                        <td className="px-4 py-3 font-medium flex items-center gap-2">
                          {titleCase(cand.label.replace(/_/g, " "))}
                          {isSelected && <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold bg-emerald-500/20 text-emerald-400">Selected</span>}
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                          {cand.label.includes("PAYMENT_LINK") ? (isSimulated ? "SUPPORTED IN RAZORPAY TEST MODE" : "RAZORPAY TEST EXECUTION") : cand.label.includes("WAIT") ? "SIMULATION ONLY" : "INTERNAL POLICY ACTION"}
                        </td>
                        <td className="px-4 py-3 text-right">{(cand.probability * 100).toFixed(1)}%</td>
                        <td className="px-4 py-3 text-right text-red-400/80">{cost > 0 ? `₹${(cost/100).toFixed(2)}` : "—"}</td>
                        <td className="px-4 py-3 text-right text-emerald-400/90 font-medium">₹{(cand.incremental_erv_minor/100).toFixed(2)}</td>
                        <td className="px-4 py-3 text-center">
                          {isSelected ? (
                            <span className="text-emerald-400 font-semibold text-xs">SELECTED</span>
                          ) : cand.supported ? (
                            <span className="text-muted-foreground text-xs">REJECTED (Lower ERV)</span>
                          ) : (
                            <span className="text-red-400/70 text-xs">BLOCKED</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-6 p-4 rounded-xl border bg-white/5 border-white/10 space-y-3">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">Why Selected?</span>
                <p className="mt-1 text-sm leading-relaxed">
                  {latestDecision?.selected_action 
                    ? `${titleCase(latestDecision.selected_action.replace(/_/g, " "))} had the highest positive policy-compliant Expected Recovery Value (ERV) among feasible actions.`
                    : "No action selected."}
                </p>
              </div>
              <div className="border-t border-white/10 pt-3">
                <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Raw Recovery vs Economic Value</span>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground/90">
                  RecoveryIQ does NOT simply choose the highest probability action. It chooses the highest economically justified action after deducting incremental intervention and friction costs.
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* SECTION F: EXECUTION / OUTCOME */}
      {!isSimulated && (
        <section className="grid gap-5 xl:grid-cols-2">
          <article className="surface-panel rounded-2xl p-5 sm:p-6">
            <div className="flex items-start justify-between"><div><p className="eyebrow">Execution boundary</p><h2 className="mt-2 text-lg font-semibold">Plans and external execution</h2></div><Link2 className="size-5 text-primary" /></div>
            <div className="mt-5 space-y-3">
              {recoveryCase.plans.length === 0 && recoveryCase.executions.length === 0 ? <EmptyPanel title="No execution planned" description="The policy or an operator has not created an execution plan for this case." /> : 
                <>
                  {recoveryCase.plans.map((plan) => <div key={plan.id} className="rounded-xl border bg-card/50 p-4"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold">{titleCase(plan.action)}</p><span className="rounded-full bg-muted px-2 py-1 text-[9px] font-bold tracking-wider text-muted-foreground uppercase">{titleCase(plan.initiator)}</span></div><p className="mt-2 text-xs leading-5 text-muted-foreground">{plan.rationale}</p><p className="mt-2 font-mono text-[10px] text-primary">{titleCase(plan.capability)}</p></div>)}
                  {recoveryCase.executions.map((execution) => <ExecutionRow key={execution.id} execution={execution} />)}
                </>
              }
            </div>
          </article>

          <article className="surface-panel rounded-2xl p-5 sm:p-6">
            <div className="flex items-start justify-between"><div><p className="eyebrow">Provider outcome</p><h2 className="mt-2 text-lg font-semibold">Verified payment result</h2></div>{latestOutcome?.verified ? <CheckCircle2 className="size-5 text-emerald-500" /> : <AlertTriangle className="size-5 text-muted-foreground" />}</div>
            {latestOutcome ? (
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <InfoDatum label="Outcome" value={titleCase(latestOutcome.status)} />
                <InfoDatum label="Verified" value={latestOutcome.verified ? "Yes · provider event" : "No"} />
                <InfoDatum label="Amount" value={formatMoney(latestOutcome.amount_minor, latestOutcome.currency)} />
                <InfoDatum label="Payment completed" value={formatDate(latestOutcome.occurred_at)} />
              </div>
            ) : (
              <div className="mt-5"><EmptyPanel title="No verified outcome" description="Only an authenticated provider event can create an external outcome." /></div>
            )}
            
            <div className="mt-6 border-t border-white/5 pt-6">
               <h3 className="mb-4 text-sm font-semibold">Recovery Attribution</h3>
               {recoveryCase.attribution ? (
                 <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.065] p-5">
                   <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">{formatMoney(recoveryCase.attribution.amount_minor, recoveryCase.attribution.currency)}</p>
                   <p className="mt-2 text-xs text-emerald-800/75 dark:text-emerald-200/70">{titleCase(recoveryCase.attribution.attribution_source)} · Recorded {formatDate(recoveryCase.attribution.created_at)}</p>
                   <div className="mt-4 flex items-center gap-2 border-t border-emerald-500/15 pt-4 text-[10px] font-bold tracking-[0.1em] text-emerald-700 uppercase dark:text-emerald-300">
                     <CheckCircle2 className="size-3.5" />Recorded exactly once
                   </div>
                 </div>
               ) : (
                 <EmptyPanel title="No recovery attribution" description="Attribution appears only after a matching, verified payment outcome." />
               )}
            </div>
          </article>
        </section>
      )}

      {/* Payment Link Card for non-simulated cases */}
      {!isSimulated && (
        <section className="grid gap-5 xl:grid-cols-2">
          {recoveryCase.synthetic ? <SyntheticExecutionBoundaryCard /> : <PaymentLinkCard recoveryCase={recoveryCase} onCreated={onRefresh} />}
        </section>
      )}

      <ExplanationCard caseId={recoveryCase.id} hasDecision={Boolean(latestDecision)} isSimulated={isSimulated} />
    </div>
  );
}

function EvidenceBanner({ recoveryCase, isSimulated }: { recoveryCase: RecoveryCaseDetail; isSimulated?: boolean }) {
  if (isSimulated) return <section className="rounded-2xl border border-violet-500/25 bg-violet-500/[0.07] p-5"><div className="flex flex-wrap items-center gap-3"><span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-[10px] font-bold tracking-wider text-violet-700 uppercase dark:text-violet-300">Simulated</span><h2 className="text-sm font-bold">Sealed Simulated Decision Example</h2></div><p className="mt-3 text-xs leading-5 text-muted-foreground">This is NOT an operational RecoveryCase and NOT Razorpay evidence. It is a frozen artifact used to illustrate the economic decision intelligence of the model.</p></section>;
  if (recoveryCase.synthetic) return <section className="rounded-2xl border border-cyan-500/25 bg-cyan-500/[0.07] p-5"><div className="flex flex-wrap items-center gap-3"><span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-[10px] font-bold tracking-wider text-cyan-700 uppercase dark:text-cyan-300">Demo · Synthetic</span><h2 className="text-sm font-bold">Synthetic Demo Opportunity</h2></div><p className="mt-3 text-xs leading-5 text-muted-foreground">Presentation-only revenue-risk evidence. It is not a Razorpay transaction, has no fabricated provider event, and is never counted as provider-verified recovery.</p></section>;
  if (recoveryCase.source === "RAZORPAY_TEST_MODE") return <section className="rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.07] p-5"><div className="flex flex-wrap items-center gap-3"><span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[10px] font-bold tracking-wider text-emerald-700 uppercase dark:text-emerald-300">Razorpay · Test Mode</span><h2 className="text-sm font-bold">Provider-backed test evidence</h2></div><p className="mt-3 text-xs leading-5 text-muted-foreground">Authenticated Test Mode evidence only. No real money moved.</p></section>;
  return <section className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.07] p-5"><div className="flex flex-wrap items-center gap-3"><span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-[10px] font-bold tracking-wider text-amber-700 uppercase dark:text-amber-300">Local · Unverified</span><h2 className="text-sm font-bold">Local evidence only</h2></div><p className="mt-3 text-xs leading-5 text-muted-foreground">No authenticated Razorpay provider lifecycle is attached, so this case is not counted as provider-verified recovery.</p></section>;
}

function SyntheticExecutionBoundaryCard() {
  return <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between"><div><p className="eyebrow">Execution boundary</p><h2 className="mt-2 text-lg font-semibold">Provider actions disabled</h2></div><Ban className="size-5 text-cyan-600 dark:text-cyan-300" /></div><p className="mt-5 text-xs leading-5 text-muted-foreground">Synthetic demo opportunities can show risk, evidence, safe abstention, and auditability. They cannot create Razorpay Payment Links, provider outcomes, or recovery attribution.</p><div className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/[0.055] p-4 text-[11px] font-semibold text-cyan-800 dark:text-cyan-200">No provider side effect is available for this source.</div></article>;
}

function SummaryCard({ label, value, detail, icon: Icon, mono = false }: { label: string; value: React.ReactNode; detail: string; icon: typeof ShieldCheck; mono?: boolean }) {
  return <article className="surface-panel interactive-panel rounded-2xl p-5"><div className="flex items-start justify-between"><p className="eyebrow">{label}</p><Icon className="size-4 text-primary" /></div><div className={`mt-4 text-lg font-semibold ${mono ? "font-mono text-sm" : ""}`}>{value}</div><p className="mt-2 text-[11px] text-muted-foreground">{detail}</p></article>;
}

function InfoDatum({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="rounded-xl border bg-card/50 p-3.5"><p className="text-[10px] font-bold tracking-[0.1em] text-muted-foreground uppercase">{label}</p><p className={`mt-2 break-words text-xs font-semibold ${mono ? "font-mono" : ""}`}>{value}</p></div>;
}

function ExecutionRow({ execution }: { execution: ExternalExecution }) {
  return <div className="rounded-xl border bg-[var(--surface-soft)] p-4"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold">External execution</p><StatusBadge status={execution.state} /><span className="ml-auto font-mono text-[10px] text-muted-foreground">{execution.execution_mode}</span></div><div className="mt-3 grid gap-2 sm:grid-cols-2"><InfoDatum label="Action" value={titleCase(execution.action)} /><InfoDatum label="Link status" value={execution.payment_link_status ? titleCase(execution.payment_link_status) : "Not issued"} /></div>{execution.failure_reason && <p className="mt-3 text-xs text-destructive">{execution.failure_reason}</p>}</div>;
}

function ExplanationCard({ caseId, hasDecision, isSimulated }: { caseId: string; hasDecision: boolean; isSimulated?: boolean }) {
  const [explanation, setExplanation] = useState<DecisionExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const explain = async () => {
    if (loading || explanation || isSimulated) return;
    setLoading(true); setError(null);
    try { setExplanation(await getCaseExplanation(caseId)); } catch (reason) { setError(errorMessage(reason)); } finally { setLoading(false); }
  };
  return <article className="surface-panel rounded-2xl p-5 sm:p-6 mt-5"><div className="flex items-start justify-between gap-3"><div><p className="eyebrow text-cyan-500">LLM EXPLANATION</p><h2 className="mt-2 text-lg font-semibold">AI Assistant</h2></div><span className="grid size-10 place-items-center rounded-xl bg-cyan-500/10 text-cyan-700 dark:text-cyan-300"><Bot className="size-4.5" /></span></div><div className="mt-4 flex items-start gap-2 rounded-xl border border-cyan-500/20 bg-cyan-500/[0.055] p-3 text-[11px] leading-5 text-cyan-900 dark:text-cyan-100"><ShieldCheck className="mt-0.5 size-3.5 shrink-0" /><p><strong>Explanation only.</strong> AI cannot select actions, change policy, execute Razorpay, or mark recovery.</p></div>{!explanation && <div className="mt-5"><p className="text-xs leading-5 text-muted-foreground">{hasDecision && !isSimulated ? "Generate a structured explanation from the persisted decision and outcome evidence." : isSimulated ? "AI explanation is not available for simulated sealed artifacts." : "This case has no model decision; the explanation will state only the available case, execution, and outcome evidence."}</p><Button onClick={explain} disabled={loading || isSimulated} className="mt-4 w-full">{loading ? <LoaderCircle className="animate-spin" /> : <Sparkles />} {loading ? "Explaining supplied evidence…" : "Explain this case"}</Button>{error && <div className="mt-3 rounded-xl bg-destructive/10 p-3 text-xs text-destructive" role="alert">{error}<Button variant="ghost" size="xs" className="ml-2" onClick={() => { setError(null); void explain(); }}>Retry</Button></div>}</div>}{explanation && <div className="mt-5 space-y-4"><p className="text-sm leading-6">{explanation.summary}</p><div><p className="mb-2 text-[10px] font-bold tracking-[0.1em] text-muted-foreground uppercase">Factors</p><ul className="space-y-2">{explanation.factors.map((factor) => <li key={factor} className="flex gap-2 text-xs leading-5 text-muted-foreground"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" />{factor}</li>)}</ul></div><div><div className="mb-2 flex justify-between text-[10px] font-semibold text-muted-foreground"><span>Explanation fidelity</span><span>{Math.round(explanation.confidence * 100)}%</span></div><div className="h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-cyan-500" style={{ width: `${explanation.confidence * 100}%` }} /></div></div><div className="rounded-xl border bg-muted/35 p-3"><p className="text-[10px] font-bold tracking-[0.1em] text-muted-foreground uppercase">Limitations</p>{explanation.limitations.map((item) => <p key={item} className="mt-2 text-[11px] leading-5 text-muted-foreground">{item}</p>)}</div></div>}</article>;
}

function PaymentLinkCard({ recoveryCase, onCreated }: { recoveryCase: RecoveryCaseDetail; onCreated: () => void }) {
  const existing = recoveryCase.executions.find((item) => item.provider_url) ?? recoveryCase.executions.at(-1) ?? null;
  const [execution, setExecution] = useState<ExternalExecution | null>(existing);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const createLink = async () => {
    if (submitting || execution?.provider_url) return;
    setSubmitting(true); setError(null);
    try { const created = await createTestPaymentLink(recoveryCase.id); setExecution(created); setConfirmOpen(false); onCreated(); } catch (reason) { setError(errorMessage(reason)); } finally { setSubmitting(false); }
  };
  return <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between"><div><p className="eyebrow">Safe recovery action</p><h2 className="mt-2 text-lg font-semibold">Razorpay Payment Link</h2></div><span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1 text-[10px] font-bold tracking-wider text-amber-700 uppercase dark:text-amber-300">Test only</span></div>{execution ? <div className="mt-5 rounded-2xl border bg-card/55 p-4"><div className="flex flex-wrap items-center gap-2"><StatusBadge status={execution.payment_link_status ?? execution.state} /><span className="font-mono text-[10px] text-muted-foreground">{execution.execution_mode}</span></div><dl className="mt-4 grid gap-3 sm:grid-cols-2"><InfoDatum label="Reference" value={shortId(recoveryCase.correlation_id, 14)} mono /><InfoDatum label="Amount" value={formatMoney(execution.amount_minor, execution.currency)} /></dl>{execution.provider_url ? <Button className="mt-4 w-full" nativeButton={false} render={<a href={execution.provider_url} target="_blank" rel="noreferrer" />}><ExternalLink className="size-4" />Open Test Payment Link</Button> : <p className="mt-4 rounded-xl bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">The provider URL is not available. Current execution state: {titleCase(execution.state)}.</p>}</div> : <div className="mt-5"><p className="text-xs leading-5 text-muted-foreground">Create one non-partial INR Payment Link through the existing idempotent execution path. Repeated requests cannot create a second link for the same case.</p><Button className="mt-4 w-full" onClick={() => setConfirmOpen(true)}><Link2 className="size-4" />Create Test Payment Link</Button></div>}{error && <p className="mt-3 rounded-xl bg-destructive/10 p-3 text-xs text-destructive" role="alert">{error}</p>}{confirmOpen && <div className="fixed inset-0 z-[80] grid place-items-center bg-slate-950/55 p-4 backdrop-blur-sm" role="presentation"><div role="dialog" aria-modal="true" aria-labelledby="payment-link-title" className="surface-panel w-full max-w-lg rounded-3xl p-6 shadow-2xl sm:p-7"><div className="flex items-start justify-between"><div><p className="eyebrow text-amber-600 dark:text-amber-300">Test Mode confirmation</p><h2 id="payment-link-title" className="mt-2 text-xl font-bold">Create a Razorpay Test Payment Link?</h2></div><button type="button" aria-label="Close confirmation" onClick={() => setConfirmOpen(false)} disabled={submitting} className="focus-ring grid size-9 place-items-center rounded-xl text-muted-foreground hover:bg-muted"><X className="size-4" /></button></div><div className="mt-5 rounded-2xl border border-amber-500/20 bg-amber-500/[0.06] p-4 text-sm leading-6"><strong>No live money.</strong> This invokes the existing Razorpay Test Mode integration for {formatMoney(recoveryCase.amount_minor, recoveryCase.currency)} and reference {shortId(recoveryCase.correlation_id, 14)}.</div><ul className="mt-5 space-y-2 text-xs text-muted-foreground"><li>• Non-partial payment</li><li>• Backend idempotency prevents double creation</li><li>• Provider outcome still requires a signed webhook</li></ul>{error && <p className="mt-4 rounded-xl bg-destructive/10 p-3 text-xs text-destructive">{error}</p>}<div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={submitting}>Cancel</Button><Button onClick={() => void createLink()} disabled={submitting}>{submitting ? <LoaderCircle className="animate-spin" /> : <Link2 />}{submitting ? "Creating once…" : "Confirm Test Link"}</Button></div></div></div>}</article>;
}
