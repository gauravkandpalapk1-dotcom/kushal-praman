"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

interface ApiState<T> {
  key: string | null;
  data: T | null;
  error: unknown;
}

/**
 * GET `path` (skipped when null). Keeps the previous data while reloading so polling views don't flash.
 * `loading` is true until the response for the current path/reload has arrived.
 */
export function useApi<T>(path: string | null) {
  const [tick, setTick] = useState(0);
  const key = path ? `${path}#${tick}` : null;
  const [state, setState] = useState<ApiState<T>>({ key: null, data: null, error: null });

  useEffect(() => {
    if (!key || !path) return;
    let alive = true;
    api
      .get<T>(path)
      .then((data) => alive && setState({ key, data, error: null }))
      .catch((error) => alive && setState((s) => ({ key, data: s.data, error })));
    return () => {
      alive = false;
    };
  }, [key, path]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((data: T) => setState((s) => ({ ...s, data })), []);
  return { data: state.data, error: state.error, loading: key !== null && state.key !== key, reload, setData };
}

/** Calls fn every `ms` while `active`. */
export function useInterval(fn: () => void, ms: number, active: boolean) {
  const ref = useRef(fn);
  useEffect(() => {
    ref.current = fn;
  }, [fn]);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => ref.current(), ms);
    return () => clearInterval(id);
  }, [ms, active]);
}
