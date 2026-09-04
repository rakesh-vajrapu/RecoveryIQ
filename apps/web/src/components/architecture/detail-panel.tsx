"use client";

import { ArchitectureScenario, ArchitectureStage, NodeColor } from "@/lib/architecture-data";
import { cn } from "@/lib/utils";
import { Info, LogIn, LogOut, Code, AlertTriangle, FileText, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { Button } from "../ui/button";

interface Props {
  stage: ArchitectureStage | null;
  scenario: ArchitectureScenario | null;
}

const colorMap: Record<NodeColor, string> = {
  emerald: "text-emerald-500",
  blue: "text-blue-500",
  cyan: "text-cyan-500",
  electric: "text-blue-400",
  violet: "text-violet-500",
  magenta: "text-pink-500",
  amber: "text-amber-500",
  red: "text-red-500",
  teal: "text-teal-500",
  gold: "text-yellow-500",
  aqua: "text-cyan-300",
  slate: "text-slate-400"
};

const bgMap: Record<NodeColor, string> = {
  emerald: "bg-emerald-500/10 border-emerald-500/20 shadow-emerald-500/10",
  blue: "bg-blue-500/10 border-blue-500/20 shadow-blue-500/10",
  cyan: "bg-cyan-500/10 border-cyan-500/20 shadow-cyan-500/10",
  electric: "bg-blue-400/10 border-blue-400/20 shadow-blue-400/10",
  violet: "bg-violet-500/10 border-violet-500/20 shadow-violet-500/10",
  magenta: "bg-pink-500/10 border-pink-500/20 shadow-pink-500/10",
  amber: "bg-amber-500/10 border-amber-500/20 shadow-amber-500/10",
  red: "bg-red-500/10 border-red-500/20 shadow-red-500/10",
  teal: "bg-teal-500/10 border-teal-500/20 shadow-teal-500/10",
  gold: "bg-yellow-500/10 border-yellow-500/20 shadow-yellow-500/10",
  aqua: "bg-cyan-300/10 border-cyan-300/20 shadow-cyan-300/10",
  slate: "bg-slate-500/10 border-slate-500/20 shadow-slate-500/10"
};

export function DetailPanel({ stage, scenario }: Props) {
  if (!stage && !scenario) {
    return (
      <div className="surface-panel rounded-2xl p-8 sticky top-4 border flex flex-col items-center justify-center text-center text-muted-foreground h-[400px]">
        <Info className="size-8 mb-4 opacity-20" />
        <p className="text-sm max-w-[200px]">Select a scenario on the left or click any stage in the flowchart to view deep-dive details.</p>
      </div>
    );
  }

  // If a scenario is active but no stage is specifically selected, show the scenario details.
  if (!stage && scenario) {
    return (
      <div className="surface-panel rounded-2xl p-6 sticky top-4 border flex flex-col gap-6 animate-in slide-in-from-bottom-2 duration-300">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className={cn("flex h-2 w-2 rounded-full animate-pulse", colorMap[scenario.colorTheme].replace('text-', 'bg-'))} />
            <h3 className={cn("text-xs font-bold tracking-widest uppercase", colorMap[scenario.colorTheme])}>Scenario Active</h3>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">{scenario.label}</h2>
        </div>

        <div className="p-4 bg-muted/30 rounded-xl border">
          <p className="text-sm leading-relaxed text-muted-foreground">{scenario.description}</p>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Final System State</h4>
          <div className={cn("inline-flex items-center px-3 py-1 rounded-full font-bold text-xs border", bgMap[scenario.colorTheme], colorMap[scenario.colorTheme])}>
            {scenario.finalOutcome}
          </div>
        </div>
      </div>
    );
  }

  // Otherwise, show the specifically selected stage details.
  const s = stage!;
  const Icon = s.icon;

  return (
    <div className="surface-panel rounded-2xl p-6 sticky top-4 border flex flex-col gap-6 animate-in slide-in-from-bottom-2 duration-300 max-h-[85vh] overflow-y-auto custom-scrollbar">
      
      <div className="flex items-start gap-4 pb-4 border-b">
        <div className={cn("p-3 rounded-xl border shrink-0 shadow-lg", bgMap[s.color], colorMap[s.color])}>
          <Icon className="size-6" />
        </div>
        <div>
          <h2 className="text-xl font-bold tracking-tight">{s.label}</h2>
          {s.sublabel && <p className="text-xs font-semibold text-muted-foreground tracking-widest uppercase mt-1">{s.sublabel}</p>}
        </div>
      </div>

      <div className="space-y-6">
        <div className="space-y-1.5">
          <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">What is this?</h4>
          <p className="text-sm leading-relaxed">{s.whatIsThis}</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-1.5"><LogIn className="size-3" /> What goes in?</h4>
            <p className="text-sm leading-relaxed text-muted-foreground">{s.whatGoesIn}</p>
          </div>
          <div className="space-y-1.5">
            <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-1.5"><LogOut className="size-3" /> What comes out?</h4>
            <p className="text-sm leading-relaxed text-muted-foreground">{s.whatComesOut}</p>
          </div>
        </div>

        <div className="space-y-1.5">
          <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-1.5"><Code className="size-3" /> What happens?</h4>
          <p className="text-sm leading-relaxed bg-muted/30 p-3 rounded-lg border">{s.whatHappens}</p>
        </div>

        <div className="space-y-1.5 p-4 bg-primary/5 border border-primary/10 rounded-lg">
          <h4 className="text-[10px] font-bold text-primary uppercase tracking-widest flex items-center gap-2"><AlertTriangle className="size-3" /> Why does it matter?</h4>
          <p className="text-sm leading-relaxed mt-1 text-foreground">{s.whyDoesItMatter}</p>
        </div>
      </div>

      {(s.evidenceType || s.whereToSeeIt) && (
        <div className="pt-6 border-t flex flex-col gap-3">
          {s.evidenceType && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <FileText className="size-3" />
              <span className="font-semibold uppercase tracking-widest">Evidence:</span> {s.evidenceType}
            </div>
          )}
          {s.whereToSeeIt && (
            <Link href={s.whereToSeeIt} className="w-full mt-2">
              <Button variant="outline" size="sm" className="w-full justify-between">
                <span className="flex items-center gap-2"><LayoutDashboard className="size-3" /> View Evidence</span>
                <span>→</span>
              </Button>
            </Link>
          )}
        </div>
      )}

    </div>
  );
}
