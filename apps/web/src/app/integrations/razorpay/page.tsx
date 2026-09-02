"use client";

import { CheckCircle2, CreditCard, Link2, LockKeyhole, RefreshCw, ShieldCheck, Webhook } from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getRazorpayStatus, getRecoveryCases, getRazorpayEvidence, type RazorpayStatus, type RazorpayEvidence } from "@/lib/api";
import { formatMoney, titleCase } from "@/lib/format";

type IntegrationData = { status: RazorpayStatus; evidence: RazorpayEvidence; verifiedRecoveryMinor: number };

export default function RazorpayIntegrationPage() {
  const load = useCallback(async (signal: AbortSignal): Promise<IntegrationData> => {
    const [status, , evidence] = await Promise.all([getRazorpayStatus(signal), getRecoveryCases(signal), getRazorpayEvidence(signal)]);
    return { status, evidence, verifiedRecoveryMinor: evidence.all_time_recovered_minor };
  }, []);
  const resource = useApiResource(load);
  return (
    <>
      <PageHeader eyebrow="Provider integration" title="Razorpay, constrained to Test Mode." description="Inspect provider readiness and execution capabilities without exposing credentials or enabling Live Mode." icon={CreditCard} actions={<Button variant="outline" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} />Refresh status</Button>} />
      {resource.loading && <LoadingPanel />}
      {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
      {resource.data && <div className="space-y-5">
        <section className="relative overflow-hidden rounded-3xl border border-emerald-500/20 bg-[linear-gradient(130deg,rgb(16_185_129_/_0.13),var(--surface-glass)_55%)] p-6 shadow-[var(--shadow-panel)] sm:p-8"><div className="pointer-events-none absolute -right-16 -top-16 size-56 rounded-full border-[34px] border-emerald-500/[0.06]" /><div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-center"><div><div className="flex items-center gap-2 text-sm font-semibold text-emerald-700 dark:text-emerald-300"><CheckCircle2 className="size-4" />Integration configured</div><h2 className="mt-3 text-2xl font-bold tracking-tight">Secure provider execution is ready.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">API and webhook credentials are detected by typed backend settings. Values are never returned to this page.</p></div><div className="rounded-2xl border border-amber-500/25 bg-amber-500/10 px-6 py-4 text-center"><p className="text-[10px] font-bold tracking-[0.16em] text-amber-700 uppercase dark:text-amber-300">Provider mode</p><p className="mt-1 text-2xl font-black text-amber-700 dark:text-amber-200">TEST</p><p className="mt-1 text-[10px] text-amber-700/75 dark:text-amber-300/75">No Live Mode</p></div></div></section>
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <IntegrationCard icon={CreditCard} label="API connection" value={resource.data.status.api_configured ? "Connected" : "Not configured"} ok={resource.data.status.api_configured} />
          <IntegrationCard icon={Webhook} label="Webhook" value={resource.data.status.webhook_configured ? "Active" : "Not configured"} ok={resource.data.status.webhook_configured} />
          <IntegrationCard icon={Link2} label="Payment Link" value={resource.data.status.capabilities.CREATE_PAYMENT_LINK === "REAL_TEST_EXECUTION" ? "Available" : "Unavailable"} ok={resource.data.status.capabilities.CREATE_PAYMENT_LINK === "REAL_TEST_EXECUTION"} />
          <IntegrationCard icon={LockKeyhole} label="Live payments" value="Blocked" ok />
        </section>
        <section className="grid gap-5 lg:grid-cols-[0.65fr_1.35fr]"><article className="rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.065] p-6"><p className="eyebrow text-emerald-700 dark:text-emerald-300">Provider-verified Test recovery</p><p className="mt-3 text-3xl font-black text-emerald-700 dark:text-emerald-200">{formatMoney(resource.data.verifiedRecoveryMinor)}</p><p className="mt-2 text-xs leading-5 text-muted-foreground">Exactly-once attribution from authenticated Razorpay Test Mode evidence. No real money moved.</p></article><section className="surface-panel overflow-hidden rounded-2xl"><div className="border-b px-5 py-4 sm:px-6"><p className="eyebrow">Execution capability map</p><h2 className="mt-1.5 text-base font-semibold">What each action is allowed to do</h2></div><div className="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-3">{Object.entries(resource.data.status.capabilities).map(([action, capability]) => <div key={action} className="bg-card/85 p-4"><p className="font-mono text-[11px] font-semibold">{action}</p><p className="mt-2 text-xs text-muted-foreground">{action === "STOP" ? "Policy Decision Only" : titleCase(capability)}</p></div>)}</div></section></section>
        {resource.data.evidence.selected_case && (
          <TimelineAndEvidence data={resource.data.evidence.selected_case} />
        )}
        
        <div className="flex flex-col items-start justify-between gap-4 rounded-2xl border bg-card/65 p-5 sm:flex-row sm:items-center"><div><p className="text-sm font-semibold">Payment Links are created from a Recovery Case.</p><p className="mt-1 text-xs text-muted-foreground">Every request uses a confirmation step and backend idempotency.</p></div><Button nativeButton={false} render={<Link href="/recovery-cases" />}><Link2 className="size-4" />Open recovery queue</Button></div>
      </div>}
    </>
  );
}

function IntegrationCard({ icon: Icon, label, value, ok }: { icon: typeof ShieldCheck; label: string; value: string; ok: boolean }) {
  return <article className="surface-panel interactive-panel rounded-2xl p-5"><div className="flex items-start justify-between"><span className={`grid size-10 place-items-center rounded-xl ${ok ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300" : "bg-amber-500/10 text-amber-700 dark:text-amber-300"}`}><Icon className="size-4.5" /></span><span className={`size-2 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`} /></div><p className="eyebrow mt-5">{label}</p><p className="mt-2 text-lg font-semibold">{value}</p></article>;
}

function TimelineAndEvidence({ data }: { data: NonNullable<RazorpayEvidence["selected_case"]> }) {
  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <div className="surface-panel rounded-2xl overflow-hidden flex flex-col">
        <div className="border-b px-5 py-4">
          <p className="eyebrow">Recovery Timeline</p>
          <h2 className="mt-1.5 text-base font-semibold">Verified Case Events</h2>
        </div>
        <div className="p-6 flex-1 bg-card/50">
          <div className="space-y-6 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-border before:to-transparent">
            {/* Aug 23 Initial Failure */}
            <TimelineItem title="Initial Payment Failed" time={data.failed_attempts[0]?.created_at} description={`Provider Event: ${data.failed_attempts[0]?.provider_event_id || 'N/A'}`} status="failure" />
            
            {/* Operator Action */}
            <TimelineItem title="Operator Initiated Recovery" time={data.executions[0]?.created_at} description={`Created Payment Link via ${data.execution_initiator}`} status="info" />
            
            {/* Aug 30 Additional failures (Optional depending on data) */}
            {data.failed_attempts.length > 1 && (
              <TimelineItem title={`Additional Failures (${data.failed_attempts.length - 1})`} time={data.failed_attempts[data.failed_attempts.length - 1]?.created_at} description="Multiple retry attempts failed" status="failure" />
            )}
            
            {/* Success */}
            <TimelineItem title="Recovery Successful" time={data.outcomes[0]?.created_at} description={`Verified ${formatMoney(data.outcomes[0]?.amount_minor || 0)}`} status="success" />
          </div>
        </div>
      </div>

      <div className="surface-panel rounded-2xl overflow-hidden flex flex-col">
        <div className="border-b px-5 py-4 flex justify-between items-center">
          <div>
            <p className="eyebrow">Sanitized Provider Evidence</p>
            <h2 className="mt-1.5 text-base font-semibold">Redacted Webhook Evidence</h2>
          </div>
          <span className="rounded bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">Read Only</span>
        </div>
        
        {data.provider_truth && (
          <div className="border-b p-5 bg-card/40">
            <h3 className="text-sm font-semibold mb-3">Provider Truth Triangulation</h3>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${data.provider_truth.webhook_authenticated ? 'bg-emerald-500' : 'bg-muted'}`} />
                <span className="text-muted-foreground">Webhook Auth:</span>
                <span className="font-semibold">{data.provider_truth.webhook_authenticated ? "Verified" : "Missing"}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${data.provider_truth.provider_confirmation_status === 'CONFIRMED' ? 'bg-emerald-500' : (data.provider_truth.provider_confirmation_status === 'PENDING' ? 'bg-amber-500' : 'bg-red-500')}`} />
                <span className="text-muted-foreground">Provider State:</span>
                <span className="font-semibold">{data.provider_truth.provider_confirmation_status.replace(/_/g, ' ')}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${data.provider_truth.webhook_invariants_verified ? 'bg-emerald-500' : 'bg-muted'}`} />
                <span className="text-muted-foreground">Invariants:</span>
                <span className="font-semibold">{data.provider_truth.webhook_invariants_verified ? "Verified" : "Pending"}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${data.provider_truth.recovery_attribution_count > 0 ? 'bg-emerald-500' : 'bg-muted'}`} />
                <span className="text-muted-foreground">Attribution:</span>
                <span className="font-semibold">{data.provider_truth.recovery_attribution_count > 0 ? "Attributed" : "None"}</span>
              </div>
            </div>
          </div>
        )}

        <div className="p-6 flex-1 bg-black/90 text-emerald-400 font-mono text-[11px] overflow-auto max-h-[400px]">
          <pre>{JSON.stringify(data.webhooks.filter(w => w.event_type === "payment_link.paid" || w.event_type === "payment.failed"), null, 2)}</pre>
        </div>
      </div>
    </section>
  );
}

function TimelineItem({ title, time, description, status }: { title: string, time?: string, description: string, status: 'success' | 'failure' | 'info' }) {
  const Icon = status === 'success' ? CheckCircle2 : (status === 'failure' ? Webhook : ShieldCheck);
  const colorClass = status === 'success' ? 'text-emerald-500 bg-emerald-500/10' : (status === 'failure' ? 'text-red-500 bg-red-500/10' : 'text-blue-500 bg-blue-500/10');
  
  return (
    <div className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
      <div className="flex items-center justify-center w-10 h-10 rounded-full border-4 border-card bg-background shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 shadow-sm z-10">
        <div className={`w-full h-full rounded-full flex items-center justify-center ${colorClass}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-xl border bg-card shadow-sm">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-semibold text-sm">{title}</h3>
          {time && <time className="text-xs font-medium text-muted-foreground">{time ? new Date(time).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : ''}</time>}
        </div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
