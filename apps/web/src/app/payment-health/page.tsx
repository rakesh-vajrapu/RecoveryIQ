"use client";

import { Activity, AlertTriangle, HeartPulse, RefreshCw, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";

import { RecoveryDonut } from "@/components/charts";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getRecoveryCases } from "@/lib/api";
import { formatMoney, shortId } from "@/lib/format";

const terminalStates = new Set(["RECOVERED", "FAILED", "STOPPED"]);

export default function PaymentHealthPage() {
  const load = useCallback((signal: AbortSignal) => getRecoveryCases(signal), []);
  const resource = useApiResource(load);
  const cases = resource.data ?? [];
  const recovered = cases.filter((item) => item.status === "RECOVERED");
  const active = cases.filter((item) => !terminalStates.has(item.status));
  const terminal = cases.filter((item) => item.status === "FAILED" || item.status === "STOPPED");
  const exposed = active.reduce((sum, item) => sum + item.amount_minor, 0);

  return (
    <>
      <PageHeader eyebrow="Advisory monitoring" title="Payment health without hidden authority." description="A live operational snapshot derived from recovery-case state. Detector signals are advisory and can never trigger execution or override policy." icon={HeartPulse} actions={<Button variant="outline" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} />Refresh</Button>} />
      {resource.loading && <LoadingPanel />}
      {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
      {resource.data && <div className="space-y-5">
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Observed failures" value={String(cases.length)} detail="Current recovery opportunities" icon={AlertTriangle} tone="rose" progress={100} />
          <MetricCard label="Active exposure" value={formatMoney(exposed)} detail="Value not yet terminal" icon={Activity} tone="amber" progress={cases.length ? active.length / cases.length * 100 : 0} />
          <MetricCard label="Recovered" value={String(recovered.length)} detail="Provider-verified outcomes" icon={HeartPulse} tone="emerald" progress={cases.length ? recovered.length / cases.length * 100 : 0} />
          <MetricCard label="Policy overrides" value="0" detail="Detector remains advisory" icon={ShieldCheck} tone="violet" progress={0} />
        </section>
        <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.55fr)_minmax(0,1.45fr)]">
          <RecoveryDonut recovered={recovered.length} active={active.length} terminal={terminal.length} />
          <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between"><div><p className="eyebrow">Needs attention</p><h2 className="mt-2 text-lg font-semibold">Non-terminal recovery cases</h2></div><span className="rounded-full border bg-amber-500/10 px-3 py-1 text-[10px] font-bold tracking-[0.1em] text-amber-700 uppercase dark:text-amber-300">Advisory only</span></div>{active.length === 0 ? <div className="mt-5"><EmptyPanel title="No active exposure" description="Every recorded case is currently in a terminal state." /></div> : <div className="mt-5 divide-y overflow-hidden rounded-xl border">{active.map((item) => <Link key={item.id} href={`/recovery-cases/${item.id}`} className="flex flex-wrap items-center gap-3 bg-card/40 px-4 py-3.5 transition-colors hover:bg-muted/45"><div><p className="font-mono text-xs font-semibold">Case {shortId(item.id)}</p><p className="mt-1 text-[10px] text-muted-foreground">Reference {shortId(item.correlation_id, 12)}</p></div><StatusBadge status={item.status} className="ml-auto" /><p className="w-full text-right text-xs font-semibold sm:w-auto">{formatMoney(item.amount_minor, item.currency)}</p></Link>)}</div>}</article>
        </section>
        <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/[0.055] p-5 text-sm leading-6 text-cyan-900 dark:text-cyan-100"><strong>Authority boundary:</strong> this page summarizes observable operational state. Detector V2 failed its hard-policy safety gate and therefore cannot select actions, change probabilities, or execute recovery.</div>
      </div>}
    </>
  );
}

