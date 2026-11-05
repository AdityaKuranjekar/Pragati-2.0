"use client";
import { useSyncExternalStore } from "react";
import type { Attempt, Decision } from "./types";

// Session-only demo state. Nothing is sent anywhere or stored; a reload resets it.
type State = { attempts: Attempt[]; decisions: Decision[] };
const EMPTY: State = { attempts: [], decisions: [] };
let state: State = EMPTY;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
export const useDemoState = () => useSyncExternalStore(subscribe, () => state, () => EMPTY);

export function recordAttempt(a: Omit<Attempt, "id">) {
  state = { ...state, attempts: [...state.attempts, { ...a, id: `att-${state.attempts.length + 1}` }] };
  emit();
}
export function recordDecision(d: Omit<Decision, "id" | "decidedAt" | "decidedBy">) {
  state = { ...state, decisions: [...state.decisions, { ...d, id: `dec-${state.decisions.length + 1}`, decidedAt: new Date().toISOString(), decidedBy: "Demo teacher" }] };
  emit();
}
export function resetDemo() {
  state = EMPTY;
  emit();
}
