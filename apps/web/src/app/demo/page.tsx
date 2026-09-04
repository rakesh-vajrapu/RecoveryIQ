"use client";

import { useEffect, useState, useCallback } from "react";
import { PageHeader } from "@/components/page-header";
import { getReplayTrace, TraceData } from "@/lib/api";
import { formatMoney } from "@/lib/format";

// Inline UI wrappers
const Card = ({ children, className = "", onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) => (
  <div onClick={onClick} className={`rounded-xl border border-zinc-800 bg-zinc-950/50 shadow-sm ${className} ${onClick ? 'cursor-pointer hover:border-emerald-500/50 transition-colors' : ''}`}>
    {children}
  </div>
);
const CardHeader = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`flex flex-col space-y-1.5 p-6 ${className}`}>{children}</div>
);
const CardTitle = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <h3 className={`font-semibold leading-none tracking-tight ${className}`}>{children}</h3>
);
const CardContent = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`p-6 pt-0 ${className}`}>{children}</div>
);
const Badge = ({ children, variant = "default", className = "" }: { children: React.ReactNode; variant?: "default" | "destructive" | "outline" | "safety"; className?: string }) => {
  const vclass = variant === "destructive" ? "bg-red-500/10 text-red-500 border-red-500/20" 
               : variant === "outline" ? "border border-zinc-700 text-zinc-300"
               : variant === "safety" ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
               : "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
  return <div className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors ${vclass} ${className}`}>{children}</div>;
};

const PHASES = [
  "OBSERVE",
  "PREDICT",
  "OPTIMIZE",
  "AUTHORIZE",
  "OUTCOME",
  "REPLAN"
];

function formatActionLabel(label: string) {
  const mapping: Record<string, string> = {
    "RETRY_NOW": "Retry Now",
    "RETRY_LATER_2H": "Retry Later · 2h",
    "RETRY_LATER_6H": "Retry Later · 6h",
    "RETRY_LATER_12H": "Retry Later · 12h",
    "RETRY_LATER_24H": "Retry Later · 24h",
    "CREATE_PAYMENT_LINK": "Create Payment Link",
    "SEND_NUDGE": "Send Nudge",
    "REQUEST_PAYMENT_METHOD_UPDATE": "Request Method Update",
    "OFFER_ALTERNATE_METHOD": "Offer Alternate Method",
  };
  return mapping[label] || label;
}

export default function ReplayLabPage() {
  const [selectedPreset, setSelectedPreset] = useState<string>("successful-adaptive-trace-v2");
  const [trace, setTrace] = useState<TraceData | null>(null);
  const [loading, setLoading] = useState(false);

  // Playback state
  const [currentDecisionIndex, setCurrentDecisionIndex] = useState(0);
  const [currentPhaseIndex, setCurrentPhaseIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMicroscope, setIsMicroscope] = useState(false);

  useEffect(() => {
    if (!selectedPreset) return;
    
    // We shouldn't trigger loading state from inside the effect without a mount check, 
    // but in this simple demo component we can safely load data. To appease the linter, 
    // we use a boolean flag or just let it be since it's a demo. Wait, the linter says:
    // "Calling setState synchronously within an effect can trigger cascading renders"
    
    let isMounted = true;
    
    getReplayTrace(selectedPreset)
      .then((data) => {
        if (isMounted) {
          setTrace(data);
          setLoading(false);
          // Reset playback
          setCurrentDecisionIndex(0);
          setCurrentPhaseIndex(0);
          setIsPlaying(false);
        }
      });
      
    return () => { isMounted = false; };
  }, [selectedPreset]);

  const handleNextStep = useCallback(() => {
    if (!trace) return;
    if (currentPhaseIndex < 4) { // Up to OUTCOME
      setCurrentPhaseIndex(p => p + 1);
    } else if (currentPhaseIndex === 4) {
      // At OUTCOME, decide if there is a next decision or if it's the end
      if (currentDecisionIndex < trace.decisions.length - 1) {
        setCurrentPhaseIndex(5); // REPLAN
      } else {
        setIsPlaying(false);
      }
    } else if (currentPhaseIndex === 5) { // At REPLAN
      setCurrentDecisionIndex(d => d + 1);
      setCurrentPhaseIndex(0); // Back to OBSERVE
    }
  }, [trace, currentPhaseIndex, currentDecisionIndex]);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isPlaying && trace) {
      timer = setTimeout(() => {
        handleNextStep();
      }, 800);
    }
    return () => clearTimeout(timer);
  }, [isPlaying, currentPhaseIndex, currentDecisionIndex, trace, handleNextStep]);

  const handlePrevStep = () => {
    if (currentPhaseIndex > 0) {
      setCurrentPhaseIndex(p => p - 1);
    } else if (currentDecisionIndex > 0) {
      setCurrentDecisionIndex(d => d - 1);
      setCurrentPhaseIndex(4); // Back to previous OUTCOME
    }
  };

  const handleReset = () => {
    setCurrentDecisionIndex(0);
    setCurrentPhaseIndex(0);
    setIsPlaying(false);
  };

  const renderPresetCards = () => (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <Card 
        onClick={() => { setSelectedPreset("successful-adaptive-trace-v2"); setIsMicroscope(false); }}
        className={selectedPreset === "successful-adaptive-trace-v2" && !isMicroscope ? "border-emerald-500/50 bg-emerald-950/10" : ""}
      >
        <CardHeader>
          <CardTitle>Adaptive Recovery</CardTitle>
          <div className="text-sm text-zinc-400 mt-2">Watch RecoveryIQ replan after failed interventions and eventually recover.</div>
        </CardHeader>
      </Card>
      
      <Card 
        onClick={() => { setSelectedPreset("bounded-failure-trace-v2"); setIsMicroscope(false); }}
        className={selectedPreset === "bounded-failure-trace-v2" && !isMicroscope ? "border-emerald-500/50 bg-emerald-950/10" : ""}
      >
        <CardHeader>
          <CardTitle>Bounded Safety Stop</CardTitle>
          <div className="text-sm text-zinc-400 mt-2">Watch RecoveryIQ stop after its autonomous intervention budget is exhausted.</div>
        </CardHeader>
      </Card>

      <Card 
        onClick={() => { setSelectedPreset("successful-adaptive-trace-v2"); setIsMicroscope(true); }}
        className={isMicroscope ? "border-emerald-500/50 bg-emerald-950/10" : ""}
      >
        <CardHeader>
          <CardTitle>Decision Microscope</CardTitle>
          <div className="text-sm text-zinc-400 mt-2">Inspect one frozen policy decision in detail.</div>
        </CardHeader>
      </Card>
    </div>
  );

  if (loading || !trace) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="TRY RECOVERYIQ" title="RecoveryIQ Replay Lab" description="Replay frozen RecoveryIQ decisions from sealed evaluation evidence." />
        {renderPresetCards()}
        <div className="text-zinc-400 p-8 text-center animate-pulse">Loading trace evidence...</div>
      </div>
    );
  }

  const decision = trace.decisions[currentDecisionIndex];
  const isFinalDecision = currentDecisionIndex === trace.decisions.length - 1;
  const showOutcome = currentPhaseIndex >= 4;
  const isRecovered = trace.final.recovered;
  const showFinalOutcome = showOutcome && isFinalDecision;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="TRY RECOVERYIQ"
        title="RecoveryIQ Replay Lab"
        description="Replay frozen RecoveryIQ decisions from sealed evaluation evidence."
      />

      {renderPresetCards()}

      <div className="flex items-center justify-between p-4 bg-zinc-900/50 border border-zinc-800 rounded-lg">
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-[10px] tracking-widest uppercase border-emerald-500/20 text-emerald-400 bg-emerald-500/10">
            SEALED · SIMULATED REPLAY
          </Badge>
          <span className="text-sm text-zinc-400">Interactive replay of frozen evaluation evidence. No new inference, provider action, or real money.</span>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs font-mono text-zinc-500 justify-center p-4 border border-zinc-800 bg-zinc-950/30 rounded-xl my-8">
        <span>MODEL V2 <br/><span className="text-[10px] text-zinc-600">(Recorded calibrated probabilities)</span></span>
        <span>→</span>
        <span>ERV <br/><span className="text-[10px] text-zinc-600">(Economic ranking)</span></span>
        <span>→</span>
        <span>POLICY V2 <br/><span className="text-[10px] text-zinc-600">(Deterministic authority)</span></span>
      </div>

      {isMicroscope ? (
        <div className="space-y-6 animate-in fade-in duration-500">
          <div className="text-center">
            <h2 className="text-xl font-bold tracking-tight text-emerald-500">DECISION MICROSCOPE</h2>
            <p className="text-zinc-400 text-sm mt-2">Inspect one frozen policy decision in detail. (This is not a third independent trajectory).</p>
          </div>
          
          <Card className="overflow-hidden border-zinc-800/50 bg-zinc-900/20">
            <CardHeader className="bg-zinc-900/40 border-b border-zinc-800/50 pb-4">
               <CardTitle className="text-lg text-emerald-500">Frozen Policy Authorization</CardTitle>
               <div className="mt-2 text-sm text-zinc-400">
                 <span className="font-semibold text-zinc-200">Selected Action:</span> <Badge>{formatActionLabel(decision.selected_action)}</Badge>
                 <br />
                 <span className="font-semibold text-zinc-200">Policy Reason:</span> {decision.policy_checks?.reason || "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV"}
               </div>
            </CardHeader>
            <CardContent className="p-0">
               <div className="w-full overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-zinc-900/60 text-zinc-400 text-xs uppercase tracking-wider">
                    <tr>
                      <th className="px-6 py-3 text-left font-medium">Candidate Action</th>
                      <th className="px-6 py-3 text-right font-medium">P(recovery)</th>
                      <th className="px-6 py-3 text-right font-medium">Incremental ERV</th>
                      <th className="px-6 py-3 text-right font-medium">Stage Support</th>
                      <th className="px-6 py-3 text-right font-medium">Calibration Support</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {decision.candidates.map((cand, i) => {
                      const isSelected = cand.label === decision.selected_action;
                      return (
                        <tr key={i} className={`group transition-colors ${isSelected ? "bg-emerald-900/20 border-l-2 border-emerald-500" : "hover:bg-zinc-800/30"}`}>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex flex-col">
                              <span className={`text-sm ${isSelected ? "text-emerald-400 font-bold" : "text-zinc-300"}`}>
                                {formatActionLabel(cand.label)}
                              </span>
                              <span className="text-[10px] font-mono text-zinc-600">{cand.label}</span>
                              {isSelected && (
                                <span className="mt-1 inline-flex w-fit items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500 text-zinc-950 uppercase tracking-widest shadow-sm">
                                  Selected
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-zinc-300">
                            {(cand.probability * 100).toFixed(2)}%
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right font-mono">
                            <span className={cand.incremental_erv_minor > 0 ? "text-emerald-400" : "text-zinc-500"}>
                              {cand.incremental_erv_minor > 0 ? "+" : ""}{formatMoney(cand.incremental_erv_minor, "INR")}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-zinc-400">
                            {cand.action_stage_support}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-zinc-400">
                            {cand.calibration_bin_support}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="space-y-6 animate-in fade-in duration-500">
          <div className="flex gap-4 mb-8 justify-center">
             {PHASES.map((phase, idx) => (
                <div key={phase} className={`flex items-center gap-2 ${idx <= currentPhaseIndex ? 'text-emerald-500' : 'text-zinc-600'}`}>
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${idx === currentPhaseIndex ? 'border-emerald-500 bg-emerald-500/20' : idx < currentPhaseIndex ? 'border-emerald-500 bg-transparent' : 'border-zinc-700 bg-transparent'}`}>
                    {idx + 1}
                  </span>
                  <span className="text-xs font-mono tracking-wider">{phase}</span>
                </div>
             ))}
          </div>

          <div className="flex gap-4 justify-center mb-8">
            <button onClick={handlePrevStep} disabled={currentPhaseIndex === 0 && currentDecisionIndex === 0} className="px-4 py-2 bg-zinc-800 rounded text-sm disabled:opacity-50 hover:bg-zinc-700 transition-colors">Previous Step</button>
            <button onClick={() => setIsPlaying(!isPlaying)} disabled={showFinalOutcome} className={`px-4 py-2 rounded text-sm font-bold transition-colors disabled:opacity-50 ${isPlaying ? 'bg-amber-600 hover:bg-amber-500 text-white' : 'bg-emerald-600 hover:bg-emerald-500 text-white'}`}>
              {isPlaying ? "Pause Replay" : "Play Replay"}
            </button>
            <button onClick={handleNextStep} disabled={showFinalOutcome} className="px-4 py-2 bg-zinc-800 rounded text-sm disabled:opacity-50 hover:bg-zinc-700 transition-colors">Next Step</button>
            <button onClick={handleReset} className="px-4 py-2 bg-zinc-800 rounded text-sm text-red-400 hover:bg-zinc-700 transition-colors">Reset</button>
          </div>

          {isPlaying && (
            <div className="text-center text-amber-500 text-xs font-mono tracking-widest animate-pulse mb-4">
              REPLAYING FROZEN EVIDENCE
            </div>
          )}

          {currentPhaseIndex === 0 && currentDecisionIndex === 0 && (
            <Card className="border-emerald-500/30">
              <CardHeader>
                <CardTitle>Initial Failure Context</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-zinc-300">
                <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                  <span>Amount:</span>
                  <span className="font-mono text-zinc-100">{formatMoney(trace.initial_failure.amount_minor, "INR")}</span>
                </div>
                <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                  <span>Payment Method:</span>
                  <span className="font-mono text-zinc-100">{trace.initial_failure.payment_method}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Failure:</span>
                  <span className="font-mono text-amber-400">{trace.initial_failure.failure_reason}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {currentPhaseIndex > 0 && (
            <Card className="overflow-hidden border-zinc-800/50 bg-zinc-900/20">
              <CardHeader className="bg-zinc-900/40 border-b border-zinc-800/50 pb-4">
                <CardTitle className="text-lg text-emerald-500">Decision {decision.decision_index}</CardTitle>
                <div className="text-sm text-zinc-500 font-mono mt-1 flex gap-4">
                  <span>Elapsed: {decision.observable_context.elapsed_hours}h</span>
                  <span>Previous Action: {decision.observable_context.last_action}</span>
                  <span>Previous Result: {decision.observable_context.previous_result}</span>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                 <div className="w-full overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-900/60 text-zinc-400 text-xs uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3 text-left font-medium">Candidate Action</th>
                        <th className="px-6 py-3 text-right font-medium">P(recovery)</th>
                        <th className="px-6 py-3 text-right font-medium">Incremental ERV</th>
                        <th className="px-6 py-3 text-right font-medium">Support</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {decision.candidates.map((cand, i) => {
                        const isSelected = cand.label === decision.selected_action;
                        return (
                          <tr key={i} className={`group transition-colors ${(isSelected && currentPhaseIndex >= 3) ? "bg-emerald-900/20 border-l-2 border-emerald-500" : "hover:bg-zinc-800/30"}`}>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="flex flex-col">
                                <span className={`text-sm ${(isSelected && currentPhaseIndex >= 3) ? "text-emerald-400 font-bold" : "text-zinc-300"}`}>
                                  {formatActionLabel(cand.label)}
                                </span>
                                <span className="text-[10px] font-mono text-zinc-600">{cand.label}</span>
                                {(isSelected && currentPhaseIndex >= 3) && (
                                  <span className="mt-1 inline-flex w-fit items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500 text-zinc-950 uppercase tracking-widest shadow-sm">
                                    Selected
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-zinc-300">
                              {currentPhaseIndex >= 1 ? `${(cand.probability * 100).toFixed(2)}%` : "—"}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right font-mono">
                              {currentPhaseIndex >= 2 ? (
                                <span className={cand.incremental_erv_minor > 0 ? "text-emerald-400" : "text-zinc-500"}>
                                  {cand.incremental_erv_minor > 0 ? "+" : ""}{formatMoney(cand.incremental_erv_minor, "INR")}
                                </span>
                              ) : "—"}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-zinc-400">
                              {cand.supported ? "SUPPORTED" : "UNSUPPORTED"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
              {currentPhaseIndex >= 3 && (
                <div className="p-4 bg-zinc-900 border-t border-zinc-800 text-sm">
                  <span className="font-bold text-zinc-300">Why this action?</span><br />
                  <span className="text-zinc-400 text-xs">Sequential Policy V2 authorized the supported feasible action with the maximum positive incremental ERV. (Reason: {decision.policy_checks?.reason || "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV"})</span>
                </div>
              )}
            </Card>
          )}

          {currentPhaseIndex === 5 && !isFinalDecision && (
            <Card className="border-amber-500/30">
              <CardHeader>
                <CardTitle className="text-amber-500">RECORDED SIMULATED OUTCOME</CardTitle>
                <div className="text-sm font-mono text-amber-400 mt-2">FAILED</div>
              </CardHeader>
            </Card>
          )}

          {showFinalOutcome && (
            <Card className={isRecovered ? "border-emerald-500/50 bg-emerald-950/20" : "border-amber-500/50 bg-amber-950/20"}>
              <CardHeader>
                <CardTitle className={isRecovered ? "text-emerald-400 text-2xl" : "text-amber-400 text-2xl"}>
                  {isRecovered ? "SIMULATED RECOVERY" : "BOUNDED AUTONOMY WORKED AS DESIGNED"}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-zinc-300">
                {!isRecovered && (
                  <div className="mb-4">
                    <Badge variant="safety" className="text-sm px-3 py-1 mr-2">STOP</Badge>
                    <Badge variant="safety" className="text-sm px-3 py-1">MAX_INTERVENTIONS</Badge>
                  </div>
                )}
                <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                  <span>Status:</span>
                  <span className={`font-bold ${isRecovered ? "text-emerald-500" : "text-amber-500"}`}>{trace.final.termination}</span>
                </div>
                {isRecovered && (
                  <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                    <span>Recovered Amount:</span>
                    <span className="font-mono text-zinc-100">{formatMoney(trace.final.recovered_amount_minor, "INR")}</span>
                  </div>
                )}
                <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                  <span>Autonomous Interventions Used:</span>
                  <span className="font-mono text-zinc-100">{trace.final.action_count}</span>
                </div>
                {!isRecovered && trace.final.no_fourth_autonomous_action && (
                  <div className="text-amber-500 text-xs font-bold tracking-widest mt-4">NO FOURTH AUTONOMOUS ACTION ALLOWED</div>
                )}
                {isRecovered && (
                  <>
                    <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                      <span>Total Intervention Cost:</span>
                      <span className="font-mono text-zinc-100">{formatMoney(trace.final.total_intervention_cost_minor, "INR")}</span>
                    </div>
                    <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                      <span>Total Friction Cost:</span>
                      <span className="font-mono text-zinc-100">{formatMoney(trace.final.total_friction_cost_minor, "INR")}</span>
                    </div>
                    <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                      <span>Simulated Net Recovery Value:</span>
                      <span className="font-mono text-emerald-400 font-bold">{formatMoney(trace.final.simulated_net_recovery_value_minor, "INR")}</span>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}

          {showFinalOutcome && (
            <div className="mt-12 p-6 border border-zinc-800 bg-zinc-950/80 rounded-xl text-center">
              <h3 className="text-lg font-bold text-zinc-300 mb-2 tracking-widest">PROVIDER EXECUTION NOT REPLAYED HERE</h3>
              <p className="text-sm text-zinc-500 mb-4">Replay Lab ends at policy evidence. Razorpay provider execution is demonstrated separately in Test Mode evidence.</p>
              <a href="/integrations/razorpay" className="inline-flex items-center justify-center px-4 py-2 border border-emerald-500/50 text-emerald-500 rounded hover:bg-emerald-500/10 transition-colors text-sm font-medium">
                View Razorpay Test Evidence
              </a>
            </div>
          )}
        </div>
      )}

      <div className="pt-12 mt-12 border-t border-zinc-800/50 grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
         <a href="/decision-trace" className="text-sm text-zinc-400 hover:text-emerald-400 transition-colors">Inspect Decision Trace</a>
         <a href="/batch-explorer" className="text-sm text-zinc-400 hover:text-emerald-400 transition-colors">Explore 27,406 Sealed Episodes</a>
         <a href="/integrations/razorpay" className="text-sm text-zinc-400 hover:text-emerald-400 transition-colors">View Razorpay Test Evidence</a>
         <a href="/evaluation" className="text-sm text-zinc-400 hover:text-emerald-400 transition-colors">Open Evaluation Lab</a>
      </div>
    </div>
  );
}
