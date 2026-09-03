import { BarChart3, Beaker, Bot, CheckCircle2, DatabaseZap, ShieldCheck, Sparkles, AlertTriangle } from "lucide-react";

import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { getActionAdvantageDiagnostic } from "@/lib/api";

const policies = [
  { label: "Sequential Policy V2", value: 75.97, color: "bg-primary" },
  { label: "Observable rules", value: 64.6, color: "bg-sky-500" },
  { label: "Reminder + Retry", value: 53.09, color: "bg-violet-500" },
];

export const dynamic = "force-dynamic";

export default async function EvaluationPage() {
  const diagnostic = await getActionAdvantageDiagnostic().catch(() => null);

  return (
    <>
      <PageHeader eyebrow="Frozen evaluation evidence" title="Evidence before claims." description="A transparent view of the sealed simulator, model, policy, detector, and Test Mode results that support this submission." icon={BarChart3} />
      <div className="space-y-5">
        <section className="rounded-2xl border border-violet-500/25 bg-violet-500/[0.07] p-5 sm:p-6"><span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1 text-[10px] font-bold tracking-[0.12em] text-violet-700 uppercase dark:text-violet-300">Simulated batch evaluation</span><h2 className="mt-4 text-xl font-bold">Measured recovery across deterministic simulated trajectories.</h2><p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">Batch evaluation measures recovery performance across deterministic simulated payment trajectories. Monetary values shown here are simulated and are separate from Razorpay Test Mode evidence.</p></section>
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Sealed episodes" value="27,406" detail="Paired simulated evaluation" icon={CheckCircle2} tone="emerald" progress={100} />
          <MetricCard label="Recovery performance" value="75.97%" detail="Sequential ERV Policy V2 · simulated" icon={Beaker} tone="cyan" progress={75.97} />
          <MetricCard label="Policy violations" value="0" detail="27,406 sealed episodes" icon={ShieldCheck} tone="violet" progress={0} />
          <MetricCard label="Separate provider proof" value="₹2.00" detail="Razorpay Test Mode · no real money" icon={DatabaseZap} tone="amber" progress={100} />
        </section>
        
        {diagnostic && (
          <section className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.03] p-5 sm:p-6">
            <div className="flex items-start justify-between">
              <div>
                <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1 text-[10px] font-bold tracking-[0.12em] text-amber-700 uppercase dark:text-amber-300">SEALED · POST-HOC · SIMULATED</span>
                <h2 className="mt-4 text-xl font-bold">COUNTERFACTUAL ACTION ADVANTAGE</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Feasible actions are compared under matched simulated hidden-world conditions. This is not production causal evidence. Simulator 0.3.0 does not model direct natural recovery during WAIT.
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard 
                label="Selected Action Best/Tied" 
                value={`${((diagnostic.metrics.fraction_best + diagnostic.metrics.fraction_tied) * 100).toFixed(1)}%`} 
                detail="vs feasible alternatives" 
                icon={Sparkles} 
                tone="cyan" 
                progress={(diagnostic.metrics.fraction_best + diagnostic.metrics.fraction_tied) * 100} 
              />
              <MetricCard 
                label="Counterfactual Value Capture" 
                value={diagnostic.metrics.counterfactual_value_capture ? `${(diagnostic.metrics.counterfactual_value_capture * 100).toFixed(1)}%` : "N/A"} 
                detail="of best alternative net value" 
                icon={BarChart3} 
                tone="emerald" 
                progress={diagnostic.metrics.counterfactual_value_capture ? diagnostic.metrics.counterfactual_value_capture * 100 : 0} 
              />
              <MetricCard 
                label="Mean Action Regret" 
                value={`₹${(diagnostic.metrics.mean_regret_minor / 100).toFixed(2)}`} 
                detail="average value lost to suboptimal choice" 
                icon={AlertTriangle} 
                tone="amber" 
                progress={100} 
              />
              <MetricCard 
                label="Eligible Decisions" 
                value={diagnostic.metrics.eligible_paired_decisions.toLocaleString()} 
                detail=">= 2 feasible modeled candidates" 
                icon={CheckCircle2} 
                tone="violet" 
                progress={100} 
              />
            </div>
            
            <div className="mt-6 overflow-hidden rounded-xl border">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-muted/50 text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3 font-medium">Selected Action</th>
                      <th className="px-4 py-3 font-medium text-right">Decisions</th>
                      <th className="px-4 py-3 font-medium text-right">Recovery Rate</th>
                      <th className="px-4 py-3 font-medium text-right">Best Alternative</th>
                      <th className="px-4 py-3 font-medium text-right">Value Capture</th>
                      <th className="px-4 py-3 font-medium text-right">Regret</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {Object.entries(diagnostic.breakdown.action)
                      .sort(([, a], [, b]) => b.eligible_decisions - a.eligible_decisions)
                      .map(([action, stats]) => {
                        const capture = stats.best_feasible_total_realized_net_value > 0 
                          ? stats.selected_total_realized_net_value / stats.best_feasible_total_realized_net_value 
                          : null;
                        return (
                          <tr key={action} className="bg-card hover:bg-muted/30">
                            <td className="px-4 py-3 font-medium">{action}</td>
                            <td className="px-4 py-3 text-right">{stats.eligible_decisions.toLocaleString()}</td>
                            <td className="px-4 py-3 text-right">{(stats.factual_recovery_rate * 100).toFixed(1)}%</td>
                            <td className="px-4 py-3 text-right">{(stats.best_counterfactual_recovery_rate * 100).toFixed(1)}%</td>
                            <td className="px-4 py-3 text-right">{capture !== null ? `${(capture * 100).toFixed(1)}%` : "N/A"}</td>
                            <td className="px-4 py-3 text-right text-amber-600 dark:text-amber-400">
                              ₹{(stats.regret_minor / 100 / stats.eligible_decisions).toFixed(2)}
                            </td>
                          </tr>
                        );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
          <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between"><div><p className="eyebrow">Sealed policy comparison</p><h2 className="mt-2 text-lg font-semibold">Episode recovery rate</h2></div><span className="rounded-full border bg-card px-3 py-1 text-[10px] font-semibold text-muted-foreground">Synthetic evidence</span></div><div className="mt-8 space-y-6">{policies.map((policy) => <div key={policy.label}><div className="mb-2 flex items-center justify-between gap-4"><p className="text-xs font-medium">{policy.label}</p><p className="font-mono text-xs font-semibold">{policy.value.toFixed(2)}%</p></div><div className="h-3 overflow-hidden rounded-full bg-muted"><div className={`h-full rounded-full ${policy.color}`} style={{ width: `${policy.value}%` }} /></div></div>)}</div><p className="mt-7 border-t pt-4 text-[11px] leading-5 text-muted-foreground">Results come from paired synthetic evaluation and are not production revenue claims.</p></article>
          <div className="grid gap-4"><EvidenceCard icon={Bot} title="Recovery Model V2" body="Passed its held-out gate on 62,918 decisions across 27,451 synthetic episodes with frozen isotonic calibration." /><EvidenceCard icon={ShieldCheck} title="Detector V2" body="Failed its hard-policy safety gate and remains advisory-only. It is excluded from primary Model V2 features." /><EvidenceCard icon={Sparkles} title="Explanation layer" body="Groq is optional, structured, and non-authoritative. Deterministic fallback preserves availability without changing recovery." /></div>
        </section>
        <section className="grid gap-4 md:grid-cols-3"><EvidenceCard icon={ShieldCheck} title="Compliant escalation" body="Unsupported feature context ends in Human Review instead of fabricated certainty." /><EvidenceCard icon={Beaker} title="Stopping rules" body="48-hour horizon, three interventions, two retries, two contacts, and terminal recovery/STOP/review boundaries." /><EvidenceCard icon={CheckCircle2} title="Auditability" body="Every simulated decision is evaluated against the frozen policy contract with zero recorded violations." /></section>
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.055] p-5 text-sm leading-6 text-amber-900 dark:text-amber-100"><strong>Reproducibility guard:</strong> all overall-final seeds remain untouched. Existing frozen artifacts are evidence, not mutable application state.</div>
      </div>
    </>
  );
}

function EvidenceCard({ icon: Icon, title, body }: { icon: typeof Bot; title: string; body: string }) {
  return <article className="surface-panel interactive-panel rounded-2xl p-5"><div className="flex items-start gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent text-primary"><Icon className="size-4" /></span><div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-2 text-xs leading-5 text-muted-foreground">{body}</p></div></div></article>;
}
