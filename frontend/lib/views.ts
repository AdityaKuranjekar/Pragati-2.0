"use client";

import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { apiFetch } from "./http";
import { useQuery } from "./query";
import { useApi, useApp } from "./app-context";
import { MasterySchema, ParentSchema, RiskSchema, StudentSchema } from "./types";

const Batch = z
  .object({ id: z.string(), name: z.string(), exam: z.string(), class_level: z.string().optional(), mentor_capacity_per_week: z.number().optional(), students: z.number().optional(), active_students: z.number().optional() })
  .passthrough();
export type Batch = z.infer<typeof Batch>;
const BatchesRes = z.object({ batches: z.array(Batch) }).passthrough();

const RosterRow = z.object({ student_id: z.string(), roll_no: z.string(), name: z.string(), status: z.string().optional(), dob: z.string().nullable().optional() }).passthrough();
const BatchStudents = z.object({ students: z.array(RosterRow) }).passthrough();

export type Person = { id: string; roll: string; name: string; batchId: string; batchName: string; minor: boolean | null; status: string };

export function useBatches() {
  return useApi("/batches", (x) => BatchesRes.parse(x).batches);
}

/** Pick the remembered batch if it still exists, else the first one. */
export function useBatchChoice() {
  const { sel, setBatch } = useApp();
  const q = useBatches();
  const batches = q.data ?? [];
  const current = batches.find((b) => b.id === sel.batchId) ?? batches[0] ?? null;
  return { ...q, batches, batch: current, setBatch };
}

/** One fetch per batch; the people list is the union, always alphabetical (never by performance). */
export function useRoster() {
  const { institute, ready } = useApp();
  const b = useBatches();
  const [state, setState] = useState<{ key: string; people: Person[]; loading: boolean; error: string | null }>({ key: "", people: [], loading: true, error: null });
  const ids = (b.data ?? []).map((x) => x.id).join(",");
  const key = `${institute}|${ids}`;
  useEffect(() => {
    if (!ready || !b.data) return;
    let alive = true;
    Promise.all(
      b.data.map((bt) =>
        apiFetch<unknown>(`/batches/${bt.id}/students`).then((r) =>
          BatchStudents.parse(r).students.map<Person>((s) => ({
            id: s.student_id,
            roll: s.roll_no,
            name: s.name,
            batchId: bt.id,
            batchName: bt.name,
            minor: s.dob ? (Date.UTC(2026, 9, 25) - +new Date(s.dob)) / 31557600000 < 18 : null,
            status: s.status ?? "active",
          }))
        )
      )
    )
      .then((rows) => alive && setState({ key, people: rows.flat().sort((x, y) => x.name.localeCompare(y.name) || x.roll.localeCompare(y.roll)), loading: false, error: null }))
      .catch((e: Error) => alive && setState({ key, people: [], loading: false, error: e.message }));
    return () => {
      alive = false;
    };
  }, [key, ready, b.data]);
  const fresh = state.key === key;
  const people = useMemo(() => (fresh ? state.people : []), [fresh, state.people]);
  const byId = useMemo(() => new Map(people.map((p) => [p.id, p])), [people]);
  return { people, byId, loading: b.loading || (!fresh && !b.error) , error: b.error ?? (fresh ? state.error : null), status: b.status, reload: b.reload };
}

export function useHeatmap(batchId: string | null) {
  return useApi(batchId ? `/batches/${batchId}/heatmap` : null, (x) => MasterySchema.parse(x));
}
export function useSupportList(batchId: string | null) {
  return useApi(batchId ? `/batches/${batchId}/support-list` : null, (x) => RiskSchema.parse(x));
}
export function useProfile(studentId: string | null) {
  return useApi(studentId ? `/students/${studentId}/profile` : null, (x) => StudentSchema.parse(x));
}
export function useParentView(studentId: string | null) {
  return useApi(studentId ? `/students/${studentId}/parent-view` : null, (x) => ParentSchema.parse(x));
}

/** How many students are on this week's support lists, summed over all batches. */
export function useWeeklyActions() {
  const { institute, ready } = useApp();
  const b = useBatches();
  const ids = (b.data ?? []).map((x) => x.id);
  return useQuery<number>(ready && b.data ? `${institute}|weekly|${ids.join(",")}` : null, async () => {
    const lists = await Promise.all(ids.map((id) => apiFetch<unknown>(`/batches/${id}/support-list`).then((r) => RiskSchema.parse(r).list.length)));
    return lists.reduce((x, y) => x + y, 0);
  });
}
