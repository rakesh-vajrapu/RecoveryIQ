"use client";

import { ArrowUpDown, Eye, ListChecks, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/state-panel";
import { useApiResource } from "@/hooks/use-api-resource";
import { getRecoveryCases } from "@/lib/api";
import { formatDate, formatMoney, shortId } from "@/lib/format";

type SortMode = "newest" | "oldest" | "amount-high" | "amount-low";

export default function RecoveryCasesPage() {
  const load = useCallback((signal: AbortSignal) => getRecoveryCases(signal), []);
  const resource = useApiResource(load);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [sort, setSort] = useState<SortMode>("newest");

  const statuses = useMemo(() => Array.from(new Set(resource.data?.map((item) => item.status) ?? [])).sort(), [resource.data]);
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return [...(resource.data ?? [])].filter((item) => {
      const matchesQuery = !normalized || item.id.toLowerCase().includes(normalized) || item.correlation_id.toLowerCase().includes(normalized) || item.currency.toLowerCase().includes(normalized);
      return matchesQuery && (status === "ALL" || item.status === status);
    }).sort((left, right) => {
      if (sort === "oldest") return new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
      if (sort === "amount-high") return right.amount_minor - left.amount_minor;
      if (sort === "amount-low") return left.amount_minor - right.amount_minor;
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    });
  }, [query, resource.data, sort, status]);

  return (
    <>
      <PageHeader eyebrow="Recovery operations" title="Every opportunity, one auditable queue." description="Search, filter, and inspect persisted recovery cases. References are anonymous correlation IDs; customer identity is intentionally not exposed by this API." icon={ListChecks} actions={<Button variant="outline" onClick={resource.retry} disabled={resource.loading}><RefreshCw className={resource.loading ? "animate-spin" : ""} />Refresh</Button>} />
      {resource.loading && <LoadingPanel label="Loading recovery cases" />}
      {resource.error && <ErrorPanel message={resource.error} onRetry={resource.retry} />}
      {resource.data && (
        <div className="surface-panel overflow-hidden rounded-2xl">
          <div className="grid gap-3 border-b p-4 sm:p-5 lg:grid-cols-[minmax(260px,1fr)_190px_190px_auto]">
            <label className="relative block"><span className="sr-only">Search recovery cases</span><Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search case or reference…" className="focus-ring h-11 w-full rounded-xl border bg-card pl-10 pr-4 text-sm shadow-sm placeholder:text-muted-foreground/70" /></label>
            <label><span className="sr-only">Filter by status</span><select value={status} onChange={(event) => setStatus(event.target.value)} className="focus-ring h-11 w-full rounded-xl border bg-card px-3 text-sm shadow-sm"><option value="ALL">All statuses</option>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label><span className="sr-only">Sort recovery cases</span><select value={sort} onChange={(event) => setSort(event.target.value as SortMode)} className="focus-ring h-11 w-full rounded-xl border bg-card px-3 text-sm shadow-sm"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="amount-high">Amount: high to low</option><option value="amount-low">Amount: low to high</option></select></label>
            <div className="flex items-center justify-end gap-2 rounded-xl border bg-[var(--surface-soft)] px-3 text-xs text-muted-foreground"><ArrowUpDown className="size-3.5" /><span>{filtered.length} of {resource.data.length}</span></div>
          </div>

          {filtered.length === 0 ? <div className="p-5"><EmptyPanel title={resource.data.length ? "No cases match these filters" : "No recovery cases yet"} description={resource.data.length ? "Try a different reference, status, or sort option." : "Cases will appear here when the backend records a recoverable payment failure."} /></div> : (
            <>
            <div className="divide-y md:hidden">
              {filtered.map((item) => <article key={item.id} className="p-4 transition-colors hover:bg-muted/30"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><Link href={`/recovery-cases/${item.id}`} className="focus-ring block truncate rounded-md font-mono text-xs font-semibold hover:text-primary">Case {shortId(item.id, 12)}</Link><p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">Ref {shortId(item.correlation_id, 14)}</p></div><StatusBadge status={item.status} /></div><dl className="mt-4 grid grid-cols-2 gap-3 rounded-xl border bg-[var(--surface-soft)] p-3"><div><dt className="text-[9px] font-bold tracking-wider text-muted-foreground uppercase">Amount</dt><dd className="mt-1 text-sm font-semibold">{formatMoney(item.amount_minor, item.currency)}</dd></div><div><dt className="text-[9px] font-bold tracking-wider text-muted-foreground uppercase">Created</dt><dd className="mt-1 text-[11px] text-muted-foreground">{formatDate(item.created_at)}</dd></div><div className="col-span-2"><dt className="text-[9px] font-bold tracking-wider text-muted-foreground uppercase">Last activity</dt><dd className="mt-1 text-[11px] text-muted-foreground">{formatDate(item.last_activity_at)}</dd></div></dl><Button variant="outline" size="sm" className="mt-3 w-full" nativeButton={false} render={<Link href={`/recovery-cases/${item.id}`} />}><Eye className="size-3.5" />Open case</Button></article>)}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[1080px] text-left">
                <thead className="bg-muted/45 text-[10px] font-bold tracking-[0.12em] text-muted-foreground uppercase"><tr><th className="px-5 py-3.5 sm:px-6">Case</th><th className="px-4 py-3.5">Reference</th><th className="px-4 py-3.5">Failure type</th><th className="px-4 py-3.5">Amount</th><th className="px-4 py-3.5">Status</th><th className="px-4 py-3.5">Created</th><th className="px-4 py-3.5">Last activity</th><th className="px-5 py-3.5 text-right sm:px-6">Action</th></tr></thead>
                <tbody className="divide-y">{filtered.map((item) => <tr key={item.id} className="group transition-colors hover:bg-muted/35"><td className="px-5 py-4 sm:px-6"><Link href={`/recovery-cases/${item.id}`} className="focus-ring rounded-md font-mono text-xs font-semibold hover:text-primary">{shortId(item.id, 12)}</Link></td><td className="px-4 py-4"><p className="font-mono text-[11px] text-muted-foreground">{shortId(item.correlation_id, 14)}</p></td><td className="px-4 py-4"><p className="text-xs font-medium">Recurring payment</p><p className="mt-1 text-[10px] text-muted-foreground">Failure detail in case evidence</p></td><td className="px-4 py-4 text-sm font-semibold">{formatMoney(item.amount_minor, item.currency)}</td><td className="px-4 py-4"><StatusBadge status={item.status} /></td><td className="px-4 py-4 text-xs text-muted-foreground">{formatDate(item.created_at)}</td><td className="px-4 py-4 text-xs text-muted-foreground">{formatDate(item.last_activity_at)}</td><td className="px-5 py-4 text-right sm:px-6"><Button variant="ghost" size="sm" nativeButton={false} render={<Link href={`/recovery-cases/${item.id}`} />}><Eye className="size-3.5" />Open case</Button></td></tr>)}</tbody>
              </table>
            </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
