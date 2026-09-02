"use client";

import { ArrowRight, BrainCircuit, CheckCircle2, Cpu, RefreshCw, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getRecoveryCase, getRecoveryCases, type RecoveryCaseDetail } from "@/lib/api";
import { shortId, titleCase } from "@/lib/format";

export default function DecisionTracePage() {
  const load = useCallback(async (signal: AbortSignal): Promise<RecoveryCaseDetail[]> => {
    const cases = await getRecoveryCases(signal);
    const results = await Promise.allSettled(cases.map((item) => getRecoveryCase(item.id, signal)));
    return results.flatMap((result) => result.status === "fulfilled" ? [result.value] : []);
  }, []);
  const resource = useApiResource(load);
  const traces = resource.data?.flatMap((recoveryCase) => recoveryCase.decisions.map((decision) => ({ recoveryCase, decision }))) ?? [];

  return (
    <>
      <PageHeader eyebrow="Decision intelligence" title="See why policy allowed, stopped, or escalated." description="Decision records are immutable evidence. Models estimate probabilities, while the deterministic policy remains the only action-selection authority." icon={BrainCircuit} actions={<Button variant="outline" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} />Refresh traces</Button>} />
      <BoundaryGraphic />
      <div className="mt-4 rounded-2xl border border-violet-500/20 bg-violet-500/[0.055] p-4 text-xs leading-5 text-muted-foreground"><strong className="text-foreground">Bounded stopping rules:</strong> 48-hour horizon, at most three autonomous interventions, at most two retries, at most two contacts, and immediate termination on recovery, STOP, or Human Review.</div>
      <div className="mt-5">
        {resource.loading && <LoadingPanel />}
        {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
        {resource.data && traces.length === 0 && <EmptyPanel title="No persisted decision traces" description={`${resource.data.length} case${resource.data.length === 1 ? " is" : "s are"} available, but none contains a model/policy decision record. Operator-created Test Mode cases can legitimately have no decision trace.`} />}
        {traces.length > 0 && <div className="grid gap-4 xl:grid-cols-2">{traces.map(({ recoveryCase, decision }) => <article key={decision.id} className="surface-panel interactive-panel rounded-2xl p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><EvidenceBadge source={recoveryCase.source} /><p className="mt-2 font-mono text-[10px] font-semibold text-muted-foreground">Case {shortId(recoveryCase.id, 12)}</p><h2 className="mt-2 text-base font-semibold">{decision.selected_action ? titleCase(decision.selected_action) : titleCase(decision.kind)}</h2></div><StatusBadge status={recoveryCase.status} /></div><div className="mt-5 grid gap-3 sm:grid-cols-3"><Datum label="Kind" value={titleCase(decision.kind)} /><Datum label="Model" value={decision.model_version} /><Datum label="Policy" value={decision.policy_version} /></div><div className="mt-4 rounded-xl border bg-[var(--surface-soft)] p-4"><p className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">Reason</p><p className="mt-2 text-xs leading-5">{titleCase(decision.reason)}</p>{decision.reason === "INSUFFICIENT_CONTEXT" && <p className="mt-2 text-[11px] leading-5 text-muted-foreground">Safe abstention: RecoveryIQ refuses to fabricate historical or provider context merely to force an ML action.</p>}</div><Link href={`/recovery-cases/${recoveryCase.id}`} className="focus-ring group mt-5 flex items-center gap-2 rounded-lg text-xs font-semibold text-primary">Open complete case<ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" /></Link></article>)}</div>}
      </div>
    </>
  );
}

function BoundaryGraphic() {
  const steps = [{ icon: Cpu, label: "Model", detail: "Estimates" }, { icon: Workflow, label: "ERV", detail: "Compares" }, { icon: ShieldCheck, label: "Policy", detail: "Authorizes" }, { icon: CheckCircle2, label: "Provider", detail: "Verifies" }, { icon: Sparkles, label: "AI", detail: "Explains" }];
  return <section className="surface-panel overflow-x-auto rounded-2xl p-5"><div className="flex min-w-[660px] items-center justify-between">{steps.map((step, index) => <div key={step.label} className="contents"><div className="flex min-w-24 flex-col items-center text-center"><span className={`grid size-10 place-items-center rounded-xl ${step.label === "Policy" ? "bg-primary text-primary-foreground shadow-[0_8px_24px_var(--glow-primary)]" : "border bg-card text-muted-foreground"}`}><step.icon className="size-4" /></span><p className="mt-2 text-xs font-semibold">{step.label}</p><p className="mt-1 text-[9px] tracking-wider text-muted-foreground uppercase">{step.detail}</p></div>{index < steps.length - 1 && <div className="mx-3 h-px flex-1 bg-gradient-to-r from-border via-primary/40 to-border" />}</div>)}</div></section>;
}

function EvidenceBadge({ source }: { source: string }) {
  if (source === "DEMO_SYNTHETIC") return <span className="inline-flex rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-cyan-700 uppercase dark:text-cyan-300">Demo · Synthetic</span>;
  if (source === "RAZORPAY_TEST_MODE") return <span className="inline-flex rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-emerald-700 uppercase dark:text-emerald-300">Razorpay · Test</span>;
  return <span className="inline-flex rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-amber-700 uppercase dark:text-amber-300">Local · Unverified</span>;
}

function Datum({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border bg-card/50 p-3"><p className="text-[9px] font-bold tracking-wider text-muted-foreground uppercase">{label}</p><p className="mt-1.5 font-mono text-[11px] font-semibold">{value}</p></div>; }
