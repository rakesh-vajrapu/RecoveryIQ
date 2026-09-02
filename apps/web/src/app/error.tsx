"use client";

import { RefreshCw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <div className="surface-panel mx-auto max-w-2xl rounded-3xl p-8 text-center sm:p-12"><span className="mx-auto grid size-14 place-items-center rounded-2xl bg-destructive/10 text-destructive"><TriangleAlert className="size-6" /></span><h1 className="mt-5 text-2xl font-bold">This page could not be displayed.</h1><p className="mt-3 text-sm leading-6 text-muted-foreground">RecoveryIQ kept the failure contained. No recovery decision or payment operation was attempted.</p><Button onClick={reset} className="mt-6"><RefreshCw />Try this page again</Button></div>;
}

