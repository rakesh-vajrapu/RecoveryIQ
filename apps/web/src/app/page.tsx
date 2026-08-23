import {
  Activity,
  ArrowRight,
  BarChart3,
  CircleDollarSign,
  FileSearch,
  HeartPulse,
  ListChecks,
  ShieldCheck,
} from "lucide-react";

import { ApiStatus } from "@/components/api-status";

const navigation = [
  { label: "Command Center", icon: Activity, current: true },
  { label: "Payment Health", icon: HeartPulse },
  { label: "Recovery Queue", icon: ListChecks },
  { label: "Decision Trace", icon: FileSearch },
  { label: "Evaluation Lab", icon: BarChart3 },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-[#090d12] text-slate-100">
      <div className="mx-auto grid min-h-screen max-w-[1680px] lg:grid-cols-[252px_1fr]">
        <aside className="border-b border-white/[0.07] bg-[#0c1118] lg:border-r lg:border-b-0">
          <div className="flex h-[74px] items-center justify-between px-5 lg:justify-start lg:gap-3 lg:px-6">
            <div className="grid size-9 place-items-center rounded-lg border border-emerald-400/20 bg-emerald-400/10 font-mono text-sm font-bold text-emerald-300">
              RQ
            </div>
            <div>
              <p className="text-sm font-semibold tracking-wide text-white">RecoverIQ</p>
              <p className="text-[11px] text-slate-500">Revenue recovery control plane</p>
            </div>
            <span className="rounded-full border border-cyan-400/20 bg-cyan-400/[0.08] px-2.5 py-1 text-[10px] font-semibold tracking-[0.12em] text-cyan-300 lg:hidden">
              SIMULATION
            </span>
          </div>

          <nav aria-label="Product navigation" className="hidden px-3 py-5 lg:block">
            <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.16em] text-slate-600 uppercase">
              Operations
            </p>
            <ul className="space-y-1">
              {navigation.map(({ label, icon: Icon, current }) => (
                <li key={label}>
                  <div
                    aria-current={current ? "page" : undefined}
                    aria-disabled={!current}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${
                      current
                        ? "border border-white/[0.06] bg-white/[0.055] text-white shadow-sm"
                        : "text-slate-500"
                    }`}
                  >
                    <Icon className={`size-4 ${current ? "text-emerald-300" : ""}`} />
                    <span>{label}</span>
                    {!current && (
                      <span className="ml-auto text-[9px] tracking-wider uppercase">Soon</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </nav>

          <div className="hidden px-6 lg:absolute lg:bottom-6 lg:block lg:w-[252px]">
            <div className="border-t border-white/[0.07] pt-5">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <ShieldCheck className="size-4 text-emerald-400" />
                <span>Bounded autonomy</span>
              </div>
              <p className="mt-2 text-[11px] leading-5 text-slate-600">
                Deterministic policy authorizes. Optional LLMs only explain validated evidence.
              </p>
            </div>
          </div>
        </aside>

        <main className="min-w-0">
          <header className="flex h-[74px] items-center justify-between border-b border-white/[0.07] px-5 sm:px-8">
            <div>
              <p className="text-[10px] font-semibold tracking-[0.16em] text-emerald-400 uppercase">
                Operations / Command Center
              </p>
              <h1 className="mt-1 text-base font-semibold text-white">Submission status</h1>
            </div>
            <div className="hidden items-center gap-3 sm:flex">
              <span className="text-xs text-slate-500">Mode</span>
              <span className="rounded-full border border-cyan-400/20 bg-cyan-400/[0.08] px-3 py-1.5 text-[10px] font-semibold tracking-[0.12em] text-cyan-300">
                SIMULATION
              </span>
            </div>
          </header>

          <div className="px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
            <section className="mb-8 flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
              <div>
                <div className="mb-4 flex items-center gap-2 text-xs text-slate-500">
                  <span className="size-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.7)]" />
                  Phase 7.5 verified
                </div>
                <h2 className="max-w-3xl text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">
                  Bounded recovery intelligence with verified execution safety.
                </h2>
                <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
                  RecoverIQ combines reproducible action-level evidence, deterministic sequential
                  policy, Razorpay Test Mode execution, exactly-once attribution, and optional
                  explanation-only LLM enrichment.
                </p>
              </div>
              <div className="flex items-center gap-2 self-start rounded-lg border border-amber-300/15 bg-amber-300/[0.06] px-3 py-2 text-xs text-amber-200/80">
                <CircleDollarSign className="size-4" />
                Synthetic evaluation · Razorpay Test Mode
              </div>
            </section>

            <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
              <ApiStatus />

              <article className="rounded-xl border border-white/[0.08] bg-[#0d131b] p-5 sm:p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold tracking-[0.12em] text-slate-500 uppercase">
                      Environment
                    </p>
                    <h3 className="mt-2 text-lg font-medium text-white">Safe local development</h3>
                  </div>
                  <ShieldCheck className="size-5 text-emerald-400" />
                </div>
                <dl className="mt-6 space-y-4 text-sm">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                    <dt className="text-slate-500">Database</dt>
                    <dd className="font-mono text-xs text-slate-300">SQLite fallback</dd>
                  </div>
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                    <dt className="text-slate-500">Background tasks</dt>
                    <dd className="font-mono text-xs text-slate-300">Celery eager</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="text-slate-500">External credentials</dt>
                    <dd className="font-mono text-xs text-emerald-300">Optional · Test only</dd>
                  </div>
                </dl>
              </article>
            </section>

            <section className="mt-4 grid gap-4 md:grid-cols-3">
              {[
                {
                  step: "01",
                  title: "Observe safely",
                  body: "Leakage-safe evidence and advisory degradation signals preserve the boundary between observation and hidden truth.",
                },
                {
                  step: "02",
                  title: "Score bounded actions",
                  body: "Calibrated trajectory-aware probabilities feed deterministic ERV, support, budget, and abstention rules.",
                },
                {
                  step: "03",
                  title: "Verify and attribute",
                  body: "Signed Test Mode outcomes are matched, deduplicated, audited, and attributed exactly once.",
                },
              ].map((item) => (
                <article
                  key={item.step}
                  className="group rounded-xl border border-white/[0.07] bg-[#0b1017] p-5 transition-colors hover:border-white/[0.12]"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-emerald-400">{item.step}</span>
                    <ArrowRight className="size-4 text-slate-700 transition-colors group-hover:text-slate-500" />
                  </div>
                  <h3 className="mt-8 text-sm font-medium text-slate-200">{item.title}</h3>
                  <p className="mt-2 text-xs leading-5 text-slate-500">{item.body}</p>
                </article>
              ))}
            </section>

            <p className="mt-8 text-center text-[11px] text-slate-700">
              RecoverIQ Phase 7.5 · Synthetic evidence · Razorpay Test Mode · No Live Mode
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
