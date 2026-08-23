import { BarChart3, Beaker, Bot, CheckCircle2, DatabaseZap, ShieldCheck, Sparkles } from "lucide-react";

import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";

const policies = [
  { label: "Sequential Policy V2", value: 75.97, color: "bg-primary" },
  { label: "Observable rules", value: 64.6, color: "bg-sky-500" },
  { label: "Reminder + Retry", value: 53.09, color: "bg-violet-500" },
];

export default function EvaluationPage() {
  return (
    <>
      <PageHeader eyebrow="Frozen evaluation evidence" title="Evidence before claims." description="A transparent view of the sealed simulator, model, policy, detector, and Test Mode results that support this submission." icon={BarChart3} />
      <div className="space-y-5">
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Backend tests" value="54 / 54" detail="Latest local verification" icon={CheckCircle2} tone="emerald" progress={100} />
          <MetricCard label="Simulator tests" value="128 / 128" detail="Frozen intelligence boundaries" icon={Beaker} tone="cyan" progress={100} />
          <MetricCard label="Policy violations" value="0" detail="27,406 sealed episodes" icon={ShieldCheck} tone="violet" progress={0} />
          <MetricCard label="Test Mode proof" value="₹1.00" detail="Exactly-once recovered outcome" icon={DatabaseZap} tone="amber" progress={100} />
        </section>
        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
          <article className="surface-panel rounded-2xl p-5 sm:p-6"><div className="flex items-start justify-between"><div><p className="eyebrow">Sealed policy comparison</p><h2 className="mt-2 text-lg font-semibold">Episode recovery rate</h2></div><span className="rounded-full border bg-card px-3 py-1 text-[10px] font-semibold text-muted-foreground">Synthetic evidence</span></div><div className="mt-8 space-y-6">{policies.map((policy) => <div key={policy.label}><div className="mb-2 flex items-center justify-between gap-4"><p className="text-xs font-medium">{policy.label}</p><p className="font-mono text-xs font-semibold">{policy.value.toFixed(2)}%</p></div><div className="h-3 overflow-hidden rounded-full bg-muted"><div className={`h-full rounded-full ${policy.color}`} style={{ width: `${policy.value}%` }} /></div></div>)}</div><p className="mt-7 border-t pt-4 text-[11px] leading-5 text-muted-foreground">Results come from paired synthetic evaluation and are not production revenue claims.</p></article>
          <div className="grid gap-4"><EvidenceCard icon={Bot} title="Recovery Model V2" body="Passed its held-out gate on 62,918 decisions across 27,451 synthetic episodes with frozen isotonic calibration." /><EvidenceCard icon={ShieldCheck} title="Detector V2" body="Failed its hard-policy safety gate and remains advisory-only. It is excluded from primary Model V2 features." /><EvidenceCard icon={Sparkles} title="Explanation layer" body="Groq is optional, structured, and non-authoritative. Deterministic fallback preserves availability without changing recovery." /></div>
        </section>
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.055] p-5 text-sm leading-6 text-amber-900 dark:text-amber-100"><strong>Reproducibility guard:</strong> all overall-final seeds remain untouched. Existing frozen artifacts are evidence, not mutable application state.</div>
      </div>
    </>
  );
}

function EvidenceCard({ icon: Icon, title, body }: { icon: typeof Bot; title: string; body: string }) {
  return <article className="surface-panel interactive-panel rounded-2xl p-5"><div className="flex items-start gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent text-primary"><Icon className="size-4" /></span><div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-2 text-xs leading-5 text-muted-foreground">{body}</p></div></div></article>;
}

