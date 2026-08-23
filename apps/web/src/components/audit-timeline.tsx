"use client";

import { ArrowLeft, CheckCircle2, Clock3, FileClock, RefreshCw, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getRecoveryCase, getRecoveryCaseAudit, type AuditEvent, type RecoveryCaseDetail } from "@/lib/api";
import { formatDate, shortId, titleCase } from "@/lib/format";

type AuditData = { recoveryCase: RecoveryCaseDetail; events: AuditEvent[] };

export function AuditTimelineView({ id }: { id: string }) {
  const load = useCallback(async (signal: AbortSignal): Promise<AuditData> => { const [recoveryCase, events] = await Promise.all([getRecoveryCase(id, signal), getRecoveryCaseAudit(id, signal)]); return { recoveryCase, events }; }, [id]);
  const resource = useApiResource(load);
  return <><PageHeader eyebrow="Immutable evidence" title="Recovery audit timeline" description="Chronological, redacted audit records associated with the case correlation ID." icon={FileClock} actions={<><Button variant="outline" nativeButton={false} render={<Link href={`/recovery-cases/${id}`} />}><ArrowLeft />Case detail</Button><Button variant="ghost" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} /></Button></>} />{resource.loading && <LoadingPanel />}{resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}{resource.data && <AuditContent data={resource.data} />}</>;
}

function AuditContent({ data }: { data: AuditData }) {
  return <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]"><article className="surface-panel rounded-2xl p-5 sm:p-7"><div className="flex items-center justify-between border-b pb-5"><div><p className="font-mono text-xs font-semibold">Case {shortId(data.recoveryCase.id, 12)}</p><p className="mt-1 font-mono text-[10px] text-muted-foreground">Correlation {shortId(data.recoveryCase.correlation_id, 16)}</p></div><StatusBadge status={data.recoveryCase.status} /></div>{data.events.length === 0 ? <div className="mt-5"><EmptyPanel title="No audit events recorded" description="The case exists, but no redacted audit event is associated with its correlation ID." /></div> : <ol className="relative mt-6 space-y-0 before:absolute before:top-3 before:bottom-3 before:left-[17px] before:w-px before:bg-border">{data.events.map((event, index) => <li key={event.id} className="relative grid grid-cols-[36px_1fr] gap-4 pb-7 last:pb-0"><span className="relative z-10 grid size-9 place-items-center rounded-xl border bg-card text-primary shadow-sm">{index === data.events.length - 1 ? <CheckCircle2 className="size-4" /> : <Clock3 className="size-4" />}</span><div className="rounded-2xl border bg-card/45 p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="text-sm font-semibold">{titleCase(event.event_type)}</h2><p className="mt-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">{titleCase(event.entity_type)} · {titleCase(event.actor)}</p></div><time className="font-mono text-[10px] text-muted-foreground">{formatDate(event.created_at)}</time></div><Metadata metadata={event.event_metadata} /></div></li>)}</ol>}</article><aside className="space-y-4"><article className="surface-panel rounded-2xl p-5"><ShieldCheck className="size-5 text-primary" /><h2 className="mt-4 text-sm font-semibold">Audit boundary</h2><p className="mt-2 text-xs leading-5 text-muted-foreground">Events contain redacted operational metadata. Raw provider payloads, credentials, payment secrets, and unnecessary PII are never displayed.</p></article><article className="surface-panel rounded-2xl p-5"><p className="eyebrow">Recorded objects</p><dl className="mt-4 space-y-3"><CountRow label="Decisions" value={data.recoveryCase.decisions.length} /><CountRow label="Plans" value={data.recoveryCase.plans.length} /><CountRow label="Executions" value={data.recoveryCase.executions.length} /><CountRow label="Outcomes" value={data.recoveryCase.outcomes.length} /><CountRow label="Attribution" value={data.recoveryCase.attribution ? 1 : 0} /></dl></article></aside></div>;
}

function Metadata({ metadata }: { metadata: Record<string, unknown> }) {
  const safeEntries = Object.entries(metadata).filter(([, value]) => typeof value === "string" || typeof value === "number" || typeof value === "boolean").slice(0, 8);
  if (!safeEntries.length) return <p className="mt-3 text-[11px] text-muted-foreground">No displayable metadata.</p>;
  return <dl className="mt-4 grid gap-2 sm:grid-cols-2">{safeEntries.map(([key, value]) => <div key={key} className="rounded-lg bg-muted/50 px-3 py-2"><dt className="text-[9px] font-bold tracking-wider text-muted-foreground uppercase">{titleCase(key)}</dt><dd className="mt-1 break-words font-mono text-[10px]">{String(value)}</dd></div>)}</dl>;
}

function CountRow({ label, value }: { label: string; value: number }) { return <div className="flex items-center rounded-xl border bg-card/50 px-3 py-2.5"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="ml-auto font-mono text-xs font-semibold">{value}</dd></div>; }
