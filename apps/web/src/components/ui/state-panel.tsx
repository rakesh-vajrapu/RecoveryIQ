import { Inbox, RefreshCw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LoadingPanel({ label = "Loading live recovery data" }: { label?: string }) {
  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label={label} aria-busy="true">{Array.from({ length: 4 }, (_, index) => <div key={index} className="surface-panel rounded-2xl p-5"><div className="shimmer h-3 w-24 rounded-full" /><div className="shimmer mt-7 h-8 w-32 rounded-lg" /><div className="shimmer mt-4 h-3 w-full rounded-full" /></div>)}</div>;
}
export function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="surface-panel rounded-2xl p-8 text-center sm:p-12" role="alert"><span className="mx-auto grid size-12 place-items-center rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-300"><TriangleAlert className="size-5" /></span><h2 className="mt-4 text-lg font-semibold">We could not load this view</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">{message}</p><Button onClick={onRetry} variant="outline" size="lg" className="mt-5"><RefreshCw className="size-4" />Try again</Button></div>;
}
export function EmptyPanel({ title, description }: { title: string; description: string }) {
  return <div className="rounded-2xl border border-dashed bg-card/45 p-8 text-center sm:p-12"><span className="mx-auto grid size-12 place-items-center rounded-2xl bg-muted text-muted-foreground"><Inbox className="size-5" /></span><h2 className="mt-4 text-base font-semibold">{title}</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">{description}</p></div>;
}

