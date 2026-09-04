"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Database, RefreshCw, Server, TriangleAlert, Wifi } from "lucide-react";

import { Button } from "@/components/ui/button";

type HealthResponse = {
  service: string;
  status: "healthy";
  environment: string;
  database: "sqlite" | "postgresql" | "other";
  celery_eager: boolean;
};

type ConnectionState =
  | { kind: "checking" }
  | { kind: "connected"; health: HealthResponse }
  | { kind: "unavailable"; message: string };

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`API returned HTTP ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown connection error";
}

export function ApiStatus() {
  const [state, setState] = useState<ConnectionState>({ kind: "checking" });

  useEffect(() => {
    const controller = new AbortController();
    void fetchHealth(controller.signal).then(
      (health) => setState({ kind: "connected", health }),
      (error: unknown) => {
        if (!isAbortError(error)) {
          setState({ kind: "unavailable", message: errorMessage(error) });
        }
      },
    );
    return () => controller.abort();
  }, []);

  const retry = () => {
    setState({ kind: "checking" });
    void fetchHealth().then(
      (health) => setState({ kind: "connected", health }),
      (error: unknown) => {
        setState({ kind: "unavailable", message: errorMessage(error) });
      },
    );
  };

  return (
    <article className="overflow-hidden rounded-xl border bg-card shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b p-5 sm:p-6">
        <div>
          <p className="text-xs font-semibold tracking-[0.12em] text-muted-foreground uppercase">
            API connectivity
          </p>
          <h3 className="mt-2 text-lg font-medium text-foreground">Backend control plane</h3>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">{apiBaseUrl}/health</p>
        </div>
        <Server className="size-5 text-muted-foreground" />
      </div>

      <div className="p-5 sm:p-6">
        {state.kind === "checking" && (
          <div className="flex min-h-28 items-center gap-3 text-sm text-slate-400">
            <RefreshCw className="size-4 animate-spin text-cyan-300" />
            Checking backend health…
          </div>
        )}

        {state.kind === "connected" && (
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-emerald-300">
              <CheckCircle2 className="size-4" />
              Connected and healthy
            </div>
            <dl className="mt-6 grid gap-3 sm:grid-cols-2">
              <StatusDatum icon={Wifi} label="Environment" value={state.health.environment} />
              <StatusDatum icon={Database} label="Database" value={state.health.database} />
              <StatusDatum
                icon={RefreshCw}
                label="Celery"
                value={state.health.celery_eager ? "eager mode" : "broker mode"}
              />
              <StatusDatum
                icon={Server}
                label="Explanation"
                value="non-authoritative"
              />
            </dl>
          </div>
        )}

        {state.kind === "unavailable" && (
          <div className="flex min-h-28 items-center justify-between gap-5">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-amber-300">
                <TriangleAlert className="size-4" />
                Backend unavailable
              </div>
              <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
                Start the FastAPI service locally, then retry. No financial data is inferred while
                the API is offline.
              </p>
              <p className="mt-2 font-mono text-[10px] text-muted-foreground">{state.message}</p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={retry}
              className="border-border bg-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground"
            >
              <RefreshCw className="mr-2 h-3 w-3" />
              Retry
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}

function StatusDatum({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Server;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="flex items-center gap-2 text-[10px] tracking-wide text-muted-foreground uppercase">
        <Icon className="size-3.5" />
        {label}
      </div>
      <p className="mt-2 font-mono text-xs text-foreground">{value}</p>
    </div>
  );
}
