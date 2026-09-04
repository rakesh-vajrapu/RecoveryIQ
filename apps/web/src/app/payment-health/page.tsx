export const dynamic = 'force-dynamic';
import { Activity, AlertTriangle, CheckCircle2, ShieldAlert, Zap, BookOpen, AlertOctagon, BarChart3, HelpCircle } from "lucide-react";
import { getPaymentHealthSummary } from "@/lib/api";
import { PageHeader } from "@/components/page-header";

export default async function PaymentHealthPage() {
  let summary = null;
  try {
    summary = await getPaymentHealthSummary();
  } catch {
    // Graceful unavailable state
    return (
      <div className="p-8 text-center text-muted-foreground">
        <AlertTriangle className="mx-auto mb-4 h-8 w-8 text-amber-500" />
        <h2 className="text-xl font-bold text-foreground mb-2">Simulated Data Unavailable</h2>
        <p>The read-only API endpoint for simulated payment health is currently unreachable.</p>
      </div>
    );
  }

  const { final_context, episodes } = summary;
  const globalHealth = final_context.global_health;
  const issuerHealth = final_context.issuer_health;
  const methodHealth = final_context.method_health;
  
  // Helper to render health badge
  const renderHealthBadge = (level: string) => {
    switch(level) {
      case "HEALTHY":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><CheckCircle2 className="w-3.5 h-3.5" /> HEALTHY</span>;
      case "WATCH":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20"><AlertTriangle className="w-3.5 h-3.5" /> WATCH</span>;
      case "CONFIRMED":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-red-500/10 text-red-400 border border-red-500/20"><AlertOctagon className="w-3.5 h-3.5 animate-pulse" /> CONFIRMED</span>;
      default:
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-gray-500/10 text-gray-400 border border-gray-500/20">{level}</span>;
    }
  };

  const incident = episodes[0]; // The simulated incident example

  return (
    <>
      <PageHeader 
        eyebrow="SIMULATED PAYMENT HEALTH" 
        title="Degradation Intelligence V2.0" 
        description="A read-only visualization of sealed simulated degradation data. Detector signals are purely advisory and cannot override policy execution." 
        icon={Activity} 
      />

      <div className="space-y-12 pb-12 mt-8">
        {/* SECTION A: NETWORK HEALTH OVERVIEW */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-5 h-5 text-cyan-500" />
            <h2 className="text-lg font-bold tracking-widest text-foreground uppercase">Network Health Overview</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-card border rounded-xl p-5 shadow-sm">
              <p className="text-sm text-muted-foreground mb-1">Scopes Evaluated</p>
              <p className="text-2xl font-semibold text-foreground">3</p>
              <p className="text-xs text-muted-foreground/70 mt-2">Global, Issuer, Method</p>
            </div>
            <div className="bg-card border rounded-xl p-5 relative overflow-hidden shadow-sm">
              <div className="absolute top-0 right-0 p-4 opacity-10"><CheckCircle2 className="w-16 h-16 text-emerald-500" /></div>
              <p className="text-sm text-emerald-600 dark:text-emerald-400/80 mb-1">Healthy Scopes</p>
              <p className="text-2xl font-semibold text-foreground">3</p>
              <p className="text-xs text-muted-foreground/70 mt-2">Current Final Context</p>
            </div>
            <div className="bg-card border rounded-xl p-5 relative overflow-hidden shadow-sm">
              <div className="absolute top-0 right-0 p-4 opacity-10"><AlertOctagon className="w-16 h-16 text-red-500" /></div>
              <p className="text-sm text-red-600 dark:text-red-400/80 mb-1">Historical Incidents</p>
              <p className="text-2xl font-semibold text-foreground">{episodes.length}</p>
              <p className="text-xs text-muted-foreground/70 mt-2">Simulated Episodes</p>
            </div>
            <div className="bg-card border rounded-xl p-5 relative overflow-hidden shadow-sm">
              <div className="absolute top-0 right-0 p-4 opacity-10"><ShieldAlert className="w-16 h-16 text-cyan-500" /></div>
              <p className="text-sm text-cyan-600 dark:text-cyan-400/80 mb-1">Policy Overrides</p>
              <p className="text-2xl font-semibold text-foreground">0</p>
              <p className="text-xs text-cyan-600 dark:text-cyan-400/60 mt-2 font-mono tracking-tight uppercase">Detector is advisory only</p>
            </div>
          </div>
        </section>

        {/* SECTION B: SCOPE HEALTH MATRIX */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
            <h2 className="text-lg font-bold tracking-widest text-foreground uppercase">Scope Health Matrix</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { title: "GLOBAL HEALTH", data: globalHealth },
              { title: "ISSUER HEALTH", data: issuerHealth },
              { title: "PAYMENT METHOD HEALTH", data: methodHealth }
            ].map((scope, i) => (
              <div key={i} className="bg-card border rounded-2xl overflow-hidden shadow-xl flex flex-col">
                <div className="p-4 border-b bg-muted/30 flex items-center justify-between">
                  <h3 className="text-sm font-bold text-muted-foreground">{scope.title}</h3>
                  {scope.data.scope.issuer ? <span className="text-[10px] bg-muted px-2 py-0.5 rounded text-muted-foreground font-mono">{scope.data.scope.issuer}</span> : null}
                  {scope.data.scope.payment_method ? <span className="text-[10px] bg-muted px-2 py-0.5 rounded text-muted-foreground font-mono">{scope.data.scope.payment_method}</span> : null}
                </div>
                <div className="p-5 flex-1 flex flex-col justify-center items-center py-8">
                  <div className="mb-4">
                    {renderHealthBadge(scope.data.evidence_level)}
                  </div>
                  <div className="grid grid-cols-2 gap-x-8 gap-y-4 w-full px-4 text-center mt-4 border-t pt-6">
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Baseline Success</p>
                      <p className="text-lg font-mono text-foreground">{(scope.data.baseline_success_probability * 100).toFixed(1)}%</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Baseline Attempts</p>
                      <p className="text-lg font-mono text-foreground">{scope.data.baseline_attempts}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* SECTION C & D: SIMULATED INCIDENT EXAMPLE & DEGRADATION EVIDENCE */}
        {incident && (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <AlertOctagon className="w-5 h-5 text-rose-500 dark:text-rose-400" />
              <h2 className="text-lg font-bold tracking-widest text-foreground uppercase">Simulated Incident Example</h2>
            </div>
            <div className="bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-500/20 rounded-2xl overflow-hidden">
              <div className="p-6 border-b border-rose-200 dark:border-rose-500/10 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-rose-900 dark:text-rose-100 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span>
                    Issuer / Payment Method Degradation
                  </h3>
                  <p className="text-xs text-rose-600/70 dark:text-rose-200/50 mt-1 font-mono">{incident.incident_id} • Detected {new Date(incident.confirmed_at).toLocaleString()}</p>
                </div>
                <div className="flex gap-2">
                  <span className="text-[10px] px-2 py-1 bg-muted border rounded font-mono text-muted-foreground">Scope: {incident.scope.level}</span>
                  {incident.scope.issuer && <span className="text-[10px] px-2 py-1 bg-rose-500/10 border border-rose-500/20 rounded font-mono text-rose-600 dark:text-rose-300">Issuer: {incident.scope.issuer}</span>}
                  {incident.scope.payment_method && <span className="text-[10px] px-2 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded font-mono text-indigo-600 dark:text-indigo-300">Method: {incident.scope.payment_method}</span>}
                </div>
              </div>
              
              <div className="grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-rose-200 dark:divide-rose-500/10">
                {/* Evidence Tier */}
                <div className="p-6">
                  <p className="text-[10px] font-bold text-rose-700/60 dark:text-rose-400/60 uppercase tracking-widest mb-4">Degradation Evidence</p>
                  
                  <div className="space-y-6">
                    <div>
                      <div className="flex justify-between items-end mb-1">
                        <p className="text-xs text-muted-foreground">Expected / Baseline Success</p>
                        <p className="text-sm font-mono text-foreground">{(incident.baseline_success_probability * 100).toFixed(1)}%</p>
                      </div>
                      <div className="w-full bg-muted h-2 rounded-full overflow-hidden">
                        <div className="bg-emerald-500/50 h-full rounded-full" style={{ width: `${incident.baseline_success_probability * 100}%` }}></div>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-1">{incident.baseline_attempts} observations</p>
                    </div>
                    
                    <div>
                      <div className="flex justify-between items-end mb-1">
                        <p className="text-xs text-rose-800/70 dark:text-rose-300/70">Observed Success</p>
                        <p className="text-sm font-mono text-rose-600 dark:text-rose-400">
                          {(((incident.current_attempts - incident.current_failures) / incident.current_attempts) * 100).toFixed(1)}%
                        </p>
                      </div>
                      <div className="w-full bg-muted h-2 rounded-full overflow-hidden">
                        <div className="bg-rose-500 h-full rounded-full" style={{ width: `${((incident.current_attempts - incident.current_failures) / incident.current_attempts) * 100}%` }}></div>
                      </div>
                      <p className="text-[10px] text-rose-700/50 dark:text-rose-300/40 mt-1">{incident.current_attempts} observations ({incident.current_failures} failures)</p>
                    </div>

                    <div className="pt-4 border-t border-rose-200 dark:border-rose-500/10">
                      <div className="flex justify-between items-center">
                        <p className="text-xs text-muted-foreground">Performance Delta</p>
                        <p className="text-sm font-mono font-bold text-rose-600 dark:text-rose-400">
                          -{((incident.baseline_success_probability - ((incident.current_attempts - incident.current_failures) / incident.current_attempts)) * 100).toFixed(1)} pp
                        </p>
                      </div>
                      <div className="flex justify-between items-center mt-2">
                        <p className="text-xs text-muted-foreground">Evidence Tier</p>
                        {renderHealthBadge("CONFIRMED")}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Timeline */}
                <div className="p-6 lg:col-span-2 bg-rose-50/50 dark:bg-rose-950/5">
                  <p className="text-[10px] font-bold text-rose-700/60 dark:text-rose-400/60 uppercase tracking-widest mb-4">Signal Escalation Timeline</p>
                  <div className="relative pl-4 border-l border-border space-y-4 pb-2">
                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    {incident.transitions.map((t: any, i: number) => (
                      <div key={i} className="relative">
                        <div className={`absolute -left-[21px] w-2.5 h-2.5 rounded-full border-2 border-background ${t.evidence_level === 'CONFIRMED' ? 'bg-rose-500' : t.evidence_level === 'WATCH' ? 'bg-amber-500' : 'bg-emerald-500'}`}></div>
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-muted-foreground font-mono w-16">{new Date(t.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                          {renderHealthBadge(t.evidence_level)}
                          <span className="text-[10px] text-muted-foreground hidden sm:inline">LLR: {t.maximum_llr.toFixed(2)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* SECTION E: WHY THIS MATTERS FOR RECOVERY */}
          <section>
            <div className="bg-card border rounded-2xl p-6 h-full flex flex-col relative overflow-hidden shadow-sm">
              <div className="absolute -right-4 -top-4 w-32 h-32 bg-indigo-500/10 blur-3xl rounded-full"></div>
              <div className="flex items-center gap-2 mb-4 text-indigo-600 dark:text-indigo-400">
                <HelpCircle className="w-5 h-5" />
                <h3 className="text-sm font-bold tracking-widest uppercase">Why this matters for recovery</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed mb-6">
                A failed payment may not be an isolated customer problem. RecoveryIQ surfaces population-level evidence alongside case-level recovery reasoning to provide crucial context.
              </p>
              <div className="bg-muted/30 border rounded-xl p-4 flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 rounded-full bg-rose-500/10 flex items-center justify-center border border-rose-500/20">
                    <span className="text-rose-600 dark:text-rose-400 text-xs font-bold">1</span>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-foreground">Individual View</p>
                    <p className="text-[10px] text-muted-foreground">Payment fails with <code className="text-rose-600 dark:text-rose-300">TEMPORARY_NETWORK_ERROR</code></p>
                  </div>
                </div>
                <div className="w-0.5 h-4 bg-border ml-4 my-1"></div>
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 rounded-full bg-amber-500/10 flex items-center justify-center border border-amber-500/20">
                    <span className="text-amber-600 dark:text-amber-400 text-xs font-bold">2</span>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-foreground">Payment Health View</p>
                    <p className="text-[10px] text-muted-foreground">Issuer route is in <code className="text-amber-600 dark:text-amber-300">CONFIRMED DEGRADATION</code></p>
                  </div>
                </div>
                <div className="w-0.5 h-4 bg-border ml-4 my-1"></div>
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                    <span className="text-emerald-600 dark:text-emerald-400 text-xs font-bold">3</span>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-foreground">Recovery Implication</p>
                    <p className="text-[10px] text-muted-foreground">An immediate same-route retry may have lower strategic value. Degradation evidence informs operator/decision context.</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* SECTION F: METHODOLOGY / AUTHORITY */}
          <section className="space-y-6">
            <div className="bg-card border border-cyan-500/20 rounded-2xl p-6 relative overflow-hidden shadow-sm">
              <div className="absolute right-0 bottom-0 w-40 h-40 bg-cyan-500/5 blur-3xl rounded-full"></div>
              <div className="flex items-center gap-2 mb-4 text-cyan-600 dark:text-cyan-400">
                <ShieldAlert className="w-5 h-5" />
                <h3 className="text-sm font-bold tracking-widest uppercase">Detector Authority Boundary</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed mb-4">
                Detection confidence is intentionally separated from execution authority. RecoveryIQ uses degradation evidence for observability and advisory reasoning, while financial actions remain governed by deterministic recovery policy.
              </p>
              <div className="bg-cyan-500/10 border border-cyan-500/20 p-3 rounded-lg text-xs text-cyan-800 dark:text-cyan-200">
                <strong>Engineering Principle:</strong> Detector V2 failed its hard-policy safety gate during validation and therefore <strong>cannot</strong> autonomously select actions, change probabilities, or execute recovery.
              </div>
            </div>

            <div className="bg-card border rounded-2xl p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-4 text-muted-foreground">
                <BookOpen className="w-5 h-5" />
                <h3 className="text-sm font-bold tracking-widest uppercase">Hidden Truth Isolation</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                The detector and recovery policy operate only on observable payment evidence. Simulator incident ground truth is strictly withheld from the decision system to prevent leakage.
              </p>
              <div className="mt-4 flex gap-4 text-xs font-mono">
                <div><span className="text-muted-foreground/70 block mb-1">Detector Version</span><span className="text-foreground">2.0.0</span></div>
                <div><span className="text-muted-foreground/70 block mb-1">Config Hash</span><span className="text-foreground" title={summary.final_context?.configuration_hash}>{summary.final_context?.configuration_hash?.substring(0,8) || "50f0ca05"}</span></div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
