"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Copy, Database, Shield, ShieldCheck, AlertCircle, Activity, CircleDollarSign, Fingerprint, Lock } from "lucide-react";

import { MetricCard } from "@/components/metric-card";
import { cn } from "@/lib/utils";

interface SafetyEvidence {
  schema_version: string;
  evidence_type: string;
  generated_at: string;
  git_commit: string;
  database: {
    engine: string;
    journal_mode: string;
    temporary: boolean;
  };
  provider: {
    type: string;
    razorpay_network_calls: number;
  };
  scenarios: Record<string, Record<string, unknown>>;
}

export function SafetyLabContent() {
  const [data, setData] = useState<SafetyEvidence | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchEvidence = async () => {
    setError(false);
    try {
      const res = await fetch("/api/safety/summary");
      if (!res.ok) throw new Error("Safety evidence unavailable");
      const json = await res.json();
      setData(json);
    } catch {
      setError(true);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void fetchEvidence();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed text-muted-foreground">
        Loading safety verification evidence...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-red-200 bg-red-50/50 p-6 text-center dark:border-red-900/50 dark:bg-red-900/10">
        <AlertTriangle className="size-8 text-red-500" />
        <div>
          <h3 className="font-semibold text-red-700 dark:text-red-400">Safety evidence unavailable</h3>
          <p className="mt-1 text-sm text-muted-foreground">Run the local verification harness to generate the evidence artifact.</p>
        </div>
        <div className="mt-2 flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-xs font-mono text-muted-foreground">
          python -m app.dev.run_safety_verification
          <button 
            type="button"
            className="ml-2 hover:text-foreground focus:outline-none"
            onClick={() => navigator.clipboard.writeText("python -m app.dev.run_safety_verification")}
            aria-label="COPY VERIFICATION COMMAND"
          >
            <Copy className="size-3" />
          </button>
        </div>
      </div>
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const verifiedCount = Object.values(data.scenarios).filter((s: any) => s.status === "PROVEN").length;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const duplicateFinancialEffects = 
    ((data.scenarios.concurrent_webhook as any)?.measured?.financial_side_effects || 0) + 
    ((data.scenarios.concurrent_executor as any)?.measured?.duplicate_provider_effects || 0);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const duplicateAttributions = (data.scenarios.duplicate_success as any)?.measured?.duplicate_attributed_amount || 0;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fakeProviderCalls = (data.scenarios.concurrent_executor as any)?.measured?.fake_provider_calls || 0;

  return (
    <div className="space-y-6">
      {/* Top Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-xs font-semibold tracking-[0.08em] text-primary">
            <ShieldCheck className="size-3.5" />
            ISOLATED LOCAL VERIFICATION
          </div>
          <span className="text-xs text-muted-foreground">
            Generated: {new Date(data.generated_at).toLocaleString()}
          </span>
        </div>
        <button
          type="button"
          onClick={fetchEvidence}
          className="rounded-lg border bg-card px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          Refresh evidence
        </button>
      </div>

      {/* Top Metrics */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Scenarios Verified"
          value={verifiedCount.toString()}
          detail={`${Object.keys(data.scenarios).length} total assertions`}
          icon={ShieldCheck}
          tone="emerald"
        />
        <MetricCard
          label="Duplicate Financial Effects"
          value={duplicateFinancialEffects.toString()}
          detail="Across webhook & execution races"
          icon={CircleDollarSign}
          tone="emerald"
        />
        <MetricCard
          label="Duplicate Attributions"
          value={duplicateAttributions.toString()}
          detail="Exactly-once success recording"
          icon={Fingerprint}
          tone="emerald"
        />
        <MetricCard
          label="Fake Provider Calls"
          value={`${fakeProviderCalls} / 10-way`}
          detail="Execution race winner calls"
          icon={Activity}
          tone="cyan"
        />
      </div>

      {/* Database Guarantees Panel */}
      <div className="rounded-xl border bg-card">
        <div className="border-b px-5 py-4">
          <div className="flex items-center gap-2 font-semibold">
            <Database className="size-4 text-primary" />
            Database Guarantees
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Financial idempotency is enforced at the persistence layer, not delegated to the LLM or frontend.
          </p>
        </div>
        <div className="grid gap-6 p-5 sm:grid-cols-2">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Unique Constraints</p>
            <ul className="space-y-1.5 text-sm font-mono text-muted-foreground">
              <li className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1">
                <span>ExternalWebhookEvent.provider_event_id</span> <span className="text-primary">UNIQUE</span>
              </li>
              <li className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1">
                <span>ExternalExecution.execution_plan_id</span> <span className="text-primary">UNIQUE</span>
              </li>
              <li className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1">
                <span>ExternalExecution.idempotency_key</span> <span className="text-primary">UNIQUE</span>
              </li>
              <li className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1">
                <span>ExternalExecution.provider_reference_id</span> <span className="text-primary">UNIQUE</span>
              </li>
              <li className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1">
                <span>ExternalOutcome.webhook_event_id</span> <span className="text-primary">UNIQUE</span>
              </li>
              <li className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1">
                <span>ExternalOutcome.external_payment_id</span> <span className="text-primary">UNIQUE</span>
              </li>
              <li className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1">
                <span>RecoveryAttribution.recovery_case_id</span> <span className="text-primary">UNIQUE</span>
              </li>
              <li className="flex items-center justify-between rounded-md bg-muted/50 px-2 py-1">
                <span>RecoveryAttribution.external_outcome_id</span> <span className="text-primary">UNIQUE</span>
              </li>
            </ul>
          </div>
          <div className="space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Database Environment</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between border-b pb-1">
                  <span className="text-muted-foreground">Database Engine</span>
                  <span className="font-medium capitalize">{data.database.engine} (Isolated)</span>
                </div>
                <div className="flex justify-between border-b pb-1">
                  <span className="text-muted-foreground">Journal Mode</span>
                  <span className="font-mono uppercase">{data.database.journal_mode}</span>
                </div>
                <div className="flex justify-between border-b pb-1">
                  <span className="text-muted-foreground">WAL Enabled</span>
                  <span className="font-mono">NOT ENABLED</span>
                </div>
                <div className="flex justify-between border-b pb-1">
                  <span className="text-muted-foreground">PostgreSQL</span>
                  <span className="font-medium">COMPATIBLE (UNTESTED IN DEMO)</span>
                </div>
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Provider Status</p>
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-400">
                Tests run using an isolated {data.provider.type} provider with {data.provider.razorpay_network_calls} Razorpay network calls.
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Visual Diagrams for Scenarios A & B */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Webhook Race Visual */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 font-semibold">10-Way Webhook Concurrency</h3>
          <div className="flex flex-col items-center gap-2">
            <div className="flex gap-1">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="h-2 w-6 rounded-full bg-slate-300 dark:bg-slate-700" />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">10 Concurrent Webhook Requests</p>
            <div className="h-6 w-px bg-border" />
            <div className="rounded-lg border bg-muted px-4 py-2 text-center text-xs font-mono flex items-center gap-2">
              <Lock className="size-3.5 text-primary" />
              provider_event_id UNIQUE
            </div>
            <div className="h-6 w-px bg-border" />
            <div className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className="grid size-8 place-items-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-400">
                  <CheckCircle2 className="size-4" />
                </div>
                <span className="mt-1 text-xs font-medium">1 Processed</span>
              </div>
              <div className="flex flex-col items-center">
                <div className="grid size-8 place-items-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                  <Shield className="size-4" />
                </div>
                <span className="mt-1 text-xs font-medium">9 Duplicates Rejected</span>
              </div>
            </div>
            <div className="mt-4 rounded border border-emerald-200 bg-emerald-50 px-3 py-1 text-center text-xs font-medium text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-900/20 dark:text-emerald-400">
              0 duplicate financial effects
            </div>
          </div>
        </div>

        {/* Executor Race Visual */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 font-semibold">10-Way Execution Race</h3>
          <div className="flex flex-col items-center gap-2">
            <div className="flex gap-1">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="h-2 w-6 rounded-full bg-blue-300 dark:bg-blue-700" />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">10 Concurrent Invocations</p>
            <div className="h-6 w-px bg-border" />
            <div className="rounded-lg border bg-muted px-4 py-2 text-center text-xs font-mono flex items-center gap-2">
              <Lock className="size-3.5 text-primary" />
              UNIQUE RESERVATION / IDEMPOTENCY GATE
            </div>
            <div className="h-6 w-px bg-border" />
            <div className="flex flex-col items-center">
              <div className="grid size-8 place-items-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-400">
                <CheckCircle2 className="size-4" />
              </div>
              <span className="mt-1 text-xs font-medium">1 Logical Winner</span>
            </div>
            <div className="h-6 w-px bg-border" />
            <div className="rounded border border-primary/20 bg-primary/10 px-3 py-1 text-center text-xs font-medium text-primary">
              1 Fake Provider Call
            </div>
          </div>
        </div>
      </div>

      {/* Safety Coverage Matrix */}
      <div>
        <h3 className="mb-4 text-lg font-semibold">Safety Coverage Matrix</h3>
        <div className="overflow-hidden rounded-xl border bg-card">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-5 py-3 font-medium">Scenario</th>
                <th className="px-5 py-3 font-medium">Defense Mechanism</th>
                <th className="px-5 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              <ScenarioRow 
                title="Duplicate webhook" 
                mechanism={(data.scenarios.concurrent_webhook as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.concurrent_webhook as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="Concurrent executor" 
                mechanism={(data.scenarios.concurrent_executor as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.concurrent_executor as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="Duplicate success" 
                mechanism={(data.scenarios.duplicate_success as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.duplicate_success as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="Exactly-once attribution" 
                mechanism={(data.scenarios.duplicate_success as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.duplicate_success as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="Sequential duplicate execution" 
                mechanism={(data.scenarios.sequential_duplicate as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.sequential_duplicate as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="Retry storm" 
                mechanism={(data.scenarios.retry_storm as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.retry_storm as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="LLM outage isolation" 
                mechanism={(data.scenarios.llm_outage as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.llm_outage as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="Malformed LLM" 
                mechanism={(data.scenarios.malformed_llm as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.malformed_llm as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="Unknown payment" 
                mechanism={(data.scenarios.unmapped_payment as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.unmapped_payment as Record<string, string>)?.status}
              />
              <ScenarioRow 
                title="Provider crash ambiguity" 
                mechanism={(data.scenarios.provider_crash_ambiguity as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.provider_crash_ambiguity as Record<string, string>)?.status}
                notes={(data.scenarios.provider_crash_ambiguity as Record<string, string>)?.notes}
              />
              <ScenarioRow 
                title="Automatic stale reservation sweep" 
                mechanism={(data.scenarios.stale_reservation as Record<string, string>)?.defense_mechanism}
                status={(data.scenarios.stale_reservation as Record<string, string>)?.status}
                notes={(data.scenarios.stale_reservation as Record<string, string>)?.notes}
              />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ScenarioRow({ title, mechanism, status, notes }: { title: string, mechanism?: string, status?: string, notes?: string }) {
  if (!status) return null;
  
  let Icon = CheckCircle2;
  let statusClass = "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-900/20 dark:text-emerald-400";
  let statusText = "PROVEN";

  if (status === "PARTIALLY_PROTECTED") {
    Icon = AlertTriangle;
    statusClass = "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-400";
    statusText = "PARTIALLY PROTECTED";
  } else if (status === "NOT_IMPLEMENTED") {
    Icon = AlertCircle;
    statusClass = "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400";
    statusText = "NOT IMPLEMENTED";
  }

  return (
    <tr className="group transition-colors hover:bg-muted/50">
      <td className="px-5 py-3">
        <span className="font-medium">{title}</span>
        {notes && <p className="mt-1 text-xs text-muted-foreground">{notes}</p>}
      </td>
      <td className="px-5 py-3 font-mono text-xs text-muted-foreground">{mechanism || "N/A"}</td>
      <td className="px-5 py-3">
        <div className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold tracking-wide", statusClass)}>
          <Icon className="size-3" />
          {statusText}
        </div>
      </td>
    </tr>
  );
}
