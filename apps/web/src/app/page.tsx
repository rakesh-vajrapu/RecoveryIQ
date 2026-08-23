"use client";

import { Activity, ArrowRight, CircleDollarSign, Clock3, CreditCard, RefreshCw, ShieldCheck, Target, TriangleAlert, WalletCards } from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";

import { RecoveryDonut, RecoveryTrendChart } from "@/components/charts";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getHealth, getRazorpayStatus, getRecoveryCases, type HealthResponse, type RazorpayStatus, type RecoveryCaseSummary } from "@/lib/api";
import { formatDate, formatMoney, shortId } from "@/lib/format";

type DashboardData = { health: HealthResponse; integration: RazorpayStatus; cases: RecoveryCaseSummary[] };
const terminalStates = new Set(["RECOVERED", "FAILED", "STOPPED"]);

export default function CommandCenterPage() {
  const load = useCallback(async (signal: AbortSignal): Promise<DashboardData> => {
    const [health, integration, cases] = await Promise.all([getHealth(signal), getRazorpayStatus(signal), getRecoveryCases(signal)]);
    return { health, integration, cases };
  }, []);
  const resource = useApiResource(load);

  return (
    <>
      <PageHeader eyebrow="Recovery command center" title="Revenue recovery, with every boundary visible." description="Monitor current opportunities, verified outcomes, execution readiness, and the deterministic controls that keep recovery safe." icon={Activity} actions={<Button variant="outline" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} />Refresh data</Button>} />
      {resource.loading && <LoadingPanel label="Loading the recovery command center" />}
      {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
      {resource.data && <DashboardContent data={resource.data} />}
    </>
  );
}
function DashboardContent({ data }: { data: DashboardData }) {
  const recovered = data.cases.filter((item) => item.status === "RECOVERED");
  const active = data.cases.filter((item) => !terminalStates.has(item.status));
  const terminal = data.cases.filter((item) => item.status === "FAILED" || item.status === "STOPPED");
  const recoveredValue = recovered.reduce((sum, item) => sum + item.amount_minor, 0);
  const successRate = data.cases.length ? (recovered.length / data.cases.length) * 100 : 0;
  const latest = data.cases.slice(0, 5);

  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <MetricCard label="Opportunities" value={String(data.cases.length)} detail="Persisted recovery cases" icon={Target} tone="cyan" progress={100} />
        <MetricCard label="Recovered revenue" value={formatMoney(recoveredValue)} detail="Verified attributed value" icon={CircleDollarSign} tone="emerald" progress={successRate} />
        <MetricCard label="Active cases" value={String(active.length)} detail="Still inside recovery flow" icon={Activity} tone="blue" progress={data.cases.length ? (active.length / data.cases.length) * 100 : 0} />
        <MetricCard label="Success rate" value={`${successRate.toFixed(1)}%`} detail="Recovered / opportunities" icon={WalletCards} tone="violet" progress={successRate} />
        <MetricCard label="Payment failures" value={String(data.cases.length)} detail="Each case begins with failure" icon={TriangleAlert} tone="rose" progress={100} />
        <MetricCard label="Pending actions" value={String(active.length)} detail="Active or review states" icon={Clock3} tone="amber" progress={data.cases.length ? (active.length / data.cases.length) * 100 : 0} />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
        <RecoveryTrendChart cases={data.cases} />
        <RecoveryDonut recovered={recovered.length} active={active.length} terminal={terminal.length} />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <article className="surface-panel overflow-hidden rounded-2xl">
          <div className="flex items-center justify-between border-b px-5 py-4 sm:px-6"><div><p className="eyebrow">Latest activity</p><h2 className="mt-1.5 text-base font-semibold">Recovery queue</h2></div><Link href="/recovery-cases" className="focus-ring group flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-semibold text-primary">View all<ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" /></Link></div>
          {latest.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">No recovery cases have been recorded.</p> : <div className="divide-y">{latest.map((item) => <Link key={item.id} href={`/recovery-cases/${item.id}`} className="group grid gap-3 px-5 py-4 transition-colors hover:bg-muted/45 sm:grid-cols-[1fr_auto_auto] sm:items-center sm:px-6"><div className="min-w-0"><p className="truncate font-mono text-xs font-semibold">Case {shortId(item.id)}</p><p className="mt-1 truncate text-[11px] text-muted-foreground">Ref {shortId(item.correlation_id, 12)} · {formatDate(item.created_at)}</p></div><StatusBadge status={item.status} /><p className="text-sm font-semibold sm:text-right">{formatMoney(item.amount_minor, item.currency)}</p></Link>)}</div>}
        </article>

        <article className="surface-panel rounded-2xl p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3"><div><p className="eyebrow">Control plane</p><h2 className="mt-2 text-base font-semibold">Environment readiness</h2></div><ShieldCheck className="size-5 text-primary" /></div>
          <dl className="mt-6 space-y-3">
            <ReadinessRow label="Backend API" value={data.health.status === "healthy" ? "Healthy" : data.health.status} ok={data.health.status === "healthy"} />
            <ReadinessRow label="Database" value={data.health.database} ok />
            <ReadinessRow label="Razorpay mode" value={data.integration.provider_mode.toUpperCase()} ok={data.integration.provider_mode === "test"} />
            <ReadinessRow label="Webhook" value={data.integration.webhook_configured ? "Configured" : "Missing"} ok={data.integration.webhook_configured} />
            <ReadinessRow label="Live Mode" value="Unavailable" ok />
          </dl>
          <Link href="/integrations/razorpay" className="focus-ring mt-5 flex items-center justify-between rounded-xl border bg-[var(--surface-soft)] px-4 py-3 text-xs font-semibold transition-all hover:border-primary/30 hover:text-primary"><span className="flex items-center gap-2"><CreditCard className="size-4" />Inspect integration</span><ArrowRight className="size-3.5" /></Link>
        </article>
      </section>
    </div>
  );
}

function ReadinessRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return <div className="flex items-center gap-3 rounded-xl border bg-card/50 px-3.5 py-3"><span className={`size-2 rounded-full ${ok ? "bg-emerald-500 shadow-[0_0_9px_rgb(16_185_129_/_0.45)]" : "bg-amber-500"}`} /><dt className="text-xs text-muted-foreground">{label}</dt><dd className="ml-auto font-mono text-[11px] font-semibold uppercase">{value}</dd></div>;
}
