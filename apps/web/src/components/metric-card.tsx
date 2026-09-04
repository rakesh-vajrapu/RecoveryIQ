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

export function MetricCard({ label, value, detail, icon: Icon, tone = "emerald", progress, badge, subtext }: { label: string; value: string; detail: string; icon: LucideIcon; tone?: keyof typeof tones; progress?: number; badge?: string; subtext?: string }) {
  const boundedProgress = Math.max(0, Math.min(100, progress ?? 0));
  return (
    <article className="surface-panel group flex min-h-[190px] flex-col rounded-2xl p-5 hover:-translate-y-1.5 transition-all duration-500 hover:shadow-xl hover:border-primary/40 dark:hover:shadow-[0_10px_40px_rgba(16,185,129,0.15)] relative overflow-hidden cursor-pointer">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="eyebrow truncate" title={label}>{label}</p>
          <p className="mt-3 truncate text-2xl font-bold tracking-[-0.035em] sm:text-[1.7rem]" title={value}>{value}</p>
        </div>
        <span className={cn("shrink-0 grid size-10 place-items-center rounded-xl transition-transform duration-300 group-hover:rotate-3 group-hover:scale-105", tones[tone])}><Icon className="size-4.5" /></span>
      </div>
      <div className="mt-auto pt-5">
        {badge && <div className="mb-2 inline-flex rounded border border-current bg-transparent px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest opacity-80">{badge}</div>}
        <div className="h-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${progress === undefined ? 32 : boundedProgress}%` }} /></div>
        <div className="mt-3 flex items-center justify-between gap-2">
          <p className="truncate text-[11px] leading-5 text-muted-foreground min-w-0 flex-1" title={detail}>{detail}</p>
          {subtext && <p className="shrink-0 text-[9px] font-bold text-muted-foreground">{subtext}</p>}
        </div>
      </div>
    </article>
  );
}
