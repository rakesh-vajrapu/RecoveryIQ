import { titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  RECOVERED: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300", PAID: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300", CHARGED: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300", SUCCEEDED: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300", DETECTED: "border-cyan-500/20 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300", DIAGNOSING: "border-cyan-500/20 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300", SCORING: "border-violet-500/20 bg-violet-500/10 text-violet-700 dark:text-violet-300", POLICY_CHECK: "border-violet-500/20 bg-violet-500/10 text-violet-700 dark:text-violet-300", SCHEDULED: "border-blue-500/20 bg-blue-500/10 text-blue-700 dark:text-blue-300", WAITING: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300", EXECUTING: "border-blue-500/20 bg-blue-500/10 text-blue-700 dark:text-blue-300", HUMAN_REVIEW: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300", FAILED: "border-rose-500/20 bg-rose-500/10 text-rose-700 dark:text-rose-300", STOPPED: "border-slate-500/20 bg-slate-500/10 text-slate-600 dark:text-slate-300", CANCELLED: "border-slate-500/20 bg-slate-500/10 text-slate-600 dark:text-slate-300", EXPIRED: "border-orange-500/20 bg-orange-500/10 text-orange-700 dark:text-orange-300",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold tracking-[0.08em] uppercase", tones[status] ?? "border-border bg-muted text-muted-foreground", className)}><span className="size-1.5 rounded-full bg-current opacity-70" />{titleCase(status)}</span>;
}

