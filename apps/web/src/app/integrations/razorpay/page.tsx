"use client";

import { CheckCircle2, CreditCard, Link2, LockKeyhole, RefreshCw, ShieldCheck, Webhook } from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getRazorpayStatus, getRecoveryCases, type RazorpayStatus } from "@/lib/api";
import { formatMoney, titleCase } from "@/lib/format";

type IntegrationData = { status: RazorpayStatus; verifiedRecoveryMinor: number };

export default function RazorpayIntegrationPage() {
  const load = useCallback(async (signal: AbortSignal): Promise<IntegrationData> => {
    const [status, cases] = await Promise.all([getRazorpayStatus(signal), getRecoveryCases(signal)]);
    return { status, verifiedRecoveryMinor: cases.reduce((sum, item) => sum + item.verified_recovery_minor, 0) };
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
        <section className="grid gap-5 lg:grid-cols-[0.65fr_1.35fr]"><article className="rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.065] p-6"><p className="eyebrow text-emerald-700 dark:text-emerald-300">Provider-verified Test recovery</p><p className="mt-3 text-3xl font-black text-emerald-700 dark:text-emerald-200">{formatMoney(resource.data.verifiedRecoveryMinor)}</p><p className="mt-2 text-xs leading-5 text-muted-foreground">Exactly-once attribution from authenticated Razorpay Test Mode evidence. No real money moved.</p></article><section className="surface-panel overflow-hidden rounded-2xl"><div className="border-b px-5 py-4 sm:px-6"><p className="eyebrow">Execution capability map</p><h2 className="mt-1.5 text-base font-semibold">What each action is allowed to do</h2></div><div className="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-3">{Object.entries(resource.data.status.capabilities).map(([action, capability]) => <div key={action} className="bg-card/85 p-4"><p className="font-mono text-[11px] font-semibold">{action}</p><p className="mt-2 text-xs text-muted-foreground">{titleCase(capability)}</p></div>)}</div></section></section>
        <div className="flex flex-col items-start justify-between gap-4 rounded-2xl border bg-card/65 p-5 sm:flex-row sm:items-center"><div><p className="text-sm font-semibold">Payment Links are created from a Recovery Case.</p><p className="mt-1 text-xs text-muted-foreground">Every request uses a confirmation step and backend idempotency.</p></div><Button nativeButton={false} render={<Link href="/recovery-cases" />}><Link2 className="size-4" />Open recovery queue</Button></div>
      </div>}
    </>
  );
}

function IntegrationCard({ icon: Icon, label, value, ok }: { icon: typeof ShieldCheck; label: string; value: string; ok: boolean }) {
  return <article className="surface-panel interactive-panel rounded-2xl p-5"><div className="flex items-start justify-between"><span className={`grid size-10 place-items-center rounded-xl ${ok ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300" : "bg-amber-500/10 text-amber-700 dark:text-amber-300"}`}><Icon className="size-4.5" /></span><span className={`size-2 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`} /></div><p className="eyebrow mt-5">{label}</p><p className="mt-2 text-lg font-semibold">{value}</p></article>;
}
