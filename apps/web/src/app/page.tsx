"use client";

import { Activity, ArrowRight, Beaker, CircleDollarSign, CreditCard, RefreshCw, ShieldAlert, ShieldCheck, Target } from "lucide-react";
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
      <PageHeader eyebrow="Recovery command center" title="RecoveryIQ: Autonomous Revenue Recovery Control Plane" description="Detect revenue at risk, select the highest-value safe intervention, execute bounded recovery, and verify the outcome." icon={Activity} actions={<Button variant="outline" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} />Refresh data</Button>} />
      
      {/* Control Loop Visual */}
      <div className="mb-6 flex overflow-x-auto rounded-xl border bg-card/50 px-5 py-3 text-[10px] font-bold tracking-widest text-muted-foreground uppercase">
        <div className="flex items-center gap-3 whitespace-nowrap" title="ML predicts · Policy decides · Razorpay verifies · AI explains">
          <span className="text-foreground">Detect</span><ArrowRight className="size-3 text-muted-foreground/50" />
          <span className="text-foreground">Predict</span><ArrowRight className="size-3 text-muted-foreground/50" />
          <span className="text-foreground">Decide</span><ArrowRight className="size-3 text-muted-foreground/50" />
          <span className="text-primary">Execute</span><ArrowRight className="size-3 text-primary/50" />
          <span className="text-emerald-600 dark:text-emerald-400">Verify</span><ArrowRight className="size-3 text-emerald-600/50 dark:text-emerald-400/50" />
          <span className="text-emerald-600 dark:text-emerald-400">Attribute</span>
        </div>
      </div>

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
  const demoActive = active.filter((item) => item.source === "DEMO_SYNTHETIC");
  const revenueAtRisk = demoActive.reduce((sum, item) => sum + item.amount_minor, 0);
  const verifiedRecovery = data.cases.reduce((sum, item) => sum + item.verified_recovery_minor, 0);
  
  // Actual relevant Human Review count for the operational demo context (not batch 35)
  const operationalReviews = demoActive.filter((item) => item.status === "HUMAN_REVIEW").length;
  const latest = [...data.cases].sort((left, right) => new Date(right.last_activity_at).getTime() - new Date(left.last_activity_at).getTime()).slice(0, 5);

  return (
    <div className="space-y-5">
      {/* Evidence Provenance Strip */}
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="flex items-center gap-3 rounded-xl border border-cyan-500/20 bg-cyan-500/[0.05] p-3"><span className="rounded bg-cyan-500/20 px-1.5 py-0.5 text-[9px] font-bold text-cyan-700 dark:text-cyan-300">DEMO</span><p className="text-[10px] font-medium text-muted-foreground">Synthetic operational scenario</p></div>
        <div className="flex items-center gap-3 rounded-xl border border-violet-500/20 bg-violet-500/[0.05] p-3"><span className="rounded bg-violet-500/20 px-1.5 py-0.5 text-[9px] font-bold text-violet-700 dark:text-violet-300">SIMULATED</span><p className="text-[10px] font-medium text-muted-foreground">Frozen batch evaluation</p></div>
        <div className="flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.05] p-3"><span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700 dark:text-emerald-300">RAZORPAY TEST</span><p className="text-[10px] font-medium text-muted-foreground">Provider-verified Test Mode</p></div>
      </section>

      {/* Row 1 Metrics */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Revenue at risk" value={formatMoney(revenueAtRisk)} detail="Featured recovery opportunities" icon={Target} tone="cyan" progress={100} badge="DEMO · SYNTHETIC" />
        <MetricCard label="Active opportunities" value={String(demoActive.length)} detail="Non-terminal synthetic cases" icon={Activity} tone="blue" progress={data.cases.length ? (demoActive.length / data.cases.length) * 100 : 0} />
        <MetricCard label="Verified Razorpay Test recovery" value={formatMoney(verifiedRecovery)} detail="Exactly-once attribution" subtext="No real money moved" icon={CircleDollarSign} tone="emerald" progress={verifiedRecovery > 0 ? 100 : 0} badge="RAZORPAY · TEST MODE" />
      </section>

      {/* Row 2 Metrics */}
      <section className="grid gap-4 sm:grid-cols-2">
        <MetricCard label="Sealed batch recovery" value="75.97%" detail="20,821 recovered · 27,406 episodes" subtext="Sealed evaluation · not provider revenue" icon={Beaker} tone="violet" progress={75.97} badge="SIMULATED" />
        <MetricCard label="Safe escalations" value={String(operationalReviews)} detail="Human Review · insufficient context" icon={ShieldAlert} tone="amber" progress={demoActive.length ? (operationalReviews / demoActive.length) * 100 : 0} />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
        <RecoveryTrendChart cases={data.cases} />
        <RecoveryDonut recovered={recovered.length} active={active.length} terminal={terminal.length} />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <article className="surface-panel overflow-hidden rounded-2xl">
          <div className="flex items-center justify-between border-b px-5 py-4 sm:px-6"><div><p className="eyebrow">Latest activity</p><h2 className="mt-1.5 text-base font-semibold">Recovery queue</h2></div><Link href="/recovery-cases" className="focus-ring group flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-semibold text-primary">View all<ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" /></Link></div>
          {latest.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">No recovery cases have been recorded.</p> : <div className="divide-y">{latest.map((item) => <Link key={item.id} href={`/recovery-cases/${item.id}`} className="group grid gap-3 px-5 py-4 transition-colors hover:bg-muted/45 sm:grid-cols-[1fr_auto_auto_auto] sm:items-center sm:px-6"><div className="min-w-0"><p className="truncate font-mono text-xs font-semibold">Case {shortId(item.id)}</p><p className="mt-1 truncate text-[11px] text-muted-foreground">Ref {shortId(item.correlation_id, 12)} · activity {formatDate(item.last_activity_at)}</p></div><SourceBadge source={item.source} /><StatusBadge status={item.status} /><p className="text-sm font-semibold sm:text-right">{formatMoney(item.amount_minor, item.currency)}</p></Link>)}</div>}
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

function SourceBadge({ source }: { source: string }) {
  if (source === "DEMO_SYNTHETIC") return <span className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-cyan-700 uppercase dark:text-cyan-300">Demo · Synthetic</span>;
  if (source === "RAZORPAY_TEST_MODE") return <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-emerald-700 uppercase dark:text-emerald-300">Razorpay · Test</span>;
  return <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-amber-700 uppercase dark:text-amber-300">Local · Unverified</span>;
}

function ReadinessRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return <div className="flex items-center gap-3 rounded-xl border bg-card/50 px-3.5 py-3"><span className={`size-2 rounded-full ${ok ? "bg-emerald-500 shadow-[0_0_9px_rgb(16_185_129_/_0.45)]" : "bg-amber-500"}`} /><dt className="text-xs text-muted-foreground">{label}</dt><dd className="ml-auto font-mono text-[11px] font-semibold uppercase">{value}</dd></div>;
}
