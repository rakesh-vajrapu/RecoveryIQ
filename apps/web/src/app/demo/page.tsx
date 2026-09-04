"use client";

import { useEffect, useState, useCallback } from "react";
import { ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { getReplayTrace } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Inline UI wrappers
const Card = ({ children, className = "", onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) => {
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cn("text-left w-full rounded-xl border bg-card shadow-sm transition-colors cursor-pointer hover:border-emerald-500/50 hover:shadow-md focus-visible:ring-2 focus-visible:ring-emerald-500 outline-none", className)}>
        {children}
      </button>
    );
  }
  return (
    <div className={cn("rounded-xl border bg-card shadow-sm", className)}>
      {children}
    </div>
  );
};

const CardHeader = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`flex flex-col space-y-1.5 p-6 ${className}`}>{children}</div>
);
const CardTitle = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <h3 className={`font-semibold leading-none tracking-tight text-foreground ${className}`}>{children}</h3>
);
const CardContent = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`p-6 pt-0 ${className}`}>{children}</div>
);
const Badge = ({ children, variant = "default", className = "" }: { children: React.ReactNode; variant?: "default" | "destructive" | "outline" | "safety"; className?: string }) => {
  const vclass = variant === "destructive" ? "bg-red-500/10 text-red-500 border-red-500/20" 
               : variant === "outline" ? "border text-muted-foreground"
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

// 20 EXACT SCENARIOS
const D1_CONTEXTS = [
  "TEMPORARY_NETWORK_ERROR", "ISSUER_UNAVAILABLE", "CUSTOMER_ACTION_REQUIRED", "AUTHENTICATION_FAILURE", 
  "INSUFFICIENT_FUNDS", "INSTRUMENT_EXPIRED", "UNKNOWN_TRANSIENT_ERROR", "MANDATE_INACTIVE"
];
const D1_ACTION_SETS = [
  {
    candidates: [
      { label: "RETRY_LATER_2H", probability: 0.88, incremental_erv_minor: 88000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "CREATE_PAYMENT_LINK", probability: 0.45, incremental_erv_minor: 45000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "SEND_NUDGE", probability: 0.20, incremental_erv_minor: 15000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "OFFER_ALTERNATE_METHOD", probability: 0.15, incremental_erv_minor: 10000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "CONTACT_SUPPORT", probability: 0.10, incremental_erv_minor: -2000, supported: false, action_stage_support: "No", calibration_bin_support: "No" },
      { label: "RETRY_NOW", probability: 0.05, incremental_erv_minor: -12000, supported: false, action_stage_support: "No", calibration_bin_support: "Yes" }
    ],
    selected_action: "RETRY_LATER_2H",
    policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
  },
  {
    candidates: [
      { label: "CREATE_PAYMENT_LINK", probability: 0.72, incremental_erv_minor: 72000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "RETRY_LATER_24H", probability: 0.35, incremental_erv_minor: 35000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "OFFER_ALTERNATE_METHOD", probability: 0.28, incremental_erv_minor: 28000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "SEND_NUDGE", probability: 0.22, incremental_erv_minor: 18000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "RETRY_LATER_2H", probability: 0.15, incremental_erv_minor: -5000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "MANUAL_REVIEW", probability: 0.08, incremental_erv_minor: -15000, supported: false, action_stage_support: "No", calibration_bin_support: "No" },
      { label: "RETRY_NOW", probability: 0.02, incremental_erv_minor: -20000, supported: false, action_stage_support: "No", calibration_bin_support: "Yes" }
    ],
    selected_action: "CREATE_PAYMENT_LINK",
    policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
  },
  {
    candidates: [
      { label: "OFFER_ALTERNATE_METHOD", probability: 0.91, incremental_erv_minor: 91000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "SEND_NUDGE", probability: 0.60, incremental_erv_minor: 60000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "CREATE_PAYMENT_LINK", probability: 0.44, incremental_erv_minor: 44000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "RETRY_LATER_2H", probability: 0.10, incremental_erv_minor: -8000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "RETRY_LATER_24H", probability: 0.08, incremental_erv_minor: -12000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "RETRY_NOW", probability: 0.04, incremental_erv_minor: -18000, supported: false, action_stage_support: "No", calibration_bin_support: "No" }
    ],
    selected_action: "OFFER_ALTERNATE_METHOD",
    policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
  },
  {
    candidates: [
      { label: "REQUEST_PAYMENT_METHOD_UPDATE", probability: 0.85, incremental_erv_minor: 85000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "CREATE_PAYMENT_LINK", probability: 0.50, incremental_erv_minor: 50000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "RETRY_LATER_24H", probability: 0.40, incremental_erv_minor: 40000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "OFFER_ALTERNATE_METHOD", probability: 0.32, incremental_erv_minor: 25000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "SEND_NUDGE", probability: 0.25, incremental_erv_minor: 18000, supported: true, action_stage_support: "Yes", calibration_bin_support: "Yes" },
      { label: "RETRY_NOW", probability: 0.08, incremental_erv_minor: -15000, supported: false, action_stage_support: "No", calibration_bin_support: "Yes" },
      { label: "CONTACT_SUPPORT", probability: 0.03, incremental_erv_minor: -25000, supported: false, action_stage_support: "No", calibration_bin_support: "No" }
    ],
    selected_action: "REQUEST_PAYMENT_METHOD_UPDATE",
    policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
  }
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const D1_SCENARIOS: any[] = Array.from({ length: 16 }).map((_, i) => ({
  id: `demo-d1-${i + 1}`,
  preset_name: "quick-recovery-demo",
  initial_failure: { amount_minor: 100000, payment_method: i % 2 === 0 ? "card" : "upi", failure_reason: D1_CONTEXTS[i % D1_CONTEXTS.length] },
  decisions: [
    {
      decision_index: 1,
      observable_context: { elapsed_hours: 0, last_action: "NONE", previous_result: "NONE" },
      ...D1_ACTION_SETS[i % 4]
    }
  ],
  final: { recovered: true, termination: "RECOVERED", recovered_amount_minor: 100000, action_count: 1 }
}));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const SYNTHETIC_SCENARIOS: any[] = [
  ...D1_SCENARIOS,
  {
    id: "demo-d2",
    initial_failure: { amount_minor: 100000, payment_method: "card", failure_reason: "AUTHENTICATION_FAILURE" },
    decisions: [
      {
        decision_index: 1,
        observable_context: { elapsed_hours: 0, last_action: "NONE", previous_result: "NONE" },
        candidates: [{ label: "CREATE_PAYMENT_LINK", probability: 0.6, incremental_erv_minor: 60000, supported: true }],
        selected_action: "CREATE_PAYMENT_LINK",
        policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
      },
      {
        decision_index: 2,
        observable_context: { elapsed_hours: 24, last_action: "CREATE_PAYMENT_LINK", previous_result: "FAILED" },
        candidates: [{ label: "OFFER_ALTERNATE_METHOD", probability: 0.7, incremental_erv_minor: 70000, supported: true }],
        selected_action: "OFFER_ALTERNATE_METHOD",
        policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
      }
    ],
    final: { recovered: true, termination: "RECOVERED", recovered_amount_minor: 100000, action_count: 2 }
  },
  {
    id: "demo-d3",
    initial_failure: { amount_minor: 100000, payment_method: "card", failure_reason: "INSTRUMENT_EXPIRED" },
    decisions: [
      {
        decision_index: 1,
        observable_context: { elapsed_hours: 0, last_action: "NONE", previous_result: "NONE" },
        candidates: [{ label: "REQUEST_PAYMENT_METHOD_UPDATE", probability: 0.5, incremental_erv_minor: 50000, supported: true }],
        selected_action: "REQUEST_PAYMENT_METHOD_UPDATE",
        policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
      },
      {
        decision_index: 2,
        observable_context: { elapsed_hours: 48, last_action: "REQUEST_PAYMENT_METHOD_UPDATE", previous_result: "FAILED" },
        candidates: [{ label: "CREATE_PAYMENT_LINK", probability: 0.4, incremental_erv_minor: 40000, supported: true }],
        selected_action: "CREATE_PAYMENT_LINK",
        policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
      },
      {
        decision_index: 3,
        observable_context: { elapsed_hours: 72, last_action: "CREATE_PAYMENT_LINK", previous_result: "FAILED" },
        candidates: [{ label: "RETRY_LATER_2H", probability: 0.6, incremental_erv_minor: 60000, supported: true }],
        selected_action: "RETRY_LATER_2H",
        policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
      }
    ],
    final: { recovered: true, termination: "RECOVERED", recovered_amount_minor: 100000, action_count: 3 }
  },
  {
    id: "demo-hr",
    initial_failure: { amount_minor: 100000, payment_method: "unknown", failure_reason: "UNKNOWN_TRANSIENT_ERROR" },
    decisions: [
      {
        decision_index: 1,
        observable_context: { elapsed_hours: 0, last_action: "NONE", previous_result: "NONE" },
        candidates: [{ label: "RETRY_LATER_24H", probability: 0.2, incremental_erv_minor: 20000, supported: true }],
        selected_action: "RETRY_LATER_24H",
        policy_checks: { reason: "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV" }
      }
    ],
    final: { recovered: false, termination: "HUMAN_REVIEW_REQUIRED", recovered_amount_minor: 0, action_count: 1 }
  },
  {
    id: "demo-stop",
    initial_failure: { amount_minor: 100000, payment_method: "card", failure_reason: "INSUFFICIENT_FUNDS" },
    decisions: [
      {
        decision_index: 1,
        observable_context: { elapsed_hours: 0, last_action: "NONE", previous_result: "NONE" },
        candidates: [{ label: "RETRY_NOW", probability: 0.1, incremental_erv_minor: -5000, supported: false }],
        selected_action: "NONE",
        policy_checks: { reason: "NO_POSITIVE_SUPPORTED_ACTION_BUDGET_EXHAUSTED" }
      }
    ],
    final: { recovered: false, termination: "STOPPED", recovered_amount_minor: 0, action_count: 0 }
  }
];

function getActiveText(phaseIndex: number, isDemo: boolean) {
  if (isDemo) {
    switch (phaseIndex) {
      case 0: return "Reading synthetic payment context";
      case 1: return "Presenting synthetic decision evidence";
      case 2: return "Ranking the demo intervention";
      case 3: return "Applying demo policy step";
      case 4: return "Revealing synthetic outcome";
      case 5: return "Updating the synthetic case state";
      default: return "";
    }
  } else {
    switch (phaseIndex) {
      case 0: return "Loading recorded observable context";
      case 1: return "Revealing recorded Model V2 probabilities";
      case 2: return "Revealing recorded ERV ranking";
      case 3: return "Revealing recorded Policy V2 decision";
      case 4: return "Revealing recorded simulated outcome";
      case 5: return "Advancing to the next recorded decision state";
      default: return "";
    }
  }
}

export default function ReplayLabPage() {
  const [selectedPreset, setSelectedPreset] = useState<string>("quick-recovery-demo");
  const [quickDemoIndex, setQuickDemoIndex] = useState(0);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [apiTrace, setApiTrace] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Playback state
  const [currentDecisionIndex, setCurrentDecisionIndex] = useState(0);
  const [currentPhaseIndex, setCurrentPhaseIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMicroscope, setIsMicroscope] = useState(false);

  const isDemo = selectedPreset === "quick-recovery-demo";
  const trace = isDemo ? SYNTHETIC_SCENARIOS[quickDemoIndex] : apiTrace;

  const handleReset = useCallback(() => {
    setCurrentDecisionIndex(0);
    setCurrentPhaseIndex(0);
    setIsPlaying(false);
  }, []);

  useEffect(() => {
    if (!selectedPreset) return;
    
    if (selectedPreset === "quick-recovery-demo") {
      setTimeout(() => {
        setLoading(false);
        setError(null);
        handleReset();
      }, 0);
      return;
    }
    
    let isMounted = true;
    setTimeout(() => {
      if (isMounted) {
        setLoading(true);
        setError(null);
      }
    }, 0);
    getReplayTrace(selectedPreset)
      .then((data) => {
        if (isMounted) {
          setApiTrace(data);
          setLoading(false);
          handleReset();
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || "Replay evidence unavailable");
          setLoading(false);
        }
      });
      
    return () => { isMounted = false; };
  }, [selectedPreset, handleReset]);

  const handleNextStep = useCallback(() => {
    if (!trace) return;
    if (currentPhaseIndex < 4) { // Up to OUTCOME
      setCurrentPhaseIndex(p => p + 1);
    } else if (currentPhaseIndex === 4) {
      // At OUTCOME
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
      }, 750);
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

  const renderPresetCards = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <Card 
        onClick={() => { setSelectedPreset("quick-recovery-demo"); setIsMicroscope(false); }}
        className={isDemo ? "border-emerald-500 bg-emerald-500/5 dark:bg-emerald-950/10" : ""}
      >
        <CardHeader>
          <CardTitle>Quick Recovery Demo</CardTitle>
          <div className="text-sm text-muted-foreground mt-2">Watch RecoveryIQ intelligently recover payments.</div>
        </CardHeader>
      </Card>
      
      <Card 
        onClick={() => { setSelectedPreset("successful-adaptive-trace-v2"); setIsMicroscope(false); }}
        className={selectedPreset === "successful-adaptive-trace-v2" && !isMicroscope ? "border-emerald-500 bg-emerald-500/5 dark:bg-emerald-950/10" : ""}
      >
        <CardHeader>
          <CardTitle>Sequential Recovery Replay</CardTitle>
          <div className="text-sm text-muted-foreground mt-2">Watch RecoveryIQ update state and replan across a full frozen recovery trajectory.</div>
        </CardHeader>
      </Card>
      
      <Card 
        onClick={() => { setSelectedPreset("bounded-failure-trace-v2"); setIsMicroscope(false); }}
        className={selectedPreset === "bounded-failure-trace-v2" && !isMicroscope ? "border-emerald-500 bg-emerald-500/5 dark:bg-emerald-950/10" : ""}
      >
        <CardHeader>
          <CardTitle>Bounded Safety Stop</CardTitle>
          <div className="text-sm text-muted-foreground mt-2">Watch RecoveryIQ stop after its autonomous intervention budget is exhausted.</div>
        </CardHeader>
      </Card>

      <Card 
        onClick={() => { setSelectedPreset("successful-adaptive-trace-v2"); setIsMicroscope(true); }}
        className={isMicroscope ? "border-emerald-500 bg-emerald-500/5 dark:bg-emerald-950/10" : ""}
      >
        <CardHeader>
          <CardTitle>Decision Microscope</CardTitle>
          <div className="text-sm text-muted-foreground mt-2">Inspect one frozen policy decision in detail.</div>
        </CardHeader>
      </Card>
    </div>
  );

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader 
          eyebrow="TRY RECOVERYIQ" 
          title={isDemo ? "RecoveryIQ Interactive Demo" : "RecoveryIQ Replay Lab"} 
          description={isDemo ? "Experience a synthetic recovery flow, or inspect sealed RecoveryIQ decision evidence." : "Replay frozen RecoveryIQ decisions from sealed evaluation evidence."}
        />
        {renderPresetCards()}
        <div className="p-8 text-center text-red-500 bg-red-500/10 border border-red-500/20 rounded-xl">
          <h3 className="font-bold mb-2 text-lg">Replay evidence unavailable</h3>
          <p className="text-sm mb-4">{error}</p>
          <Button onClick={() => setSelectedPreset(selectedPreset)} variant="outline">Retry</Button>
        </div>
      </div>
    );
  }

  if (loading || !trace) {
    return (
      <div className="space-y-6">
        <PageHeader 
          eyebrow="TRY RECOVERYIQ" 
          title={isDemo ? "RecoveryIQ Interactive Demo" : "RecoveryIQ Replay Lab"} 
          description={isDemo ? "Experience a synthetic recovery flow, or inspect sealed RecoveryIQ decision evidence." : "Replay frozen RecoveryIQ decisions from sealed evaluation evidence."}
        />
        {renderPresetCards()}
        <div className="text-muted-foreground p-8 text-center animate-pulse">Loading trace evidence...</div>
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
        title={isDemo ? "RecoveryIQ Interactive Demo" : "RecoveryIQ Replay Lab"}
        description={isDemo ? "Experience a synthetic recovery flow, or inspect sealed RecoveryIQ decision evidence." : "Replay frozen RecoveryIQ decisions from sealed evaluation evidence."}
      />

      {renderPresetCards()}

      <div className="flex items-center justify-between p-4 bg-muted/50 border rounded-lg">
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-[10px] tracking-widest uppercase border-emerald-500/20 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10">
            {isDemo ? 'DEMO · SYNTHETIC' : 'SEALED · SIMULATED REPLAY'}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {isDemo ? "Synthetic product walkthrough. Not sealed evidence, not live inference, and no provider action." : "Interactive presentation of frozen evaluation evidence. No new inference, provider action, or real money."}
          </span>
        </div>
      </div>
      

      <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground justify-center p-4 border bg-muted/30 rounded-xl my-8 overflow-x-auto text-center">
        <span>MODEL V2 <br/><span className="text-[10px] text-muted-foreground/70">(Recorded calibrated probabilities)</span></span>
        <span>→</span>
        <span>ERV <br/><span className="text-[10px] text-muted-foreground/70">(Economic ranking)</span></span>
        <span>→</span>
        <span>POLICY V2 <br/><span className="text-[10px] text-muted-foreground/70">(Deterministic authority)</span></span>
      </div>

      {isMicroscope ? (
        <div className="space-y-6 animate-in fade-in duration-500">
          <div className="text-center">
            <h2 className="text-xl font-bold tracking-tight text-emerald-600 dark:text-emerald-500">DECISION MICROSCOPE</h2>
            <p className="text-muted-foreground text-sm mt-2">Inspect one frozen policy decision in detail. (This is not a third independent trajectory).</p>
          </div>
          
          <Card className="overflow-hidden border bg-card">
            <CardHeader className="bg-muted/30 border-b pb-4">
               <CardTitle className="text-lg text-emerald-600 dark:text-emerald-500">Frozen Policy Authorization</CardTitle>
               <div className="mt-2 text-sm text-muted-foreground">
                 <span className="font-semibold text-foreground">Selected Action:</span> <Badge>{formatActionLabel(decision.selected_action)}</Badge>
                 <br />
                 <span className="font-semibold text-foreground">Policy Reason:</span> {decision.policy_checks?.reason || "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV"}
               </div>
            </CardHeader>
            <CardContent className="p-0">
               <div className="w-full overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground text-xs uppercase tracking-wider">
                    <tr>
                      <th className="px-6 py-3 text-left font-medium">Candidate Action</th>
                      <th className="px-6 py-3 text-right font-medium">P(recovery)</th>
                      <th className="px-6 py-3 text-right font-medium">Incremental ERV</th>
                      <th className="px-6 py-3 text-right font-medium">Stage Support</th>
                      <th className="px-6 py-3 text-right font-medium">Calibration Support</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    {decision.candidates.map((cand: any, i: number) => {
                      const isSelected = cand.label === decision.selected_action;
                      return (
                        <tr key={i} className={`group transition-all duration-500 relative ${isSelected ? "bg-gradient-to-r from-emerald-500/20 via-emerald-500/5 to-transparent border-l-[3px] border-emerald-500 shadow-[inset_6px_0_20px_rgba(16,185,129,0.15)]" : "hover:bg-muted/40"}`}>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex flex-col">
                              <span className={`text-sm ${isSelected ? "text-emerald-700 dark:text-emerald-400 font-bold" : "text-foreground"}`}>
                                {formatActionLabel(cand.label)}
                              </span>
                              <span className="text-[10px] font-mono text-muted-foreground">{cand.label}</span>
                              {isSelected && (
                                <span className="mt-1.5 inline-flex w-fit items-center px-2.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-500 text-emerald-950 uppercase tracking-[0.2em] shadow-[0_0_15px_rgba(16,185,129,0.5)] animate-pulse-subtle border border-emerald-400/50">
                                  Selected
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-foreground">
                            {(cand.probability * 100).toFixed(2)}%
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right font-mono">
                            <span className={cand.incremental_erv_minor > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}>
                              {cand.incremental_erv_minor > 0 ? "+" : ""}{formatMoney(cand.incremental_erv_minor, "INR")}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-muted-foreground">
                            {cand.action_stage_support}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-muted-foreground">
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
          <div className="flex flex-wrap gap-4 mb-8 justify-center">
             {PHASES.map((phase, idx) => (
                <div key={phase} className={`flex items-center gap-2 ${idx === currentPhaseIndex ? 'text-emerald-600 dark:text-emerald-500 font-bold' : idx < currentPhaseIndex ? 'text-emerald-600/70 dark:text-emerald-500/70' : 'text-muted-foreground'}`}>
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${idx === currentPhaseIndex ? 'border-emerald-500 bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)] text-white' : idx < currentPhaseIndex ? 'border-emerald-500 bg-transparent text-emerald-600' : 'border-border bg-transparent text-muted-foreground'}`}>
                    {idx < currentPhaseIndex ? "✓" : idx + 1}
                  </span>
                  <span className="text-xs font-mono tracking-wider">{phase}</span>
                </div>
             ))}
          </div>

          <div className="flex flex-wrap gap-4 justify-center mb-8">
             <Button onClick={handlePrevStep} disabled={currentPhaseIndex === 0 && currentDecisionIndex === 0} variant="outline" className="hover:scale-[1.02] active:scale-95 transition-all duration-300">Previous Step</Button>
             <Button 
                onClick={() => setIsPlaying(!isPlaying)} 
                disabled={showFinalOutcome} 
                className={cn(
                   "font-bold transition-all duration-300 disabled:opacity-50",
                   !isPlaying && isDemo ? "animated-shine-button hover:scale-[1.02] active:scale-95 bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40" : "",
                   isPlaying ? "animate-pulse hover:scale-[1.02] active:scale-95 bg-amber-600 hover:bg-amber-500 text-white shadow-[0_0_15px_rgba(217,119,6,0.6)]" : ""
                )}
             >
                {isPlaying ? "Pause Demo" : "Play Demo"}
             </Button>
             <Button onClick={handleNextStep} disabled={showFinalOutcome} variant="outline" className="hover:scale-[1.02] active:scale-95 transition-all duration-300">Next Step</Button>
             {isDemo && !isPlaying && (
                <Button onClick={() => { setQuickDemoIndex(i => (i + 1) % 20); handleReset(); }} variant="outline" className="text-emerald-600 border-emerald-600/20 hover:bg-emerald-600/10 hover:scale-[1.02] active:scale-95 transition-all duration-300">Try Another Case</Button>
             )}
             <Button onClick={handleReset} variant="outline" className="text-red-500 hover:text-red-600 hover:bg-red-500/10 border-red-500/20 hover:scale-[1.02] active:scale-95 transition-all duration-300">Reset</Button>
          </div>

          {isPlaying && (
            <div className="relative overflow-hidden flex items-center p-3.5 border border-emerald-500/30 bg-emerald-950/40 rounded-xl mb-6 shadow-lg shadow-emerald-900/20">
              {/* Animated gradient background */}
              <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/10 via-transparent to-emerald-900/20 animate-pulse"></div>
              
              <div className="relative z-10 flex items-center w-full">
                {/* Left Icon */}
                <div className="bg-emerald-500 text-emerald-950 rounded-lg p-1.5 mr-4 shadow-[0_0_15px_rgba(16,185,129,0.5)] flex items-center justify-center">
                  <ChevronRight className="size-4" strokeWidth={3} />
                </div>
                
                {/* Text */}
                <div className="flex items-center gap-2 text-[15px] font-bold text-white tracking-wide">
                  {currentPhaseIndex + 1}. {getActiveText(currentPhaseIndex, isDemo)}
                  <span className="flex text-emerald-500 ml-0.5">
                    <span className="animate-[bounce_1.4s_infinite] [animation-delay:-0.32s]">.</span>
                    <span className="animate-[bounce_1.4s_infinite] [animation-delay:-0.16s]">.</span>
                    <span className="animate-[bounce_1.4s_infinite]">.</span>
                  </span>
                </div>
                
                {/* Right Spinner */}
                <div className="ml-auto flex items-center mr-2">
                   <div className="size-5 border-[2.5px] border-emerald-500 border-t-transparent rounded-full animate-spin shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
                </div>
              </div>

              {/* Progress bar at bottom */}
              <div className="absolute bottom-0 left-0 h-1 bg-emerald-950/50 w-full overflow-hidden">
                <div 
                  className="h-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,1)] transition-all duration-500 ease-out" 
                  style={{ width: `${Math.max(5, ((currentPhaseIndex + 1) / (PHASES.length || 1)) * 100)}%` }}
                ></div>
              </div>
            </div>
          )}

          {currentPhaseIndex === 0 && currentDecisionIndex === 0 && (
            <Card className="border-emerald-500/30">
              <CardHeader>
                <CardTitle>Initial Failure Context</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <div className="flex justify-between items-center pb-2 border-b border-border">
                  <span>Amount:</span>
                  <span className="font-mono text-foreground">{formatMoney(trace.initial_failure.amount_minor, "INR")}</span>
                </div>
                <div className="flex justify-between items-center pb-2 border-b border-border">
                  <span>Payment Method:</span>
                  <span className="font-mono text-foreground">{trace.initial_failure.payment_method}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Failure:</span>
                  <span className="font-mono text-amber-600 dark:text-amber-400">{trace.initial_failure.failure_reason}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {currentPhaseIndex > 0 && (
            <Card className="overflow-hidden border bg-card">
              <CardHeader className="bg-muted/30 border-b pb-4">
                <CardTitle className="text-lg text-emerald-600 dark:text-emerald-500">Decision {decision.decision_index}</CardTitle>
                <div className="text-sm text-muted-foreground font-mono mt-1 flex gap-4">
                  <span>Elapsed: {decision.observable_context.elapsed_hours}h</span>
                  <span>Previous Action: {decision.observable_context.last_action}</span>
                  <span>Previous Result: {decision.observable_context.previous_result}</span>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                 <div className="w-full overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-muted-foreground text-xs uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3 text-left font-medium">Candidate Action</th>
                        <th className="px-6 py-3 text-right font-medium">P(recovery)</th>
                        <th className="px-6 py-3 text-right font-medium">Incremental ERV</th>
                        <th className="px-6 py-3 text-right font-medium">Support</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    {decision.candidates.map((cand: any, i: number) => {
                        const isSelected = cand.label === decision.selected_action;
                        return (
                          <tr key={i} className={`group transition-all duration-500 relative ${(isSelected && currentPhaseIndex >= 3) ? "bg-gradient-to-r from-emerald-500/20 via-emerald-500/5 to-transparent border-l-[3px] border-emerald-500 shadow-[inset_6px_0_20px_rgba(16,185,129,0.15)]" : "hover:bg-muted/40"}`}>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="flex flex-col">
                                <span className={`text-sm ${(isSelected && currentPhaseIndex >= 3) ? "text-emerald-700 dark:text-emerald-400 font-bold" : "text-foreground"}`}>
                                  {formatActionLabel(cand.label)}
                                </span>
                                <span className="text-[10px] font-mono text-muted-foreground">{cand.label}</span>
                                {(isSelected && currentPhaseIndex >= 3) && (
                                  <span className="mt-1.5 inline-flex w-fit items-center px-2.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-500 text-emerald-950 uppercase tracking-[0.2em] shadow-[0_0_15px_rgba(16,185,129,0.5)] animate-pulse-subtle border border-emerald-400/50">
                                    Selected
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-foreground">
                              {currentPhaseIndex >= 1 ? `${(cand.probability * 100).toFixed(2)}%` : "—"}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right font-mono">
                              {currentPhaseIndex >= 2 ? (
                                <span className={cand.incremental_erv_minor > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}>
                                  {cand.incremental_erv_minor > 0 ? "+" : ""}{formatMoney(cand.incremental_erv_minor, "INR")}
                                </span>
                              ) : "—"}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-muted-foreground">
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
                <div className="p-4 bg-muted/30 border-t border-border text-sm">
                  <span className="font-bold text-foreground">Why this action?</span><br />
                  <span className="text-muted-foreground text-xs">Sequential Policy V2 authorized the supported feasible action with the maximum positive incremental ERV. (Reason: {decision.policy_checks?.reason || "MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV"})</span>
                </div>
              )}
            </Card>
          )}

          {currentPhaseIndex >= 4 && !isFinalDecision && (
            <Card className="border-amber-500/30">
              <CardHeader>
                <CardTitle className="text-amber-500">RECORDED SIMULATED OUTCOME</CardTitle>
                <div className="text-sm font-mono text-amber-400 mt-2">FAILED</div>
              </CardHeader>
            </Card>
          )}

          {showFinalOutcome && (
            <Card className={cn(isRecovered ? "border-emerald-500/50 bg-emerald-500/10 dark:bg-emerald-950/20" : "border-amber-500/50 bg-amber-500/10 dark:bg-amber-950/20")}>
              <CardHeader>
                <CardTitle className={isRecovered ? "text-emerald-700 dark:text-emerald-400 text-2xl" : "text-amber-700 dark:text-amber-400 text-2xl"}>
                  {isRecovered ? "RECOVERED" : "BOUNDED AUTONOMY WORKED AS DESIGNED"}
                </CardTitle>
                {isRecovered && isDemo && (
                   <div className="text-emerald-600 mt-2">Recovered on intervention {trace.final.action_count}</div>
                )}
                {isRecovered && !isDemo && (
                   <div className="text-emerald-600 mt-2">SIMULATED RECOVERY</div>
                )}
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                {!isRecovered && (
                  <div className="mb-4">
                    <Badge variant="safety" className="text-sm px-3 py-1 mr-2">STOP</Badge>
                    <Badge variant="safety" className="text-sm px-3 py-1">MAX_INTERVENTIONS</Badge>
                  </div>
                )}
                <div className="flex justify-between items-center pb-2 border-b border-border">
                  <span>Status:</span>
                  <span className={`font-bold ${isRecovered ? "text-emerald-600 dark:text-emerald-500" : "text-amber-600 dark:text-amber-500"}`}>{trace.final.termination}</span>
                </div>
                {isRecovered && (
                  <div className="flex justify-between items-center pb-2 border-b border-border">
                    <span>Recovered Amount:</span>
                    <span className="font-mono text-foreground">{formatMoney(trace.final.recovered_amount_minor, "INR")}</span>
                  </div>
                )}
                <div className="flex justify-between items-center pb-2 border-b border-border">
                  <span>Autonomous Interventions Used:</span>
                  <span className="font-mono text-foreground">{trace.final.action_count}</span>
                </div>
                {!isRecovered && trace.final.termination === "STOPPED" && (
                  <div className="text-amber-600 dark:text-amber-500 text-xs font-bold tracking-widest mt-4">NO FOURTH AUTONOMOUS ACTION ALLOWED</div>
                )}
                {isRecovered && !isDemo && trace.final.total_intervention_cost_minor !== undefined && (
                  <>
                    <div className="flex justify-between items-center pb-2 border-b border-border">
                      <span>Total Intervention Cost:</span>
                      <span className="font-mono text-foreground">{formatMoney(trace.final.total_intervention_cost_minor, "INR")}</span>
                    </div>
                    <div className="flex justify-between items-center pb-2 border-b border-border">
                      <span>Total Friction Cost:</span>
                      <span className="font-mono text-foreground">{formatMoney(trace.final.total_friction_cost_minor, "INR")}</span>
                    </div>
                    <div className="flex justify-between items-center pb-2 border-b border-border">
                      <span>Simulated Net Recovery Value:</span>
                      <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">{formatMoney(trace.final.simulated_net_recovery_value_minor, "INR")}</span>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}

          {showFinalOutcome && !isDemo && (
            <div className="mt-12 p-6 border bg-muted/50 rounded-xl text-center">
              <h3 className="text-lg font-bold text-foreground mb-2 tracking-widest">PROVIDER EXECUTION NOT REPLAYED HERE</h3>
              <p className="text-sm text-muted-foreground mb-4">Replay Lab ends at policy evidence. Razorpay provider execution is demonstrated separately in Test Mode evidence.</p>
              <a href="/integrations/razorpay" className="inline-flex items-center justify-center px-4 py-2 border border-emerald-500/50 text-emerald-600 dark:text-emerald-500 rounded hover:bg-emerald-500/10 transition-colors text-sm font-medium">
                View Razorpay Test Evidence
              </a>
            </div>
          )}
        </div>
      )}

      <div className="pt-12 mt-12 border-t grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
         <a href="/decision-trace" className="text-sm text-muted-foreground hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">Inspect Decision Trace</a>
         <a href="/batch-explorer" className="text-sm text-muted-foreground hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">Explore 27,406 Sealed Episodes</a>
         <a href="/integrations/razorpay" className="text-sm text-muted-foreground hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">View Razorpay Test Evidence</a>
         <a href="/evaluation" className="text-sm text-muted-foreground hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">Open Evaluation Lab</a>
      </div>
    </div>
  );
}
