"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "@/lib/api";

type ResourceState<T> = { data: T | null; error: string | null; loading: boolean };

export function useApiResource<T>(loader: (signal: AbortSignal) => Promise<T>) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ResourceState<T>>({ data: null, error: null, loading: true });
  useEffect(() => {
    const controller = new AbortController();
    void loader(controller.signal).then(
      (data) => setState({ data, error: null, loading: false }),
      (error: unknown) => { if (!controller.signal.aborted) setState({ data: null, error: errorMessage(error), loading: false }); },
    );
    return () => controller.abort();
  }, [attempt, loader]);
  const retry = useCallback(() => {
    setState((current) => ({ ...current, error: null, loading: true }));
    setAttempt((value) => value + 1);
  }, []);
  return { ...state, retry };
}
