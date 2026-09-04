"use client";

import { useEffect, useState } from "react";
import { 
  Activity, AlertTriangle, ShieldCheck, 
  PieChart, Layers, Target, Coins, TrendingUp
} from "lucide-react";
import { MetricCard } from "@/components/metric-card";
import { getBatchExplorerData, BatchExplorerData, CohortItem } from "@/lib/api";
import { formatMoney } from "@/lib/format";

function formatPercentage(val: number): string {
  return (val * 100).toFixed(1) + "%";
}

function calculateInsights(cohorts: BatchExplorerData["cohorts"]) {
  let largestCohort: CohortItem | null = null;
  let highestRecovery: CohortItem | null = null;
  let lowestRecovery: CohortItem | null = null;
  
  const allCohorts = [
    ...(cohorts.failure_reason || []),
    ...(cohorts.payment_method || [])
  ];

  for (const c of allCohorts) {
    if (!largestCohort || c.episodes > largestCohort.episodes) largestCohort = c;
    if (c.episodes > 100) { // minimum threshold for rates
      if (!highestRecovery || c.recovery_rate > highestRecovery.recovery_rate) highestRecovery = c;
      if (!lowestRecovery || c.recovery_rate < lowestRecovery.recovery_rate) lowestRecovery = c;
    }
  }

  return { largestCohort, highestRecovery, lowestRecovery };
}

export function BatchExplorerContent() {
  const [data, setData] = useState<BatchExplorerData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeTab, setActiveTab] = useState<"failure_reason" | "payment_method" | "amount_bucket" | "prior_success_bucket" | "subscription_tenure_bucket">("failure_reason");

  useEffect(() => {
    let cancelled = false;
    getBatchExplorerData()
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch((e) => {
        console.error("Batch Explorer API Error:", e);
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed text-muted-foreground">
        Loading batch explorer portfolio intelligence...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-red-200 bg-red-50/50 p-6 text-center dark:border-red-900/50 dark:bg-red-900/10">
        <AlertTriangle className="size-8 text-red-500" />
        <div>
          <h3 className="font-semibold text-red-700 dark:text-red-400">Batch Explorer Unavailable</h3>
          <p className="mt-1 text-sm text-muted-foreground">Ensure the evaluation artifact exists on the backend.</p>
        </div>
      </div>
    );
  }

  const { portfolio, cohorts, action_mix, intervention_burden, baseline_comparison } = data;
  const insights = calculateInsights(cohorts);
  const currentCohorts = cohorts[activeTab] || [];

  return (
    <div className="space-y-8 pb-12">
      {/* Hero / Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-xs font-semibold tracking-[0.08em] text-primary">
              <ShieldCheck className="size-3.5" />
              SEALED &middot; SIMULATED
            </div>
          </div>
          <h1 className="mt-4 text-3xl font-bold tracking-tight">Portfolio Intelligence</h1>
          <p className="mt-2 text-muted-foreground max-w-2xl">
            Analysis of {data.episodes.toLocaleString()} simulated recovery episodes. 
            Understanding how recovery performance varies across isolated cohorts.
          </p>
        </div>
      </div>

      {/* Primary Portfolio Metrics */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Episodes"
          value={data.episodes.toLocaleString()}
          detail="Total sealed simulated episodes"
          icon={Layers}
          tone="blue"
        />
        <MetricCard
          label="Recovery Rate"
          value={formatPercentage(portfolio.recovery_rate)}
          detail={`${portfolio.recovered_episodes.toLocaleString()} recovered`}
          icon={Target}
          tone="emerald"
        />
        <MetricCard
          label="Simulated Net Value"
          value={formatMoney(portfolio.simulated_net_recovery_value_minor)}
          detail={`+${formatMoney(baseline_comparison.incremental_net_value_minor)} vs Baseline`}
          icon={Coins}
          tone="emerald"
        />
        <MetricCard
          label="Mean Recovery Time"
          value={`${portfolio.mean_recovery_time_hours.toFixed(1)}h`}
          detail={`${portfolio.mean_actions_per_episode.toFixed(2)} mean actions`}
          icon={Activity}
          tone="cyan"
        />
      </div>

      {/* Business Insights */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {insights.largestCohort && (
          <div className="surface-panel rounded-xl p-5">
            <h3 className="text-sm font-medium text-muted-foreground">Largest Cohort</h3>
            <p className="mt-2 text-lg font-semibold">{insights.largestCohort.value}</p>
            <p className="mt-1 text-sm text-muted-foreground">{insights.largestCohort.episodes.toLocaleString()} episodes</p>
          </div>
        )}
        {insights.highestRecovery && (
          <div className="surface-panel rounded-xl p-5">
            <h3 className="text-sm font-medium text-muted-foreground">Highest Recovery</h3>
            <p className="mt-2 text-lg font-semibold text-emerald-500">{insights.highestRecovery.value}</p>
            <p className="mt-1 text-sm text-muted-foreground">{formatPercentage(insights.highestRecovery.recovery_rate)} rate</p>
          </div>
        )}
        {insights.lowestRecovery && (
          <div className="surface-panel rounded-xl p-5">
            <h3 className="text-sm font-medium text-muted-foreground">Lowest Recovery</h3>
            <p className="mt-2 text-lg font-semibold text-amber-500">{insights.lowestRecovery.value}</p>
            <p className="mt-1 text-sm text-muted-foreground">{formatPercentage(insights.lowestRecovery.recovery_rate)} rate</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-3">
        {/* Recovery Cohort Map (2 cols) */}
        <div className="xl:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recovery Cohort Map</h2>
          </div>
          
          <div className="surface-panel rounded-xl overflow-hidden">
            <div className="border-b bg-muted/40 p-1">
              <div className="flex flex-wrap gap-1">
                {[
                  { id: "failure_reason", label: "Failure Reason" },
                  { id: "payment_method", label: "Payment Method" },
                  { id: "amount_bucket", label: "Amount Bucket" },
                  { id: "prior_success_bucket", label: "Prior Success" },
                  { id: "subscription_tenure_bucket", label: "Tenure" },
                ].map(t => (
                  <button 
                    key={t.id}
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    onClick={() => setActiveTab(t.id as any)}
                    className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                      activeTab === t.id 
                        ? "bg-background text-foreground shadow-sm" 
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/20 text-muted-foreground text-xs uppercase border-b">
                  <tr>
                    <th className="px-6 py-4 font-semibold">Cohort</th>
                    <th className="px-6 py-4 font-semibold text-right">Episodes</th>
                    <th className="px-6 py-4 font-semibold text-right">Recovery Rate</th>
                    <th className="px-6 py-4 font-semibold">Top Sequence</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {currentCohorts.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">
                        No data available for this dimension.
                      </td>
                    </tr>
                  )}
                  {currentCohorts
                    .sort((a: CohortItem, b: CohortItem) => b.episodes - a.episodes)
                    .map((cohort: CohortItem) => (
                    <tr key={cohort.value} className="hover:bg-muted/10 transition-colors">
                      <td className="px-6 py-4 font-medium">{cohort.value}</td>
                      <td className="px-6 py-4 text-right tabular-nums">{cohort.episodes.toLocaleString()}</td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <span className="tabular-nums">{formatPercentage(cohort.recovery_rate)}</span>
                          <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-emerald-500" 
                              style={{ width: `${cohort.recovery_rate * 100}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {cohort.top_sequence ? (
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs bg-muted/30 px-2 py-1 rounded break-all whitespace-normal">
                              {cohort.top_sequence}
                            </span>
                            {cohort.top_sequence_share !== undefined && (
                              <span className="text-xs text-muted-foreground">
                                {formatPercentage(cohort.top_sequence_share)}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Sidebar: Action Mix & Burden */}
        <div className="space-y-6">
          <div className="surface-panel rounded-xl p-5 sm:p-6">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <PieChart className="size-4" />
              Action Mix
            </h2>
            <p className="text-xs text-muted-foreground mt-1 mb-6">Total actions across {data.episodes.toLocaleString()} episodes</p>
            
            <div className="space-y-4">
              {[
                { label: "Retries", value: action_mix.retries, color: "bg-blue-500" },
                { label: "Payment Links", value: action_mix.payment_links, color: "bg-purple-500" },
                { label: "Method Updates", value: action_mix.method_updates, color: "bg-indigo-500" },
                { label: "Alternate Methods", value: action_mix.alternate_methods, color: "bg-cyan-500" },
                { label: "Human Reviews", value: action_mix.human_reviews, color: "bg-amber-500" },
                { label: "Stop Outcomes", value: action_mix.stop_outcomes, color: "bg-rose-500" },
              ].map(action => (
                <div key={action.label}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-muted-foreground">{action.label}</span>
                    <span className="font-medium tabular-nums">{action.value.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="surface-panel rounded-xl p-5 sm:p-6">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <TrendingUp className="size-4" />
              Intervention Burden
            </h2>
            <p className="text-xs text-muted-foreground mt-1 mb-6">Derived cost and efficiency metrics</p>
            
            <div className="space-y-4">
              <div className="flex justify-between text-sm border-b border-border/50 pb-2">
                <span className="text-muted-foreground">Contacts / Recovered</span>
                <span className="font-medium tabular-nums">
                  {intervention_burden.contacts_per_recovered_payment?.toFixed(2) || "0.00"}
                </span>
              </div>
              <div className="flex justify-between text-sm border-b border-border/50 pb-2">
                <span className="text-muted-foreground">Recoveries / Contact</span>
                <span className="font-medium tabular-nums">
                  {intervention_burden.recoveries_per_contact?.toFixed(2) || "0.00"}
                </span>
              </div>
              <div className="flex justify-between text-sm border-b border-border/50 pb-2">
                <span className="text-muted-foreground">Net Value / Contact</span>
                <span className="font-medium tabular-nums text-emerald-500">
                  {formatMoney(intervention_burden.net_value_per_customer_contact_minor || 0)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Policy Violations</span>
                <span className="font-medium tabular-nums">{portfolio.policy_violations}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
