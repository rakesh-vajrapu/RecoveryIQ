"use client";

import { AlertTriangle, ArrowLeft, Bot, BrainCircuit, CheckCircle2, CircleDollarSign, Clock3, ExternalLink, FileClock, Link2, LoaderCircle, LockKeyhole, RefreshCw, ShieldCheck, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { createTestPaymentLink, errorMessage, getCaseExplanation, getRecoveryCase, type DecisionExplanation, type ExternalExecution, type RecoveryCaseDetail } from "@/lib/api";
import { formatDate, formatMoney, shortId, titleCase } from "@/lib/format";

export function RecoveryCaseDetailView({ id }: { id: string }) {
  const load = useCallback((signal: AbortSignal) => getRecoveryCase(id, signal), [id]);
  const resource = useApiResource(load);
  return (
    <>
      <PageHeader eyebrow="Recovery case" title={resource.data ? `Case ${shortId(resource.data.id, 12)}` : "Recovery case detail"} description="Inspect the persisted decision, plan, provider execution, verified outcome, and exactly-once attribution for this opportunity." icon={BrainCircuit} actions={<><Button variant="outline" nativeButton={false} render={<Link href="/recovery-cases" />}><ArrowLeft className="size-4" />Queue</Button>{resource.data && <Button variant="outline" nativeButton={false} render={<Link href={`/recovery-cases/${resource.data.id}/audit`} />}><FileClock className="size-4" />Audit timeline</Button>}<Button variant="ghost" onClick={resource.retry} disabled={resource.loading} aria-label="Refresh case"><RefreshCw className={resource.loading ? "animate-spin" : ""} /></Button></>} />
      {resource.loading && <LoadingPanel label="Loading recovery case detail" />}
      {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
      {resource.data && <CaseContent recoveryCase={resource.data} onRefresh={resource.retry} />}
    </>
  );
}

function CaseContent({ recoveryCase, onRefresh }: { recoveryCase: RecoveryCaseDetail; onRefresh: () => void }) {
  const latestDecision = recoveryCase.decisions.at(-1) ?? null;
  const latestExecution = recoveryCase.executions.at(-1) ?? null;
  const latestOutcome = recoveryCase.outcomes.at(-1) ?? null;
  const confidence = latestDecision ? readConfidence(latestDecision.context_metadata) : null;
  const evidenceFactors = latestDecision ? readEvidenceFactors(latestDecision.context_metadata) : [];
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Recovery state" value={<StatusBadge status={recoveryCase.status} />} detail={titleCase(recoveryCase.status)} icon={ShieldCheck} />
        <SummaryCard label="Opportunity value" value={formatMoney(recoveryCase.amount_minor, recoveryCase.currency)} detail={`${recoveryCase.currency} · minor-unit safe`} icon={CircleDollarSign} />
        <SummaryCard label="Recovery stage" value={latestExecution?.payment_link_status ? titleCase(latestExecution.payment_link_status) : titleCase(recoveryCase.status)} detail={latestExecution ? `Execution ${titleCase(latestExecution.state)}` : "No external execution yet"} icon={Clock3} />
        <SummaryCard label="Reference" value={shortId(recoveryCase.correlation_id, 12)} detail="Anonymous correlation ID" icon={LockKeyhole} mono />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
        <article className="surface-panel rounded-2xl p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3"><div><p className="eyebrow">Deterministic decision</p><h2 className="mt-2 text-lg font-semibold">Policy trace</h2></div><span className="rounded-full border bg-violet-500/10 px-3 py-1 text-[10px] font-bold tracking-[0.1em] text-violet-700 uppercase dark:text-violet-300">Policy authority</span></div>
          {!latestDecision ? <div className="mt-5"><EmptyPanel title="No decision record" description="This operator-created Test Mode case does not contain a persisted model or policy decision." /></div> : <div className="mt-6 space-y-5"><div className="grid gap-3 sm:grid-cols-2"><InfoDatum label="Selected action" value={latestDecision.selected_action ? titleCase(latestDecision.selected_action) : titleCase(latestDecision.kind)} /><InfoDatum label="Decision reason" value={titleCase(latestDecision.reason)} /><InfoDatum label="Model version" value={latestDecision.model_version} mono /><InfoDatum label="Policy version" value={latestDecision.policy_version} mono /></div><div><div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold">Decision confidence</p><p className="font-mono text-xs text-muted-foreground">{confidence === null ? "Not recorded" : `${(confidence * 100).toFixed(1)}%`}</p></div><div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-violet-500 transition-[width] duration-700" style={{ width: `${(confidence ?? 0) * 100}%` }} /></div></div><div><p className="mb-3 text-xs font-semibold">Supplied factors</p>{evidenceFactors.length ? <ul className="grid gap-2 sm:grid-cols-2">{evidenceFactors.map((factor) => <li key={factor} className="rounded-xl border bg-card/50 px-3 py-2.5 text-xs text-muted-foreground">{factor}</li>)}</ul> : <p className="rounded-xl border border-dashed p-4 text-xs text-muted-foreground">No display-safe factor list was stored with this decision.</p>}</div></div>}
        </article>
        <ExplanationCard caseId={recoveryCase.id} hasDecision={Boolean(latestDecision)} />
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between"><div><p className="eyebrow">Execution boundary</p><h2 className="mt-2 text-lg font-semibold">Plans and external execution</h2></div><Link2 className="size-5 text-primary" /></div><div className="mt-5 space-y-3">{recoveryCase.plans.length === 0 && recoveryCase.executions.length === 0 ? <EmptyPanel title="No execution planned" description="The policy or an operator has not created an execution plan for this case." /> : <>{recoveryCase.plans.map((plan) => <div key={plan.id} className="rounded-xl border bg-card/50 p-4"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold">{titleCase(plan.action)}</p><span className="rounded-full bg-muted px-2 py-1 text-[9px] font-bold tracking-wider text-muted-foreground uppercase">{titleCase(plan.initiator)}</span></div><p className="mt-2 text-xs leading-5 text-muted-foreground">{plan.rationale}</p><p className="mt-2 font-mono text-[10px] text-primary">{titleCase(plan.capability)}</p></div>)}{recoveryCase.executions.map((execution) => <ExecutionRow key={execution.id} execution={execution} />)}</>}</div></article>
        <PaymentLinkCard recoveryCase={recoveryCase} onCreated={onRefresh} />
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between"><div><p className="eyebrow">Provider outcome</p><h2 className="mt-2 text-lg font-semibold">Verified payment result</h2></div>{latestOutcome?.verified ? <CheckCircle2 className="size-5 text-emerald-500" /> : <AlertTriangle className="size-5 text-muted-foreground" />}</div>{latestOutcome ? <div className="mt-5 grid gap-3 sm:grid-cols-2"><InfoDatum label="Outcome" value={titleCase(latestOutcome.status)} /><InfoDatum label="Verified" value={latestOutcome.verified ? "Yes · provider event" : "No"} /><InfoDatum label="Amount" value={formatMoney(latestOutcome.amount_minor, latestOutcome.currency)} /><InfoDatum label="Payment completed" value={formatDate(latestOutcome.occurred_at)} /><InfoDatum label="Outcome verified" value={formatDate(latestOutcome.created_at)} /></div> : <div className="mt-5"><EmptyPanel title="No verified outcome" description="Only an authenticated provider event can create an external outcome." /></div>}</article>
        <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between"><div><p className="eyebrow">Exactly-once attribution</p><h2 className="mt-2 text-lg font-semibold">Recovered revenue</h2></div><CircleDollarSign className="size-5 text-primary" /></div>{recoveryCase.attribution ? <div className="mt-5 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.065] p-5"><p className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">{formatMoney(recoveryCase.attribution.amount_minor, recoveryCase.attribution.currency)}</p><p className="mt-2 text-xs text-emerald-800/75 dark:text-emerald-200/70">{titleCase(recoveryCase.attribution.attribution_source)} · Recorded {formatDate(recoveryCase.attribution.created_at)}</p><div className="mt-4 flex items-center gap-2 border-t border-emerald-500/15 pt-4 text-[10px] font-bold tracking-[0.1em] text-emerald-700 uppercase dark:text-emerald-300"><CheckCircle2 className="size-3.5" />Recorded exactly once</div></div> : <div className="mt-5"><EmptyPanel title="No recovery attribution" description="Attribution appears only after a matching, verified payment outcome." /></div>}</article>
      </section>
    </div>
  );
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

function ExplanationCard({ caseId, hasDecision }: { caseId: string; hasDecision: boolean }) {
  const [explanation, setExplanation] = useState<DecisionExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const explain = async () => {
    if (loading || explanation) return;
    setLoading(true); setError(null);
    try { setExplanation(await getCaseExplanation(caseId)); } catch (reason) { setError(errorMessage(reason)); } finally { setLoading(false); }
  };
  return <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between gap-3"><div><p className="eyebrow">Why this decision?</p><h2 className="mt-2 text-lg font-semibold">AI explanation</h2></div><span className="grid size-10 place-items-center rounded-xl bg-cyan-500/10 text-cyan-700 dark:text-cyan-300"><Bot className="size-4.5" /></span></div><div className="mt-4 flex items-start gap-2 rounded-xl border border-cyan-500/20 bg-cyan-500/[0.055] p-3 text-[11px] leading-5 text-cyan-900 dark:text-cyan-100"><ShieldCheck className="mt-0.5 size-3.5 shrink-0" /><p><strong>Explanation only.</strong> AI cannot select actions, change policy, execute Razorpay, or mark recovery.</p></div>{!explanation && <div className="mt-5"><p className="text-xs leading-5 text-muted-foreground">{hasDecision ? "Generate a structured explanation from the persisted decision and outcome evidence." : "This case has no model decision; the explanation will state only the available case, execution, and outcome evidence."}</p><Button onClick={explain} disabled={loading} className="mt-4 w-full">{loading ? <LoaderCircle className="animate-spin" /> : <Sparkles />} {loading ? "Explaining supplied evidence…" : "Explain this case"}</Button>{error && <div className="mt-3 rounded-xl bg-destructive/10 p-3 text-xs text-destructive" role="alert">{error}<Button variant="ghost" size="xs" className="ml-2" onClick={() => { setError(null); void explain(); }}>Retry</Button></div>}</div>}{explanation && <div className="mt-5 space-y-4"><p className="text-sm leading-6">{explanation.summary}</p><div><p className="mb-2 text-[10px] font-bold tracking-[0.1em] text-muted-foreground uppercase">Factors</p><ul className="space-y-2">{explanation.factors.map((factor) => <li key={factor} className="flex gap-2 text-xs leading-5 text-muted-foreground"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" />{factor}</li>)}</ul></div><div><div className="mb-2 flex justify-between text-[10px] font-semibold text-muted-foreground"><span>Explanation fidelity</span><span>{Math.round(explanation.confidence * 100)}%</span></div><div className="h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-cyan-500" style={{ width: `${explanation.confidence * 100}%` }} /></div></div><div className="rounded-xl border bg-muted/35 p-3"><p className="text-[10px] font-bold tracking-[0.1em] text-muted-foreground uppercase">Limitations</p>{explanation.limitations.map((item) => <p key={item} className="mt-2 text-[11px] leading-5 text-muted-foreground">{item}</p>)}</div></div>}</article>;
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

function readConfidence(metadata: Record<string, unknown>): number | null {
  for (const key of ["recovery_probability", "selected_action_probability", "confidence"]) { const value = metadata[key]; if (typeof value === "number" && value >= 0 && value <= 1) return value; }
  return null;
}

function readEvidenceFactors(metadata: Record<string, unknown>): string[] {
  const factors = metadata.key_factors;
  if (Array.isArray(factors)) return factors.filter((item): item is string => typeof item === "string").slice(0, 6);
  const allowed = ["failure_reason", "policy_result", "candidate_action", "alternative_action"];
  return allowed.flatMap((key) => typeof metadata[key] === "string" ? [`${titleCase(key)}: ${titleCase(metadata[key])}`] : []);
}
