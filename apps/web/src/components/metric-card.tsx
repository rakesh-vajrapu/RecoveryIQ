import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

const tones = {
  emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  cyan: "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300",
  violet: "bg-violet-500/10 text-violet-700 dark:text-violet-300",
  amber: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  rose: "bg-rose-500/10 text-rose-700 dark:text-rose-300",
  blue: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
};

export function MetricCard({ label, value, detail, icon: Icon, tone = "emerald", progress }: { label: string; value: string; detail: string; icon: LucideIcon; tone?: keyof typeof tones; progress?: number }) {
  const boundedProgress = Math.max(0, Math.min(100, progress ?? 0));
  return (
    <article className="surface-panel interactive-panel group rounded-2xl p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">{label}</p>
          <p className="mt-3 text-2xl font-bold tracking-[-0.035em] sm:text-[1.7rem]">{value}</p>
        </div>
        <span className={cn("grid size-10 place-items-center rounded-xl transition-transform duration-300 group-hover:rotate-3 group-hover:scale-105", tones[tone])}><Icon className="size-4.5" /></span>
      </div>
      <div className="mt-5 h-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${progress === undefined ? 32 : boundedProgress}%` }} /></div>
      <p className="mt-3 text-[11px] leading-5 text-muted-foreground">{detail}</p>
    </article>
  );
}

