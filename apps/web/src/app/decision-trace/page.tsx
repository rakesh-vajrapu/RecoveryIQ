"use client";

import { ArrowRight, BrainCircuit, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getRecoveryCase, getRecoveryCases, type RecoveryCaseDetail } from "@/lib/api";
import { shortId, titleCase } from "@/lib/format";
import { GovernanceProfilePanel } from "@/components/ui/governance-profile";

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
      <PageHeader eyebrow="Decision intelligence" title="See why policy allowed, stopped, or escalated." description="Decision records are persisted audit evidence. Models estimate probabilities, while the deterministic policy remains the only action-selection authority." icon={BrainCircuit} actions={<Button variant="outline" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} />Refresh traces</Button>} />
      <GovernanceProfilePanel />
      <div className="mt-5">
        {resource.loading && <LoadingPanel />}
        {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
        {resource.data && traces.length === 0 && <EmptyPanel title="No persisted decision traces" description={`${resource.data.length} case${resource.data.length === 1 ? " is" : "s are"} available, but none contains a model/policy decision record. Operator-created Test Mode cases can legitimately have no decision trace.`} />}
        {traces.length > 0 && <div className="grid gap-4 xl:grid-cols-2">{traces.map(({ recoveryCase, decision }) => <article key={decision.id} className="surface-panel interactive-panel rounded-2xl p-5 sm:p-6 transition-all duration-300 hover:scale-[1.01] hover:shadow-lg hover:shadow-primary/5 hover:border-primary/20 group"><div className="flex flex-wrap items-start justify-between gap-3"><div><EvidenceBadge source={recoveryCase.source} /><p className="mt-2 font-mono text-[10px] font-semibold text-muted-foreground">Case {shortId(recoveryCase.id, 12)}</p><h2 className="mt-2 text-base font-semibold transition-colors group-hover:text-primary">{decision.selected_action ? titleCase(decision.selected_action) : titleCase(decision.kind)}</h2></div><StatusBadge status={recoveryCase.status} /></div><div className="mt-5 grid gap-3 sm:grid-cols-3"><Datum label="Kind" value={titleCase(decision.kind)} /><Datum label="Model" value={decision.model_version} /><Datum label="Policy" value={decision.policy_version} /></div><div className="mt-4 rounded-xl border bg-[var(--surface-soft)] p-4 transition-colors group-hover:border-primary/20 group-hover:bg-muted/50"><p className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">Reason</p><p className="mt-2 text-xs leading-5">{titleCase(decision.reason)}</p>{decision.reason === "INSUFFICIENT_CONTEXT" && <p className="mt-2 text-[11px] leading-5 text-muted-foreground">Safe abstention: RecoveryIQ refuses to fabricate historical or provider context merely to force an ML action.</p>}</div><Link href={`/recovery-cases/${recoveryCase.id}`} className="focus-ring mt-5 flex items-center gap-2 rounded-lg text-xs font-semibold text-primary">Open complete case<ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1 group-hover:scale-110" /></Link></article>)}</div>}
      </div>
    </>
  );
}



function EvidenceBadge({ source }: { source: string }) {
  if (source === "DEMO_SYNTHETIC") return <span className="inline-flex rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-cyan-700 uppercase dark:text-cyan-300">Demo · Synthetic</span>;
  if (source === "RAZORPAY_TEST_MODE") return <span className="inline-flex rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-emerald-700 uppercase dark:text-emerald-300">Razorpay · Test</span>;
  return <span className="inline-flex rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-amber-700 uppercase dark:text-amber-300">Local · Unverified</span>;
}

function Datum({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border bg-card/50 p-3 transition-colors hover:bg-muted/60 hover:border-primary/20"><p className="text-[9px] font-bold tracking-wider text-muted-foreground uppercase">{label}</p><p className="mt-1.5 font-mono text-[11px] font-semibold">{value}</p></div>; }
