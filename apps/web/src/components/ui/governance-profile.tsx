"use client";

import { ShieldCheck, CalendarClock, Filter, ShieldAlert, CircleSlash, Database, Activity } from "lucide-react";
import { useCallback } from "react";

import { useApiResource } from "@/hooks/use-api-resource";
import { getGovernanceProfile, type GovernanceRule } from "@/lib/api";
import { LoadingPanel, ErrorPanel } from "@/components/ui/state-panel";

export function GovernanceProfilePanel() {
  const load = useCallback(async (signal: AbortSignal) => {
    return await getGovernanceProfile(signal);
  }, []);
  const resource = useApiResource(load);

  if (resource.loading) return <LoadingPanel />;
  if (resource.error) return <ErrorPanel message={resource.error} onRetry={resource.retry} />;
  if (!resource.data) return null;

  const profile = resource.data;
  const limits = profile.limits;
  const rules = profile.rules;

  const categories = [
    { id: "AUTONOMY_BOUND", label: "Autonomy Bounds" },
    { id: "ECONOMIC_STOP", label: "Economic Safety" },
    { id: "ACTION_FEASIBILITY", label: "Action Feasibility" },
    { id: "CUSTOMER_PROTECTION", label: "Customer Protection" },
    { id: "EVIDENCE_GATE", label: "Evidence Gates" },
    { id: "ACCOUNTING_SAFETY", label: "Accounting Safety" },
  ];

  return (
    <section className="mt-4 surface-panel overflow-hidden rounded-2xl">
      <div className="border-b bg-muted/40 px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <ShieldCheck className="size-4 text-primary" />
              RECOVERY GOVERNANCE PROFILE
            </h2>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground uppercase tracking-wider">
              {profile.profile_name} · FROZEN V{profile.policy_version} · {profile.evidence_lane}
            </p>
          </div>
          <div className="text-right">
            <p className="font-mono text-[10px] text-muted-foreground break-all max-w-[200px] truncate" title={profile.config_hash}>
              {profile.config_hash}
            </p>
          </div>
        </div>
      </div>

      <div className="p-5">
        <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Hard Limits</h3>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <LimitCard value={`${limits.recovery_horizon_hours}h`} label="Horizon" />
          <LimitCard value={limits.max_autonomous_interventions.toString()} label="Interventions" />
          <LimitCard value={limits.max_retries.toString()} label="Retries" />
          <LimitCard value={limits.max_contacts.toString()} label="Contacts" />
          <LimitCard value={`${limits.minimum_retry_interval_hours}h`} label="Min Retry Interval" />
        </div>
      </div>

      <div className="border-t p-5">
        <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Rules & Semantics</h3>
        <div className="grid gap-6 md:grid-cols-2">
          {categories.map(cat => {
            const catRules = rules.filter(r => r.category === cat.id);
            if (catRules.length === 0) return null;
            return (
              <div key={cat.id}>
                <h4 className="text-[11px] font-semibold uppercase tracking-widest text-primary/80 mb-3">{cat.label}</h4>
                <ul className="space-y-3">
                  {catRules.map(rule => (
                    <RuleItem key={rule.id} rule={rule} />
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function LimitCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border bg-card/40 p-3 text-center">
      <div className="text-lg font-bold">{value}</div>
      <div className="mt-1 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground leading-tight">
        {label}
      </div>
    </div>
  );
}

function RuleItem({ rule }: { rule: GovernanceRule }) {
  let icon = <Activity className="mt-0.5 size-4 shrink-0 text-muted-foreground" />;
  let badgeColor = "bg-muted text-muted-foreground";
  
  if (rule.enforcement === "STOP") {
    icon = <CircleSlash className="mt-0.5 size-4 shrink-0 text-red-500" />;
    badgeColor = "bg-red-500/10 text-red-500 border border-red-500/20";
  } else if (rule.enforcement === "HUMAN_REVIEW") {
    icon = <ShieldAlert className="mt-0.5 size-4 shrink-0 text-amber-500" />;
    badgeColor = "bg-amber-500/10 text-amber-500 border border-amber-500/20";
  } else if (rule.enforcement === "FILTER_ACTION") {
    icon = <Filter className="mt-0.5 size-4 shrink-0 text-blue-500" />;
    badgeColor = "bg-blue-500/10 text-blue-500 border border-blue-500/20";
  } else if (rule.enforcement === "SCHEDULE_ACTION") {
    icon = <CalendarClock className="mt-0.5 size-4 shrink-0 text-purple-500" />;
    badgeColor = "bg-purple-500/10 text-purple-500 border border-purple-500/20";
  } else if (rule.enforcement === "ACCOUNTING_INVARIANT") {
    icon = <Database className="mt-0.5 size-4 shrink-0 text-emerald-500" />;
    badgeColor = "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20";
  }

  return (
    <li className="flex items-start gap-3 text-sm">
      {icon}
      <div className="flex-1">
        <span className="font-semibold">{rule.id.replace(/_/g, ' ')}</span>
        <p className="text-xs text-muted-foreground leading-relaxed mt-0.5">{rule.effect}</p>
        <div className="mt-1.5 flex flex-wrap gap-2">
          <span className={`inline-flex items-center rounded-sm px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest ${badgeColor}`}>
            {rule.enforcement.replace(/_/g, ' ')}
          </span>
          {rule.episode_termination === "YES" && (
            <span className="inline-flex items-center rounded-sm px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest bg-red-500/10 text-red-500 border border-red-500/20">
              TERMINATES EPISODE
            </span>
          )}
        </div>
      </div>
    </li>
  );
}
