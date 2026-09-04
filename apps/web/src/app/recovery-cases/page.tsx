"use client";

import { ArrowUpDown, Eye, ListChecks, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getRecoveryCases } from "@/lib/api";
import { formatDate, formatMoney, shortId, titleCase } from "@/lib/format";

type SortMode = "newest" | "oldest" | "amount-high" | "amount-low";

export default function RecoveryCasesPage() {
  const router = useRouter();
  const load = useCallback((signal: AbortSignal) => getRecoveryCases(signal), []);
  const resource = useApiResource(load);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [source, setSource] = useState("ALL");
  const [sort, setSort] = useState<SortMode>("newest");

  const statuses = useMemo(() => Array.from(new Set(resource.data?.map((item) => item.status) ?? [])).sort(), [resource.data]);
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return [...(resource.data ?? [])].filter((item) => {
      const matchesQuery = !normalized || item.id.toLowerCase().includes(normalized) || item.correlation_id.toLowerCase().includes(normalized) || item.currency.toLowerCase().includes(normalized) || item.failure_type.toLowerCase().includes(normalized) || item.payment_method.toLowerCase().includes(normalized);
      return matchesQuery && (status === "ALL" || item.status === status) && (source === "ALL" || item.source === source);
    }).sort((left, right) => {
      if (sort === "oldest") return new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
      if (sort === "amount-high") return right.amount_minor - left.amount_minor;
      if (sort === "amount-low") return left.amount_minor - right.amount_minor;
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    });
  }, [query, resource.data, sort, source, status]);

  return (
    <>
      <PageHeader eyebrow="Recovery operations" title="Every opportunity, one auditable queue." description="Search, filter, and inspect persisted recovery cases. References are anonymous correlation IDs; customer identity is intentionally not exposed by this API." icon={ListChecks} actions={<Button variant="outline" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} />Refresh</Button>} />
      {resource.loading && <LoadingPanel label="Loading recovery cases" />}
      {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
      {resource.data && (
        <div className="surface-panel overflow-hidden rounded-2xl">
          <div className="grid gap-3 border-b p-4 sm:p-5 lg:grid-cols-[minmax(180px,1fr)_140px_170px_150px_auto] xl:grid-cols-[minmax(240px,1fr)_175px_190px_190px_auto]">
            <label className="relative block"><span className="sr-only">Search recovery cases</span><Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search case or reference…" className="focus-ring h-11 w-full rounded-xl border bg-card pl-10 pr-4 text-sm shadow-sm placeholder:text-muted-foreground/70" /></label>
            <label><span className="sr-only">Filter by status</span><select value={status} onChange={(event) => setStatus(event.target.value)} className="focus-ring h-11 w-full rounded-xl border bg-card px-3 text-sm shadow-sm"><option value="ALL">All statuses</option>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label><span className="sr-only">Filter by evidence source</span><select value={source} onChange={(event) => setSource(event.target.value)} className="focus-ring h-11 w-full rounded-xl border bg-card px-3 text-sm shadow-sm"><option value="ALL">All evidence sources</option><option value="DEMO_SYNTHETIC">Demo / Synthetic</option><option value="RAZORPAY_TEST_MODE">Razorpay Test Mode</option><option value="LOCAL_UNVERIFIED">Local / Unverified</option></select></label>
            <label><span className="sr-only">Sort recovery cases</span><select value={sort} onChange={(event) => setSort(event.target.value as SortMode)} className="focus-ring h-11 w-full rounded-xl border bg-card px-3 text-sm shadow-sm"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="amount-high">Amount: high to low</option><option value="amount-low">Amount: low to high</option></select></label>
            <div className="flex items-center justify-end gap-2 rounded-xl border bg-[var(--surface-soft)] px-3 text-xs text-muted-foreground"><ArrowUpDown className="size-3.5" /><span>{filtered.length} of {resource.data.length}</span></div>
          </div>

          {filtered.length === 0 ? <div className="p-5"><EmptyPanel title={resource.data.length ? "No cases match these filters" : "No recovery cases yet"} description={resource.data.length ? "Try a different reference, status, or sort option." : "Cases will appear here when the backend records a recoverable payment failure."} /></div> : (
            <>
            <div className="divide-y xl:hidden">
              {filtered.map((item) => <article key={item.id} className="p-4 transition-colors hover:bg-muted/30"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><SourceBadge source={item.source} /><Link href={`/recovery-cases/${item.id}`} className="focus-ring mt-2 block truncate rounded-md font-mono text-xs font-semibold hover:text-primary">Case {shortId(item.id, 12)}</Link><p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">Ref {shortId(item.correlation_id, 14)}</p></div><StatusBadge status={item.status} /></div><dl className="mt-4 grid grid-cols-2 gap-3 rounded-xl border bg-[var(--surface-soft)] p-3"><Datum label="Amount" value={formatMoney(item.amount_minor, item.currency)} strong /><Datum label="Failure" value={titleCase(item.failure_type)} /><Datum label="Method" value={titleCase(item.payment_method)} /><Datum label="Decision" value={item.decision_reason ? titleCase(item.decision_reason) : "Not recorded"} /><Datum label="Created" value={formatDate(item.created_at)} /><Datum label="Last activity" value={formatDate(item.last_activity_at)} /></dl><Button variant="outline" size="sm" className="mt-3 w-full" nativeButton={false} render={<Link href={`/recovery-cases/${item.id}`} />}><Eye className="size-3.5" />Open case</Button></article>)}
            </div>
            <div className="hidden xl:block">
              <table className="w-full table-fixed text-left">
                <colgroup><col className="w-[14%]" /><col className="w-[12%]" /><col className="w-[16%]" /><col className="w-[11%]" /><col className="w-[12%]" /><col className="w-[14%]" /><col className="w-[10.5%]" /><col className="w-[10.5%]" /></colgroup>
                <thead className="bg-muted/45 text-[10px] font-bold tracking-[0.12em] text-muted-foreground uppercase"><tr><th className="px-5 py-3.5">Case</th><th className="px-3 py-3.5">Source</th><th className="px-3 py-3.5">Failure / method</th><th className="px-3 py-3.5">Amount</th><th className="px-3 py-3.5">Status</th><th className="px-3 py-3.5">Decision</th><th className="px-3 py-3.5">Created</th><th className="px-3 py-3.5">Last activity</th></tr></thead>
                <tbody className="divide-y">{filtered.map((item) => <tr key={item.id} onClick={() => router.push(`/recovery-cases/${item.id}`)} className="group transition-all duration-300 cursor-pointer hover:bg-emerald-500/10 hover:shadow-[inset_0_0_15px_rgba(16,185,129,0.1)]"><td className="px-5 py-4"><Link href={`/recovery-cases/${item.id}`} onClick={(e) => e.stopPropagation()} className="focus-ring rounded-md font-mono text-xs font-semibold group-hover:text-emerald-500">{shortId(item.id, 10)}</Link><p className="mt-1 font-mono text-[10px] text-muted-foreground">{shortId(item.correlation_id, 10)}</p></td><td className="px-3 py-4"><SourceBadge source={item.source} /></td><td className="px-3 py-4"><p className="text-xs font-medium">{titleCase(item.failure_type)}</p><p className="mt-1 text-[10px] text-muted-foreground">{titleCase(item.payment_method)}</p></td><td className="px-3 py-4 text-sm font-semibold group-hover:text-emerald-500 transition-colors">{formatMoney(item.amount_minor, item.currency)}</td><td className="px-3 py-4"><StatusBadge status={item.status} /></td><td className="px-3 py-4"><p className="text-xs font-medium">{item.decision_kind ? titleCase(item.decision_kind) : "Not recorded"}</p><p className="mt-1 text-[10px] text-muted-foreground">{item.decision_reason ? titleCase(item.decision_reason) : "Provider evidence"}</p></td><td className="px-3 py-4 text-[11px] leading-5 text-muted-foreground">{formatDate(item.created_at)}</td><td className="px-3 py-4 text-[11px] leading-5 text-muted-foreground flex items-center justify-between">{formatDate(item.last_activity_at)} <Eye className="size-3.5 text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity" /></td></tr>)}</tbody>
              </table>
            </div>
            </>
          )}
        </div>
      )}
    </>
  );
}

function SourceBadge({ source }: { source: string }) {
  if (source === "DEMO_SYNTHETIC") return <span className="inline-flex rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-cyan-700 uppercase dark:text-cyan-300">Demo · Synthetic</span>;
  if (source === "RAZORPAY_TEST_MODE") return <span className="inline-flex rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-emerald-700 uppercase dark:text-emerald-300">Razorpay · Test</span>;
  return <span className="inline-flex rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[9px] font-bold tracking-wider text-amber-700 uppercase dark:text-amber-300">Local · Unverified</span>;
}

function Datum({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return <div><dt className="text-[9px] font-bold tracking-wider text-muted-foreground uppercase">{label}</dt><dd className={`mt-1 text-[11px] ${strong ? "text-sm font-semibold" : "text-muted-foreground"}`}>{value}</dd></div>;
}
