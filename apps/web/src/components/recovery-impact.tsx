"use client";

import { EvaluationSummary } from "@/lib/api";
import { formatMinorINRToCompact, formatMinorINRToFull } from "@/lib/currency";

export function RecoveryImpact({ summary }: { summary: EvaluationSummary | null }) {
  if (!summary) {
    return (
      <section className="mt-12 bg-card border rounded-2xl p-8 shadow-sm">
        <h2 className="text-xl font-medium tracking-tight text-foreground">Recovery Impact</h2>
        <div className="mt-6 flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
          <p>Evaluation evidence unavailable</p>
        </div>
      </section>
    );
  }

  const riq = summary.recoveryiq;
  const baseline = summary.primary_baseline;
  const incValue = summary.incremental.simulated_net_value_minor;
  const incRate = summary.incremental.recovery_rate_pp;
  
  // Find Probability Policy for the story
  const probabilityPolicy = summary.strategies.find((s) => s.id === "sequential_probability_policy");
  let tradeOffStory = null;
  if (probabilityPolicy && probabilityPolicy.recovery_rate > riq.recovery_rate) {
      tradeOffStory = "Probability Policy recovers marginally more transactions, while RecoveryIQ V2 achieves nearly the same recovery with substantially fewer customer contacts.";
  }

  return (
    <section className="mt-12 space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">RECOVERY IMPACT</h2>
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            SEALED &middot; SIMULATED
          </span>
        </div>
        <p className="text-muted-foreground max-w-3xl leading-relaxed">
          Across {summary.episodes.toLocaleString()} sealed simulated recovery episodes, 
          {riq.name} achieved {(riq.recovery_rate * 100).toFixed(2)}% recovery and generated{" "}
          <span className="text-foreground font-medium">{formatMinorINRToCompact(riq.simulated_net_value_minor)}</span>{" "}
          simulated net recovery value. Compared with {baseline.name}, RecoveryIQ produced{" "}
          <span className="text-emerald-600 dark:text-emerald-400 font-medium">+{formatMinorINRToCompact(incValue)}</span> incremental simulated net value.
        </p>
        {tradeOffStory && (
            <p className="text-muted-foreground text-sm max-w-3xl mt-2 italic">{tradeOffStory}</p>
        )}
      </div>

      {/* Main Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Recovery Rate" value={`${(riq.recovery_rate * 100).toFixed(2)}%`} tooltip="Raw recovery percentage" />
        <MetricCard 
            title="Simulated Net Value" 
            value={formatMinorINRToCompact(riq.simulated_net_value_minor)} 
            tooltip={formatMinorINRToFull(riq.simulated_net_value_minor)} 
        />
        <MetricCard 
            title={`Incremental vs ${baseline.name}`} 
            value={`+${formatMinorINRToCompact(incValue)}`} 
            tooltip={`+${formatMinorINRToFull(incValue)}`}
            highlight 
        />
        <div className="flex flex-col gap-4">
            <MetricCard title="Recovery Improvement" value={`+${incRate.toFixed(2)} pp`} highlight />
            <MetricCard title="Policy Violations" value={riq.policy_violations.toString()} />
        </div>
      </div>

      {/* Decision Quality */}
      {summary.strategies.find((s) => s.id === "greedy_hidden_oracle") && (() => {
        const oracle = summary.strategies.find((s) => s.id === "greedy_hidden_oracle")!;
        const efficiency = (riq.simulated_net_value_minor / oracle.simulated_net_value_minor) * 100;
        const contactsPerRecovery = riq.recovered_count > 0 ? riq.contacts / riq.recovered_count : 0;
        
        return (
          <div className="bg-card border rounded-xl overflow-hidden mt-8 p-5 shadow-sm">
            <h3 className="text-sm font-bold tracking-widest text-muted-foreground uppercase mb-4">Decision Quality Audit</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <MetricCard 
                title="% of Oracle Net Value" 
                value={`${efficiency.toFixed(1)}%`} 
                tooltip="RecoveryIQ V2 Net Value / Hidden Oracle Net Value" 
              />
              <MetricCard 
                title="Contacts per Recovery" 
                value={contactsPerRecovery.toFixed(2)} 
                tooltip="Average contacts spent per successfully recovered episode" 
              />
              <MetricCard 
                title="Policy Violations" 
                value={riq.policy_violations.toString()} 
                tooltip="Deterministic safety bounds broken" 
              />
            </div>
          </div>
        );
      })()}

      {/* Leaderboard */}
      <div className="bg-card border rounded-xl overflow-hidden mt-8 shadow-sm">
        <div className="p-5 border-b bg-muted/30">
            <h3 className="text-lg font-medium text-foreground">RecoveryIQ vs Baselines</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-muted-foreground">
            <thead className="bg-muted/50 text-muted-foreground font-medium text-xs uppercase tracking-wider">
              <tr>
                <th className="px-6 py-4">Strategy</th>
                <th className="px-6 py-4 text-right">Recovery Rate</th>
                <th className="px-6 py-4 text-right">Net Recovery Value</th>
                <th className="px-6 py-4 text-right">Contacts</th>
                <th className="px-6 py-4 text-right">Retries</th>
                <th className="px-6 py-4 text-right">Policy Violations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {summary.strategies.map((strategy) => (
                <tr key={strategy.id} className={`hover:bg-muted/40 transition-colors ${strategy.id === riq.id ? "bg-muted font-medium text-foreground" : ""}`}>
                  <td className="px-6 py-4 whitespace-nowrap flex items-center gap-2">
                    {strategy.name}
                    {strategy.id === riq.id && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold bg-blue-500/20 text-blue-400">
                            V2
                        </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">{(strategy.recovery_rate * 100).toFixed(2)}%</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right" title={formatMinorINRToFull(strategy.simulated_net_value_minor)}>
                      {formatMinorINRToCompact(strategy.simulated_net_value_minor)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">{strategy.contacts > 0 ? strategy.contacts.toLocaleString() : "—"}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">{strategy.retries > 0 ? strategy.retries.toLocaleString() : "—"}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">{strategy.policy_violations.toString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Methodology Drawer */}
      <details className="group border rounded-xl bg-card shadow-sm">
        <summary className="flex cursor-pointer items-center justify-between p-5 font-medium text-foreground hover:text-foreground/80">
            How was this measured?
            <span className="text-muted-foreground transition-transform group-open:rotate-180">▼</span>
        </summary>
        <div className="p-5 border-t text-muted-foreground text-sm leading-relaxed">
            <p>
                Evaluation is based on {summary.episodes.toLocaleString()} sealed simulated episodes using paired randomness.
                The Sequential Policy V2 and Recovery Model V2 are frozen and evaluated against a hidden simulator ground truth
                unavailable to the policy. Results reflect full-horizon evaluation using rigorous validation/final separation.
            </p>
            <p className="mt-2 text-xs text-muted-foreground/70">Artifact: {summary.evaluation_name}</p>
        </div>
      </details>
    </section>
  );
}

function MetricCard({ title, value, tooltip, highlight = false }: { title: string; value: string; tooltip?: string; highlight?: boolean }) {
  return (
    <div className={`p-6 rounded-2xl border flex flex-col justify-center h-full shadow-sm ${highlight ? "bg-emerald-500/10 border-emerald-500/20" : "bg-card"}`} title={tooltip}>
      <p className={`text-sm font-medium mb-2 ${highlight ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground"}`}>{title}</p>
      <p className={`text-3xl font-semibold tracking-tight ${highlight ? "text-emerald-700 dark:text-emerald-400" : "text-foreground"}`}>{value}</p>
    </div>
  );
}
