"use client";

import { ArchitectureScenario, SCENARIOS } from "@/lib/architecture-data";
import { cn } from "@/lib/utils";
import { RotateCcw, Play, Square } from "lucide-react";
import { Button } from "../ui/button";

interface Props {
  activeScenarioId: string | null;
  isPlaying: boolean;
  onSelectScenario: (scenario: ArchitectureScenario | null) => void;
  onTogglePlay: () => void;
}

export function ScenarioControls({ activeScenarioId, isPlaying, onSelectScenario, onTogglePlay }: Props) {
  return (
    <div className="surface-panel rounded-2xl p-4 sticky top-4 h-fit border flex flex-col gap-3 w-full">
      <div className="flex items-center justify-between pb-2 border-b">
        <h3 className="font-bold text-sm tracking-widest text-muted-foreground uppercase">Interactive Scenarios</h3>
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={() => onSelectScenario(null)}
          className={cn("h-7 text-xs", !activeScenarioId && "opacity-50 pointer-events-none")}
        >
          <RotateCcw className="size-3 mr-1" /> Reset
        </Button>
      </div>
      
      <div className="flex flex-col gap-2">
        {SCENARIOS.map((scenario) => {
          const isActive = activeScenarioId === scenario.id;
          return (
            <div key={scenario.id} className="flex flex-col gap-1">
              <button
                onClick={() => onSelectScenario(scenario)}
                className={cn(
                  "text-left p-3 rounded-xl transition-all duration-300 text-sm border hover:border-primary/40",
                  isActive 
                    ? "bg-primary/10 border-primary/50 text-primary shadow-sm shadow-primary/20 font-medium" 
                    : "bg-muted/30 border-transparent text-muted-foreground hover:bg-muted/50"
                )}
              >
                {scenario.label}
              </button>
              
              {isActive && (
                <div className="px-1 pt-1 pb-2 animate-in slide-in-from-top-1 duration-300">
                  <Button 
                    size="sm" 
                    className="w-full justify-center gap-2 tracking-widest font-bold uppercase text-[11px]"
                    variant={isPlaying ? "destructive" : "default"}
                    onClick={(e) => {
                      e.stopPropagation();
                      onTogglePlay();
                    }}
                  >
                    {isPlaying ? <><Square className="size-3" /> STOP PLAYBACK</> : <><Play className="size-3" /> PLAY PATH</>}
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
