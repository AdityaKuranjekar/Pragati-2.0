"use client";
import { useCallback, useEffect, useState } from "react";
import { ProtoError } from "./client";

export type Resource<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: ProtoError };

/** Loads once per key and again on reload(). The data shown is always the last API response. */
export function useResource<T>(load: () => Promise<T>, key: string): Resource<T> & { reload: () => void } {
  const [state, setState] = useState<Resource<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    load().then(
      (data) => live && setState({ status: "ready", data }),
      (e) => live && setState({ status: "error", error: e instanceof ProtoError ? e : new ProtoError("unavailable", "Unexpected error.") }),
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}
