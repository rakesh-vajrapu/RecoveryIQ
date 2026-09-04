"use client";

import { Activity, BarChart3, BrainCircuit, ChevronRight, CreditCard, HeartPulse, ListChecks, Menu, Moon, ShieldCheck, Sun, X } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { cn } from "@/lib/utils";

const navigation = [
  { label: "Command Center", href: "/", icon: Activity },
  { label: "Payment Health", href: "/payment-health", icon: HeartPulse },
  { label: "Recovery Queue", href: "/recovery-cases", icon: ListChecks },
  { label: "Decision Trace", href: "/decision-trace", icon: BrainCircuit },
  { label: "Batch Explorer", href: "/batch-explorer", icon: BarChart3 },
  { label: "Safety Lab", href: "/safety-lab", icon: ShieldCheck },
  { label: "Razorpay", href: "/integrations/razorpay", icon: CreditCard },
  { label: "Evaluation Lab", href: "/evaluation", icon: BarChart3 },
];

function routeLabel(pathname: string): string {
  if (pathname.startsWith("/recovery-cases/") && pathname.endsWith("/audit")) return "Audit timeline";
  if (pathname.startsWith("/recovery-cases/")) return "Recovery case";
  return navigation.find((item) => item.href === pathname)?.label ?? "Operations";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[264px_minmax(0,1fr)]">
      <aside className={cn("fixed inset-y-0 left-0 z-50 flex w-[284px] flex-col border-r bg-[var(--sidebar)]/95 backdrop-blur-2xl transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:w-auto lg:translate-x-0", menuOpen ? "translate-x-0" : "-translate-x-full")}>
        <div className="flex h-[76px] items-center gap-3 border-b px-5">
          <Link href="/" className="focus-ring group flex min-w-0 items-center gap-3 rounded-xl">
            <LogoMark />
            <span className="min-w-0"><span className="block text-sm font-bold tracking-[-0.01em] transition-all duration-300 group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-primary group-hover:to-[#0b7b91]">RecoveryIQ</span><span className="block truncate text-[10px] font-medium tracking-[0.06em] text-muted-foreground uppercase">Revenue intelligence</span></span>
          </Link>
          <button type="button" onClick={() => setMenuOpen(false)} aria-label="Close navigation" className="focus-ring ml-auto grid size-9 place-items-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"><X className="size-4" /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-5">
          <p className="eyebrow mb-3 px-3">Workspace</p>
          <nav aria-label="Product navigation">
            <ul className="space-y-1.5">
              {navigation.map((item) => {
                const active = item.href === "/" ? pathname === "/" : pathname === item.href || pathname.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link href={item.href} onClick={() => setMenuOpen(false)} aria-current={active ? "page" : undefined} className={cn("focus-ring group relative flex items-center gap-3 overflow-hidden rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200", active ? "bg-accent text-accent-foreground shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--primary)_14%,transparent)]" : "text-muted-foreground hover:bg-[var(--sidebar-hover)] hover:text-foreground")}>
                      {active && <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary" />}
                      <Icon className={cn("size-4 transition-transform group-hover:scale-110", active && "text-primary")} />
                      <span>{item.label}</span>
                      <ChevronRight className={cn("ml-auto size-3.5 -translate-x-1 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-60", active && "translate-x-0 opacity-50")} />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </div>

        <div className="m-3 rounded-2xl border bg-card/70 p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold"><span className="grid size-7 place-items-center rounded-lg bg-accent text-primary"><ShieldCheck className="size-4" /></span>Bounded autonomy</div>
          <p className="mt-3 text-[11px] leading-5 text-muted-foreground">Policy authorizes. Providers verify. AI explains supplied evidence only.</p>
          <div className="mt-3 flex items-center gap-2 border-t pt-3 text-[10px] font-semibold tracking-[0.12em] text-primary uppercase"><span className="status-pulse flex items-center gap-2">Razorpay Test evidence</span></div>
        </div>
      </aside>

      {menuOpen && <button type="button" aria-label="Close navigation overlay" onClick={() => setMenuOpen(false)} className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-sm lg:hidden" />}

      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-[76px] items-center gap-3 border-b bg-[var(--surface-glass)] px-4 backdrop-blur-2xl sm:px-7 lg:px-9">
          <button type="button" onClick={() => setMenuOpen(true)} aria-label="Open navigation" className="focus-ring grid size-10 place-items-center rounded-xl border bg-card text-muted-foreground shadow-sm hover:text-foreground lg:hidden"><Menu className="size-4.5" /></button>
          <div className="min-w-0"><p className="eyebrow truncate">Operations / {routeLabel(pathname)}</p><p className="mt-0.5 truncate text-sm font-semibold group cursor-default"><span className="transition-all duration-300 group-hover:text-primary group-hover:drop-shadow-[0_0_8px_rgba(14,165,122,0.5)]">RecoveryIQ</span> control plane</p></div>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <div className="hidden items-center gap-2 rounded-full border bg-card/75 px-3 py-1.5 text-[10px] font-semibold tracking-[0.11em] text-primary uppercase shadow-sm sm:flex"><span className="size-1.5 rounded-full bg-primary shadow-[0_0_9px_var(--primary)]" />Reviewer demo runtime</div>
            <ThemeToggle />
          </div>
        </header>
        <main className="relative min-h-[calc(100vh-76px)] overflow-hidden">
          <div className="ambient-orb pointer-events-none absolute -top-32 right-[-7rem] size-96 rounded-full bg-primary/[0.055] blur-3xl" />
          <div key={pathname} className="page-enter relative mx-auto max-w-[1540px] px-4 py-6 sm:px-7 sm:py-8 lg:px-10 lg:py-10">{children}</div>
        </main>
      </div>
    </div>
  );
}

function LogoMark() {
  return <span className="relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-xl shadow-[0_8px_20px_var(--glow-primary)] transition-transform duration-300 group-hover:rotate-[-3deg] group-hover:scale-105"><Image src="/logo.jpg" alt="RecoveryIQ Logo" width={40} height={40} className="object-cover" /><span className="absolute -right-1 -top-1 size-3 rounded-full border border-white/50 bg-white/20" /></span>;
}

function ThemeToggle() {
  const toggleTheme = () => {
    const next = document.documentElement.classList.contains("dark") ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    document.documentElement.dataset.theme = next;
    localStorage.setItem("recoveriq-theme", next);
  };
  return (
    <button type="button" onClick={toggleTheme} aria-label="Toggle light and dark theme" className="focus-ring group relative grid size-10 place-items-center overflow-hidden rounded-xl border bg-card text-muted-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:text-primary hover:shadow-[0_8px_24px_var(--glow-primary)] active:translate-y-0">
      <Moon className="size-4 transition-transform duration-300 group-hover:-rotate-12 dark:hidden" />
      <Sun className="hidden size-4 transition-transform duration-300 group-hover:rotate-45 dark:block" />
    </button>
  );
}
