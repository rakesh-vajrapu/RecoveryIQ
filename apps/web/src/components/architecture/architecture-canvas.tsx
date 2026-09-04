"use client";

import { useState, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { ARCHITECTURE_STAGES, ArchitectureStage, NodeColor, NodeShape } from "@/lib/architecture-data";
import { ArrowDown } from "lucide-react";

interface Props {
  activeStageId: string | null;
  activePathIds: string[];
  onSelectStage: (stage: ArchitectureStage) => void;
}

const colorMap: Record<NodeColor, { border: string; bg: string; text: string; shadow: string, ring: string }> = {
  emerald: { border: "border-emerald-500/50", bg: "bg-emerald-500/10", text: "text-emerald-600 dark:text-emerald-400", shadow: "shadow-emerald-500/20", ring: "ring-emerald-500/50" },
  blue: { border: "border-blue-500/50", bg: "bg-blue-500/10", text: "text-blue-600 dark:text-blue-400", shadow: "shadow-blue-500/20", ring: "ring-blue-500/50" },
  cyan: { border: "border-cyan-500/50", bg: "bg-cyan-500/10", text: "text-cyan-600 dark:text-cyan-400", shadow: "shadow-cyan-500/20", ring: "ring-cyan-500/50" },
  electric: { border: "border-blue-400/50", bg: "bg-blue-400/10", text: "text-blue-500 dark:text-blue-400", shadow: "shadow-blue-400/20", ring: "ring-blue-400/50" },
  violet: { border: "border-violet-500/50", bg: "bg-violet-500/10", text: "text-violet-600 dark:text-violet-400", shadow: "shadow-violet-500/20", ring: "ring-violet-500/50" },
  magenta: { border: "border-pink-500/50", bg: "bg-pink-500/10", text: "text-pink-600 dark:text-pink-400", shadow: "shadow-pink-500/20", ring: "ring-pink-500/50" },
  amber: { border: "border-amber-500/50", bg: "bg-amber-500/10", text: "text-amber-600 dark:text-amber-400", shadow: "shadow-amber-500/20", ring: "ring-amber-500/50" },
  red: { border: "border-red-500/50", bg: "bg-red-500/10", text: "text-red-600 dark:text-red-400", shadow: "shadow-red-500/20", ring: "ring-red-500/50" },
  teal: { border: "border-teal-500/50", bg: "bg-teal-500/10", text: "text-teal-600 dark:text-teal-400", shadow: "shadow-teal-500/20", ring: "ring-teal-500/50" },
  gold: { border: "border-yellow-500/50", bg: "bg-yellow-500/10", text: "text-yellow-600 dark:text-yellow-400", shadow: "shadow-yellow-500/20", ring: "ring-yellow-500/50" },
  aqua: { border: "border-cyan-300/50", bg: "bg-cyan-300/10", text: "text-cyan-500 dark:text-cyan-300", shadow: "shadow-cyan-300/20", ring: "ring-cyan-300/50" },
  slate: { border: "border-muted", bg: "bg-muted/10", text: "text-muted-foreground", shadow: "shadow-none", ring: "ring-muted" },
};

function getShapeClasses(shape: NodeShape) {
  switch (shape) {
    case 'circle': return "rounded-full aspect-square justify-center text-center flex-col py-3";
    case 'diamond': return "rounded-lg before:absolute before:inset-0 before:border before:border-inherit before:rounded-lg before:rotate-45 before:scale-[0.8] before:transition-all hover:before:scale-[0.85]";
    case 'hexagon': return "rounded-xl before:absolute before:-inset-x-2 before:inset-y-3 before:border-y before:border-inherit before:bg-inherit before:-z-10";
    case 'cloud': return "rounded-3xl border-2";
    case 'cylinder': return "rounded-xl border-t-[8px]";
    case 'octagon': return "rounded-lg border-x-4";
    case 'human': return "rounded-t-full rounded-b-lg border-b-4";
    default: return "rounded-xl";
  }
}

function StageCard({ stage, isActive, isDimmed, onClick }: { stage: ArchitectureStage, isActive: boolean, isDimmed: boolean, onClick: () => void }) {
  const Icon = stage.icon;
  const colors = colorMap[stage.color];
  const shapeClass = getShapeClasses(stage.shape);
  const prefersReducedMotion = typeof window !== 'undefined' ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false;
  
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative w-full text-left group flex items-center gap-2 p-2 border transition-all duration-300 bg-card",
        shapeClass,
        colors.border,
        isDimmed ? "opacity-30 hover:opacity-100 grayscale-[0.8]" : "hover:bg-muted/20",
        isActive && `ring-2 ring-offset-2 ring-offset-background ${colors.shadow} shadow-xl scale-[1.02] ${colors.ring}`
      )}
    >
      <div className={cn("p-1.5 rounded-lg shrink-0 transition-colors", colors.bg, colors.text)}>
        <Icon className={cn("size-4", isActive && !prefersReducedMotion && "animate-pulse")} />
      </div>
      <div>
        <h4 className={cn("font-bold text-[11px] leading-tight", isDimmed ? "text-muted-foreground" : "text-foreground")}>{stage.label}</h4>
        {stage.sublabel && <p className="text-[9px] text-muted-foreground tracking-wider uppercase font-semibold mt-0.5 leading-[1.1]">{stage.sublabel}</p>}
      </div>
    </button>
  );
}

function Connector({ active, variant = 'down', height = 'h-4', labelLeft, labelRight }: { active: boolean, variant?: 'down' | 'branch' | 'merge', height?: string, labelLeft?: string, labelRight?: string }) {
  const prefersReducedMotion = typeof window !== 'undefined' ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false;
  
  if (variant === 'branch') {
    return (
      <div className="flex flex-col items-center justify-center w-full relative h-6 my-1">
         <div className={cn("absolute top-0 left-[25%] right-[25%] h-0.5 transition-colors duration-500", active ? "bg-primary" : "bg-muted")} />
         <div className="flex justify-between w-1/2 absolute top-0">
           <div className="relative">
              <ArrowDown className={cn("size-3 -ml-1.5 transition-colors duration-500", active ? "text-primary" : "text-muted")} />
              {labelLeft && <span className="absolute right-full top-0 mr-1 text-[8px] text-muted-foreground whitespace-nowrap bg-background px-1">{labelLeft}</span>}
           </div>
           <div className="relative">
              <ArrowDown className={cn("size-3 -mr-1.5 transition-colors duration-500", active ? "text-primary" : "text-muted")} />
              {labelRight && <span className="absolute left-full top-0 ml-1 text-[8px] text-muted-foreground whitespace-nowrap bg-background px-1">{labelRight}</span>}
           </div>
         </div>
      </div>
    );
  }

  if (variant === 'merge') {
    return (
      <div className="flex flex-col items-center justify-center w-full relative h-6">
         <div className={cn("absolute bottom-0 left-[25%] right-[25%] h-0.5 transition-colors duration-500", active ? "bg-primary" : "bg-muted")} />
         <div className="flex justify-between w-1/2 absolute bottom-0 h-4">
           <div className={cn("w-0.5 h-full transition-colors duration-500", active ? "bg-primary" : "bg-muted")} />
           <div className={cn("w-0.5 h-full transition-colors duration-500", active ? "bg-primary" : "bg-muted")} />
         </div>
         <ArrowDown className={cn("size-3 absolute -bottom-1 transition-colors duration-500", active ? "text-primary" : "text-muted")} />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-0.5">
      <div className={cn("w-0.5 transition-colors duration-500", height, active ? "bg-primary" : "bg-muted", active && !prefersReducedMotion && "animate-pulse")} />
      <ArrowDown className={cn("size-3 -mt-1 transition-colors duration-500", active ? "text-primary" : "text-muted")} />
    </div>
  );
}

export function ArchitectureCanvas({ activeStageId, activePathIds, onSelectStage }: Props) {
  const isPathDimmed = (id: string) => activePathIds.length > 0 && !activePathIds.includes(id);
  const getStage = (id: string) => ARCHITECTURE_STAGES.find(s => s.id === id)!;

  const containerRef = useRef<HTMLDivElement>(null);
  const actionRef = useRef<HTMLDivElement>(null);
  const authRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState<{ x1: number, y1: number, x2: number, y2: number } | null>(null);

  useEffect(() => {
    const updateCoords = () => {
      if (!containerRef.current || !actionRef.current || !authRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const actionRect = actionRef.current.getBoundingClientRect();
      const authRect = authRef.current.getBoundingClientRect();

      setCoords({
        x1: actionRect.right - containerRect.left,
        y1: actionRect.top + actionRect.height / 2 - containerRect.top,
        x2: authRect.left - containerRect.left,
        y2: authRect.top + authRect.height / 2 - containerRect.top,
      });
    };

    updateCoords();
    
    // Re-run safely when layout might shift
    const observer = new ResizeObserver(() => updateCoords());
    if (containerRef.current) observer.observe(containerRef.current);
    
    return () => observer.disconnect();
  }, [activePathIds, activeStageId]);

  const renderStage = (id: string, connectorHeight = 'h-4', connectorActiveId?: string, cardRef?: React.Ref<HTMLDivElement>) => (
    <div className="flex flex-col items-center w-full">
      <div ref={cardRef} className="w-full">
        <StageCard stage={getStage(id)} isActive={activeStageId === id} isDimmed={isPathDimmed(id)} onClick={() => onSelectStage(getStage(id))} />
      </div>
      <Connector active={!isPathDimmed(connectorActiveId || id)} height={connectorHeight} />
    </div>
  );

  return (
    <div className="py-4 px-2 w-full max-w-none mx-auto overflow-x-auto custom-scrollbar relative" ref={containerRef}>
      
      {coords && (
        <svg className="absolute top-0 left-0 w-full h-full pointer-events-none z-0">
           <path 
             d={`M ${coords.x1} ${coords.y1} L ${coords.x1 + (coords.x2 - coords.x1)/2} ${coords.y1} L ${coords.x1 + (coords.x2 - coords.x1)/2} ${coords.y2} L ${coords.x2 - 5} ${coords.y2}`}
             fill="none"
             stroke={!isPathDimmed("prov-auth") ? "#10b981" : "#334155"}
             strokeWidth="2"
             className="transition-colors duration-500"
             markerEnd="url(#arrowhead)"
           />
           <defs>
             <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
               <polygon points="0 0, 10 3.5, 0 7" fill={!isPathDimmed("prov-auth") ? "#10b981" : "#334155"} className="transition-colors duration-500" />
             </marker>
           </defs>
        </svg>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-16 lg:gap-24 min-w-[700px] max-w-[900px] mx-auto px-8 relative z-10">
        
        {/* LANE 1: DECISION ENGINE */}
        <div className="flex flex-col items-center surface-panel rounded-2xl p-4 border border-blue-500/20 bg-blue-500/5 relative z-10">
          <div className="absolute inset-0 bg-grid-white/5 opacity-10 rounded-2xl pointer-events-none" />
          <h3 className="text-xs font-bold tracking-widest text-blue-600 dark:text-blue-400 uppercase mb-6 flex items-center gap-2 text-center leading-relaxed">
            1. DECISION ENGINE
          </h3>
          
          <div className="w-full max-w-[280px] mx-auto z-10 flex flex-col items-center">
            {renderStage("dec-failed")}
            {renderStage("dec-context")}
            
            <div className="flex flex-col items-center w-full">
              <StageCard stage={getStage("dec-feasible")} isActive={activeStageId === "dec-feasible"} isDimmed={isPathDimmed("dec-feasible")} onClick={() => onSelectStage(getStage("dec-feasible"))} />
              <Connector active={!isPathDimmed("dec-feasible")} variant="branch" labelLeft="3 retry options" labelRight="3 intervention options" />
            </div>

            {/* FEASIBLE ACTIONS (2 cols) */}
            <div className="flex w-full gap-4 mt-2">
              <div className="w-1/2 flex flex-col gap-2">
                 <StageCard stage={getStage("dec-f-now")} isActive={activeStageId === "dec-f-now"} isDimmed={isPathDimmed("dec-f-now")} onClick={() => onSelectStage(getStage("dec-f-now"))} />
                 <StageCard stage={getStage("dec-f-2h")} isActive={activeStageId === "dec-f-2h"} isDimmed={isPathDimmed("dec-f-2h")} onClick={() => onSelectStage(getStage("dec-f-2h"))} />
                 <StageCard stage={getStage("dec-f-24h")} isActive={activeStageId === "dec-f-24h"} isDimmed={isPathDimmed("dec-f-24h")} onClick={() => onSelectStage(getStage("dec-f-24h"))} />
              </div>
              <div className="w-1/2 flex flex-col gap-2">
                 <StageCard stage={getStage("dec-f-nudge")} isActive={activeStageId === "dec-f-nudge"} isDimmed={isPathDimmed("dec-f-nudge")} onClick={() => onSelectStage(getStage("dec-f-nudge"))} />
                 <StageCard stage={getStage("dec-f-plink")} isActive={activeStageId === "dec-f-plink"} isDimmed={isPathDimmed("dec-f-plink")} onClick={() => onSelectStage(getStage("dec-f-plink"))} />
                 <StageCard stage={getStage("dec-f-alt")} isActive={activeStageId === "dec-f-alt"} isDimmed={isPathDimmed("dec-f-alt")} onClick={() => onSelectStage(getStage("dec-f-alt"))} />
              </div>
            </div>

            <div className="mt-2">
              <Connector active={!isPathDimmed("dec-model")} variant="merge" />
            </div>

            {renderStage("dec-model")}

            <div className="w-full">
              <Connector active={!isPathDimmed("dec-model")} variant="branch" labelLeft="CALIBRATED P(RECOVERY)" labelRight="FOR EVERY ACTION" />
            </div>

            {/* PROBABILITIES (2 cols) */}
            <div className="flex w-full gap-4 mt-2">
              <div className="w-1/2 flex flex-col gap-2">
                 <StageCard stage={getStage("dec-p-now")} isActive={activeStageId === "dec-p-now"} isDimmed={isPathDimmed("dec-p-now")} onClick={() => onSelectStage(getStage("dec-p-now"))} />
                 <StageCard stage={getStage("dec-p-2h")} isActive={activeStageId === "dec-p-2h"} isDimmed={isPathDimmed("dec-p-2h")} onClick={() => onSelectStage(getStage("dec-p-2h"))} />
                 <StageCard stage={getStage("dec-p-24h")} isActive={activeStageId === "dec-p-24h"} isDimmed={isPathDimmed("dec-p-24h")} onClick={() => onSelectStage(getStage("dec-p-24h"))} />
              </div>
              <div className="w-1/2 flex flex-col gap-2">
                 <StageCard stage={getStage("dec-p-nudge")} isActive={activeStageId === "dec-p-nudge"} isDimmed={isPathDimmed("dec-p-nudge")} onClick={() => onSelectStage(getStage("dec-p-nudge"))} />
                 <StageCard stage={getStage("dec-p-plink")} isActive={activeStageId === "dec-p-plink"} isDimmed={isPathDimmed("dec-p-plink")} onClick={() => onSelectStage(getStage("dec-p-plink"))} />
                 <StageCard stage={getStage("dec-p-alt")} isActive={activeStageId === "dec-p-alt"} isDimmed={isPathDimmed("dec-p-alt")} onClick={() => onSelectStage(getStage("dec-p-alt"))} />
              </div>
            </div>

            <div className="mt-2">
              <Connector active={!isPathDimmed("dec-erv")} variant="merge" />
            </div>

            {renderStage("dec-erv")}
            {renderStage("dec-rank")}
            {renderStage("dec-policy")}

            {/* 3-WAY SPLIT: STOP / HUMAN REVIEW / ACTION */}
            <div className="flex flex-col items-center w-full">
              <div className="flex justify-between w-full relative h-6 my-1">
                 <div className={cn("absolute top-0 left-0 right-0 h-0.5 transition-colors duration-500", !isPathDimmed("dec-policy") ? "bg-primary" : "bg-muted")} />
                 <ArrowDown className={cn("size-3 absolute top-0 left-0 -ml-1.5 transition-colors duration-500", !isPathDimmed("dec-stop") ? "text-primary" : "text-muted")} />
                 <ArrowDown className={cn("size-3 absolute top-0 left-1/2 -ml-1.5 transition-colors duration-500", !isPathDimmed("dec-human") ? "text-primary" : "text-muted")} />
                 <ArrowDown className={cn("size-3 absolute top-0 right-0 -mr-1.5 transition-colors duration-500", !isPathDimmed("dec-action") ? "text-primary" : "text-muted")} />
              </div>
            </div>
            
            <div className="flex w-[120%] -ml-[10%] gap-2 relative">
              <div className="w-1/3 flex flex-col items-center">
                 <StageCard stage={getStage("dec-stop")} isActive={activeStageId === "dec-stop"} isDimmed={isPathDimmed("dec-stop")} onClick={() => onSelectStage(getStage("dec-stop"))} />
              </div>
              <div className="w-1/3 flex flex-col items-center">
                 <StageCard stage={getStage("dec-human")} isActive={activeStageId === "dec-human"} isDimmed={isPathDimmed("dec-human")} onClick={() => onSelectStage(getStage("dec-human"))} />
              </div>
              <div className="w-1/3 flex flex-col items-center relative">
                 <div ref={actionRef} className="w-full">
                   <StageCard stage={getStage("dec-action")} isActive={activeStageId === "dec-action"} isDimmed={isPathDimmed("dec-action")} onClick={() => onSelectStage(getStage("dec-action"))} />
                 </div>
              </div>
            </div>

          </div>
        </div>

        {/* LANE 2: PROVIDER EXECUTION */}
        <div className="flex flex-col items-center surface-panel rounded-2xl p-4 border border-teal-500/20 bg-teal-500/5 relative z-10">
          <div className="absolute inset-0 bg-grid-white/5 opacity-10 rounded-2xl pointer-events-none" />
          <h3 className="text-xs font-bold tracking-widest text-teal-600 dark:text-teal-400 uppercase mb-6 flex items-center gap-2 text-center leading-relaxed">
            2. PROVIDER EXECUTION
          </h3>
          <div className="w-full max-w-[220px] mx-auto z-10 flex flex-col items-center relative">
            
            {renderStage("prov-auth", "h-4", undefined, authRef)}
            {renderStage("prov-req")}
            {renderStage("prov-test")}
            {renderStage("prov-webhook")}
            {renderStage("prov-sig")}
            {renderStage("prov-fetch")}
            {renderStage("prov-truth")}
            {renderStage("prov-outcome")}
            {renderStage("prov-attr")}
            
            <div className="flex flex-col items-center w-full">
              <StageCard stage={getStage("prov-recovered")} isActive={activeStageId === "prov-recovered"} isDimmed={isPathDimmed("prov-recovered")} onClick={() => onSelectStage(getStage("prov-recovered"))} />
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
