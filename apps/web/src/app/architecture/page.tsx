"use client";

import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { ArchitectureScenario, ArchitectureStage, SCENARIOS } from "@/lib/architecture-data";
import { PageHeader } from "@/components/page-header";
import { ArchitectureCanvas } from "@/components/architecture/architecture-canvas";
import { ScenarioControls } from "@/components/architecture/scenario-controls";

import { BrainCircuit, ShieldCheck, Database, Scale, Lock, FileWarning, Key, RefreshCw, MessageSquare, Maximize, Minimize } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function ArchitecturePage() {
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<ArchitectureStage | null>(null);
  const [mounted, setMounted] = useState(false);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  
  // Play Path State
  const [isPlaying, setIsPlaying] = useState(false);
  const [playCursor, setPlayCursor] = useState(0);

  // Full Screen State
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

  const activeScenario = SCENARIOS.find(s => s.id === activeScenarioId) || null;
  
  // Compute the paths that should be active right now.
  // If playing, only slice up to the cursor. If not playing, show all.
  const allScenarioStageIds = activeScenario?.activeStageIds || [];
  const activePathIds = isPlaying 
    ? allScenarioStageIds.slice(0, playCursor + 1)
    : allScenarioStageIds;

  // Handle auto-play effect
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isPlaying && activeScenario) {
      if (playCursor < allScenarioStageIds.length - 1) {
        timer = setTimeout(() => {
          setPlayCursor(c => c + 1);
        }, 800); // 800ms per node transition as requested
      } else {
        // Stop playing when finished
        setTimeout(() => setIsPlaying(false), 2000);
      }
    }
    return () => clearTimeout(timer);
  }, [isPlaying, playCursor, activeScenario, allScenarioStageIds.length]);

  const handleSelectScenario = (scenario: ArchitectureScenario | null) => {
    setActiveScenarioId(scenario ? scenario.id : null);
    setActiveStage(null); 
    setIsPlaying(false);
    setPlayCursor(0);
  };

  const handleSelectStage = (stage: ArchitectureStage) => {
    setActiveStage(stage);
    setIsPlaying(false); // Manually clicking a stage interrupts playback
  };

  const handleTogglePlay = () => {
    if (isPlaying) {
      setIsPlaying(false);
    } else {
      setPlayCursor(0);
      setIsPlaying(true);
      setActiveStage(null); // Focus back on the scenario playing
    }
    if (detailsRef.current) {
      detailsRef.current.open = false;
    }
  };

  const interactiveFlowContent = (
    <div className={cn(
      "grid items-start w-full",
      isFullscreen ? "grid-cols-1" : "grid-cols-1 lg:grid-cols-12 gap-8"
    )}>
      {/* Left: Sticky Controls (Only visible in normal mode) */}
      {!isFullscreen && (
        <div className="lg:col-span-3 flex flex-col gap-4">
          <Button 
            variant="outline" 
            onClick={() => setIsFullscreen(true)} 
            className="w-full gap-2 bg-primary/5 hover:bg-primary/10 border-primary/20 hover:border-primary/40 text-primary shadow-sm transition-all"
          >
            <Maximize className="size-4" /> Enter Full Screen Mode
          </Button>
          <ScenarioControls 
            activeScenarioId={activeScenarioId}
            isPlaying={isPlaying} 
            onSelectScenario={handleSelectScenario}
            onTogglePlay={handleTogglePlay}
          />
        </div>
      )}

      {/* Center: Main Canvas */}
      <div className={cn(
        "flex justify-center rounded-2xl border bg-card/50",
        isFullscreen ? "p-8 overflow-x-auto min-h-[700px] shadow-2xl w-full" : "lg:col-span-9 p-4 overflow-x-auto shadow-inner"
      )}>
        <div className="w-full">
          <ArchitectureCanvas 
            activeStageId={activeStage?.id || null} 
            activePathIds={activePathIds}
            onSelectStage={handleSelectStage}
          />
        </div>
      </div>
    </div>
  );

  const interactiveFlowSection = isFullscreen ? (
    mounted ? createPortal(
      <div className="fixed inset-0 z-[9999] bg-background/95 backdrop-blur-3xl p-4 md:p-8 overflow-y-auto overflow-x-hidden flex flex-col">
        <div className="flex justify-between items-start w-full sticky top-0 z-50 bg-background/80 backdrop-blur-md pb-4 border-b mb-8 shrink-0 mx-auto">
          
          <div className="flex flex-col gap-4">
            <h2 className="font-bold tracking-widest text-lg flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              ARCHITECTURE FULL SCREEN
              {activeScenario && <span className="text-muted-foreground font-normal ml-2">/ {activeScenario.label}</span>}
            </h2>
            
            {/* Native Collapsible Menu for Scenarios */}
            <details ref={detailsRef} className="group relative">
              <summary className="list-none cursor-pointer font-bold tracking-widest text-sm flex items-center gap-2 px-4 py-2 bg-muted/50 hover:bg-muted border rounded-lg transition-colors w-fit">
                {activeScenario ? activeScenario.label.toUpperCase() : "SELECT SCENARIO"} ▾
              </summary>
              <div className="absolute top-full left-0 mt-2 w-[320px] bg-background border rounded-xl shadow-2xl z-50 max-h-[60vh] overflow-y-auto">
                <ScenarioControls 
                  activeScenarioId={activeScenarioId}
                  isPlaying={isPlaying} 
                  onSelectScenario={handleSelectScenario}
                  onTogglePlay={handleTogglePlay}
                />
              </div>
            </details>
          </div>

          <Button variant="default" size="sm" onClick={() => setIsFullscreen(false)} className="gap-2 shadow-lg shadow-primary/20">
            <Minimize className="size-4" /> Exit Full Screen
          </Button>
        </div>
        {interactiveFlowContent}
      </div>,
      document.body
    ) : null
  ) : (
    <section className="relative w-full">
      {interactiveFlowContent}
    </section>
  );

  return (
    <div className="space-y-12 pb-16">
      
      {/* 1. Header / Hero */}
      <section className="relative">
        <div className="absolute -inset-8 bg-gradient-to-br from-primary/5 via-transparent to-transparent opacity-50 blur-3xl pointer-events-none" />
        
        <PageHeader 
          eyebrow="RECOVERYIQ ARCHITECTURE" 
          title="From failed payment signal to verified recovery." 
          description="A comprehensive walkthrough of how RecoveryIQ observes context, ranks economic value, executes safely, triangulates provider truth, and attributes revenue."
        />

        <div className="flex flex-wrap gap-3 mt-4">
          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-widest uppercase border border-blue-500/20 text-blue-600 dark:text-blue-400 bg-blue-500/10">1. Decision Engine</span>
          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-widest uppercase border border-teal-500/20 text-teal-600 dark:text-teal-400 bg-teal-500/10">2. Provider Execution</span>
        </div>
      </section>

      {/* Main Interactive Flow */}
      {interactiveFlowSection}

      {/* DEEP DIVE SECTIONS */}
      <section className="pt-20 border-t">
        <h2 className="text-3xl font-bold tracking-tight mb-12 text-center">Architecture Deep Dives</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          
          {/* 01. THE DECISION ENGINE */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-violet-500/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-violet-500/10 text-violet-500 rounded-lg group-hover:bg-violet-500 group-hover:text-white transition-colors"><BrainCircuit className="size-5" /></div>
              <h3 className="font-bold text-lg">01. The Decision Engine</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-4">
              The canonical authority line ensures AI boundaries. Model V2 predicts probabilities. ERV ranks economic value based on fixed cost definitions. Policy V2 deterministically authorizes the action.
            </p>
            <div className="bg-muted/30 p-3 rounded-lg text-xs font-medium border border-violet-500/20 text-violet-600 dark:text-violet-400">
              Model → ERV → Policy
            </div>
          </div>

          {/* 02. BOUNDED AUTONOMY */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-amber-500/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-amber-500/10 text-amber-500 rounded-lg group-hover:bg-amber-500 group-hover:text-white transition-colors"><Scale className="size-5" /></div>
              <h3 className="font-bold text-lg">02. Bounded Autonomy</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              RecoveryIQ is designed to STOP. If there is no positive incremental ERV, or the hard limit of 3 autonomous interventions is reached, the system permanently stops or explicitly escalates to Human Review. It refuses to fabricate features.
            </p>
          </div>

          {/* 03. PROVIDER BOUNDARY */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-teal-500/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-teal-500/10 text-teal-500 rounded-lg group-hover:bg-teal-500 group-hover:text-white transition-colors"><ShieldCheck className="size-5" /></div>
              <h3 className="font-bold text-lg">03. Provider Boundary</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              A decision is not an execution. An execution is not an outcome. An outcome is not an attribution. By explicitly decoupling these stages, RecoveryIQ maintains strict guarantees over external state mutations.
            </p>
          </div>

          {/* 04. PROVIDER TRUTH TRIANGULATION */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-cyan-500/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-cyan-500/10 text-cyan-500 rounded-lg group-hover:bg-cyan-500 group-hover:text-white transition-colors"><Database className="size-5" /></div>
              <h3 className="font-bold text-lg">04. Provider Triangulation</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-4">
              Never trust a webhook alone. A signed webhook triggers an independent Provider Fetch. If the reference, amount, or currency mismatches even slightly, it FAILS CLOSED.
            </p>
            <div className="flex items-center justify-between text-xs font-bold text-cyan-600 dark:text-cyan-400">
              <span>WEBHOOK</span>
              <span>+</span>
              <span>FETCH</span>
              <span>=</span>
              <span>VERIFIED OUTCOME</span>
            </div>
          </div>

          {/* 05. EXACTLY-ONCE LOCAL ACCOUNTING */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-emerald-500/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-emerald-500/10 text-emerald-500 rounded-lg group-hover:bg-emerald-500 group-hover:text-white transition-colors"><Lock className="size-5" /></div>
              <h3 className="font-bold text-lg">05. Exactly-Once Accounting</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Provider-side execution can contain distributed-system ambiguity. However, RecoveryIQ implements exactly-once local outcome and recovery attribution semantics, ensuring revenue is never double-counted internally.
            </p>
          </div>

          {/* 06. CONCURRENCY & IDEMPOTENCY */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-blue-500/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-blue-500/10 text-blue-500 rounded-lg group-hover:bg-blue-500 group-hover:text-white transition-colors"><Key className="size-5" /></div>
              <h3 className="font-bold text-lg">06. Concurrency & Races</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              If multiple executors attempt to trigger the same action, a unique execution reservation guarantees one logical winner. Duplicate webhooks for the same provider event are blocked at the idempotency gate.
            </p>
          </div>

          {/* 07. FAIL-CLOSED RECOVERY */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-red-500/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-500/10 text-red-500 rounded-lg group-hover:bg-red-500 group-hover:text-white transition-colors"><FileWarning className="size-5" /></div>
              <h3 className="font-bold text-lg">07. Fail-Closed Recovery</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              If an execution thread crashes post-dispatch but pre-acknowledgment, the state is UNKNOWN. The system will attempt to reconcile via provider reference. If it cannot, it remains blocked. It NEVER blindly creates a replacement.
            </p>
          </div>

          {/* 08. AUDITABILITY */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-cyan-300/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-cyan-300/10 text-cyan-500 rounded-lg group-hover:bg-cyan-400 group-hover:text-white transition-colors"><RefreshCw className="size-5" /></div>
              <h3 className="font-bold text-lg">08. Auditability</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Every critical lifecycle transition records a Recovery Proof. This proof includes a SHA-256 evidence fingerprint. The fingerprint changes deterministically if any included canonical evidence fields change.
            </p>
          </div>

          {/* 09. AI AUTHORITY BOUNDARY */}
          <div className="surface-panel p-6 rounded-2xl border hover:border-aqua-500/30 transition-colors group">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-cyan-500/10 text-cyan-500 rounded-lg group-hover:bg-cyan-500 group-hover:text-white transition-colors"><MessageSquare className="size-5" /></div>
              <h3 className="font-bold text-lg">09. AI Authority Boundary</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Large Language Models (LLMs) are completely detached from execution authority. The LLM only receives a read-only sealed trace log to generate a human-readable explanation, ensuring zero risk of prompt-injection execution.
            </p>
          </div>

        </div>
      </section>

    </div>
  );
}
