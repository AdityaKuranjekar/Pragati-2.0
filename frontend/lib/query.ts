"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./http";

type Snap<T> = { key: string | null; data: T | null; error: string | null; status: number | null; loading: boolean };
const cache = new Map<string, unknown>();

export type Query<T> = {
  data: T | null;
  error: string | null;
  status: number | null;
  /** true only while there is nothing to show yet */
  loading: boolean;
  /** true while re-reading with old data on screen */
  refreshing: boolean;
  reload: () => void;
  mutate: (d: T) => void;
};

/**
 * Small stale-while-revalidate hook. The state is always derived for the CURRENT key, so a page can
 * never show the previous selection's data (or an endless blank) after the key changes.
 * key = null means "not ready, do not fetch".
 */
export function useQuery<T>(key: string | null, fetcher: () => Promise<T>): Query<T> {
  const [snap, setSnap] = useState<Snap<T>>({ key: null, data: null, error: null, status: null, loading: false });
  const [tick, setTick] = useState(0);
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;

  useEffect(() => {
    if (!key) return;
    let alive = true;
    const cached = cache.get(key) as T | undefined;
    setSnap({ key, data: cached ?? null, error: null, status: cached ? 200 : null, loading: true });
    fetchRef
      .current()
      .then((d) => {
        cache.set(key, d);
        if (alive) setSnap({ key, data: d, error: null, status: 200, loading: false });
      })
      .catch((e: Error) => {
        if (!alive) return;
        const status = e instanceof ApiError ? e.status : 0;
        setSnap((s) => ({ key, data: s.key === key ? s.data : null, error: e.message, status, loading: false }));
      });
    return () => {
      alive = false;
    };
  }, [key, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const mutate = useCallback(
    (d: T) => {
      if (key) cache.set(key, d);
      setSnap({ key, data: d, error: null, status: 200, loading: false });
    },
    [key]
  );

  // derive for the current key
  if (!key) return { data: null, error: null, status: null, loading: true, refreshing: false, reload, mutate };
  const fresh = snap.key === key;
  const cached = (cache.get(key) as T | undefined) ?? null;
  const data = fresh ? snap.data : cached;
  const busy = fresh ? snap.loading : true;
  return {
    data,
    error: fresh && !data ? snap.error : null,
    status: fresh && !data ? snap.status : data ? 200 : null,
    loading: busy && data === null && !(fresh && snap.error),
    refreshing: busy && data !== null,
    reload,
    mutate,
  };
}

export function clearQueryCache() {
  cache.clear();
}
