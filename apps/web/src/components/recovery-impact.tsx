"use client";

import { EvaluationSummary } from "@/lib/api";
import { formatMinorINRToCompact, formatMinorINRToFull } from "@/lib/currency";

export function RecoveryImpact({ summary }: { summary: EvaluationSummary | null }) {
  if (!summary) {
    return (
      <section className="mt-12 bg-white/5 border border-white/10 rounded-2xl p-8 backdrop-blur-md">
        <h2 className="text-xl font-medium tracking-tight text-white/90">Recovery Impact</h2>
        <div className="mt-6 flex flex-col items-center justify-center py-12 text-center text-white/60">
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
          <h2 className="text-2xl font-semibold tracking-tight text-white">RECOVERY IMPACT</h2>
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            SEALED &middot; SIMULATED
          </span>
        </div>
        <p className="text-white/70 max-w-3xl leading-relaxed">
          Across {summary.episodes.toLocaleString()} sealed simulated recovery episodes, 
          {riq.name} achieved {(riq.recovery_rate * 100).toFixed(2)}% recovery and generated{" "}
          <span className="text-white font-medium">{formatMinorINRToCompact(riq.simulated_net_value_minor)}</span>{" "}
          simulated net recovery value. Compared with {baseline.name}, RecoveryIQ produced{" "}
          <span className="text-emerald-400 font-medium">+{formatMinorINRToCompact(incValue)}</span> incremental simulated net value.
        </p>
        {tradeOffStory && (
            <p className="text-white/60 text-sm max-w-3xl mt-2 italic">{tradeOffStory}</p>
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
          <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden mt-8 p-5">
            <h3 className="text-sm font-bold tracking-widest text-white/50 uppercase mb-4">Decision Quality Audit</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <MetricCard 
                title="Economic Efficiency" 
                value={`${efficiency.toFixed(1)}%`} 
                tooltip="Simulated Net Value vs Hidden Oracle optimal" 
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
      <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden mt-8">
        <div className="p-5 border-b border-white/10 bg-white/[0.02]">
            <h3 className="text-lg font-medium text-white/90">RecoveryIQ vs Baselines</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-white/70">
            <thead className="bg-white/5 text-white/50 font-medium text-xs uppercase tracking-wider">
              <tr>
                <th className="px-6 py-4">Strategy</th>
                <th className="px-6 py-4 text-right">Recovery Rate</th>
                <th className="px-6 py-4 text-right">Net Recovery Value</th>
                <th className="px-6 py-4 text-right">Contacts</th>
                <th className="px-6 py-4 text-right">Retries</th>
                <th className="px-6 py-4 text-right">Policy Violations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {summary.strategies.map((strategy) => (
                <tr key={strategy.id} className={`hover:bg-white/[0.02] transition-colors ${strategy.id === riq.id ? "bg-white/10 font-medium text-white" : ""}`}>
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
      <details className="group border border-white/10 rounded-xl bg-white/5">
        <summary className="flex cursor-pointer items-center justify-between p-5 font-medium text-white/80 hover:text-white">
            How was this measured?
            <span className="text-white/40 transition-transform group-open:rotate-180">▼</span>
        </summary>
        <div className="p-5 border-t border-white/10 text-white/60 text-sm leading-relaxed">
            <p>
                Evaluation is based on {summary.episodes.toLocaleString()} sealed simulated episodes using paired randomness.
                The Sequential Policy V2 and Recovery Model V2 are frozen and evaluated against a hidden simulator ground truth
                unavailable to the policy. Results reflect full-horizon evaluation using rigorous validation/final separation.
            </p>
            <p className="mt-2 text-xs text-white/40">Artifact: {summary.evaluation_name}</p>
        </div>
      </details>
    </section>
  );
}

function MetricCard({ title, value, tooltip, highlight = false }: { title: string; value: string; tooltip?: string; highlight?: boolean }) {
  return (
    <div className={`p-6 rounded-2xl border backdrop-blur-sm flex flex-col justify-center h-full ${highlight ? "bg-emerald-500/10 border-emerald-500/20" : "bg-white/5 border-white/10"}`} title={tooltip}>
      <p className={`text-sm font-medium mb-2 ${highlight ? "text-emerald-400/80" : "text-white/50"}`}>{title}</p>
      <p className={`text-3xl font-semibold tracking-tight ${highlight ? "text-emerald-400" : "text-white/90"}`}>{value}</p>
    </div>
  );
}
