"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { fetchFile } from "./api";
import { apiFetch, loadSession, saveSession, setReauth } from "./http";
import { useQuery, clearQueryCache, type Query } from "./query";
import type { FileKey, FileType } from "./types";

export type Lang = "en" | "hi";
type Selection = { batchId: string; studentId: string };

type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** set language without remembering it (used for per-page defaults, e.g. parent pages open in Hindi) */
  softLang: (l: Lang) => void;
  langTouched: boolean;
  institute: string;
  setInstitute: (i: string) => void;
  /** a demo token for the current institute is in place; queries wait for this */
  ready: boolean;
  /** last chosen batch and student for this institute */
  sel: Selection;
  setBatch: (id: string) => void;
  setStudent: (id: string) => void;
  /** pick the English or Hindi variant */
  L: (en: string, hi: string) => string;
};
const AppCtx = createContext<Ctx | null>(null);

type LoginRes = { access_token: string; me?: { name?: string; role?: string; institute_slug?: string }; user?: { name?: string; role?: string; institute_id?: string } };

export function AppProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [langTouched, setTouched] = useState(false);
  const [institute, setInstituteState] = useState("patna_jee");
  const [hydrated, setHydrated] = useState(false);
  const [ready, setReady] = useState(false);
  const [sel, setSel] = useState<Selection>({ batchId: "", studentId: "" });
  const instRef = useRef(institute);
  instRef.current = institute;

  // restore remembered choices once, on the client
  useEffect(() => {
    try {
      const l = localStorage.getItem("pragati.lang");
      if (l === "en" || l === "hi") {
        setLangState(l);
        setTouched(true);
      }
      const i = localStorage.getItem("pragati.institute");
      if (i) setInstituteState(i);
    } catch {}
    setHydrated(true);
  }, []);

  // selection is remembered per institute and reset when the institute changes
  useEffect(() => {
    if (!hydrated) return;
    try {
      const raw = localStorage.getItem(`pragati.sel.${institute}`);
      setSel(raw ? (JSON.parse(raw) as Selection) : { batchId: "", studentId: "" });
    } catch {
      setSel({ batchId: "", studentId: "" });
    }
  }, [institute, hydrated]);
  const saveSel = useCallback((s: Selection) => {
    setSel(s);
    try {
      localStorage.setItem(`pragati.sel.${instRef.current}`, JSON.stringify(s));
    } catch {}
  }, []);
  const setBatch = useCallback((batchId: string) => saveSel({ ...sel, batchId }), [sel, saveSel]);
  const setStudent = useCallback((studentId: string) => saveSel({ ...sel, studentId }), [sel, saveSel]);

  // Silent demo sign-in: always the owner (full staff access) for the current institute.
  const signIn = useCallback(async (inst: string) => {
    const r = await apiFetch<LoginRes>("/auth/login", { method: "POST", json: { role: "owner", institute_id: inst }, auth: false });
    saveSession({ token: r.access_token, institute: inst, role: "owner", name: r.me?.name ?? r.user?.name ?? "Owner (demo)" });
  }, []);
  useEffect(() => {
    if (!hydrated) return;
    let alive = true;
    setReady(false);
    const s = loadSession();
    (s && s.institute === institute ? Promise.resolve() : signIn(institute))
      .catch(() => {})
      .finally(() => alive && setReady(true));
    return () => {
      alive = false;
    };
  }, [institute, hydrated, signIn]);
  // a 401 later (server restarted, token expired): get a new token and carry on, no redirect
  useEffect(() => {
    setReauth(() => signIn(instRef.current));
    return () => setReauth(null);
  }, [signIn]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    setTouched(true);
    try {
      localStorage.setItem("pragati.lang", l);
    } catch {}
  }, []);
  const setInstitute = useCallback((i: string) => {
    if (i === instRef.current) return;
    clearQueryCache();
    setInstituteState(i);
    try {
      localStorage.setItem("pragati.institute", i);
    } catch {}
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const softLang = useCallback((l: Lang) => setLangState(l), []);
  const value = useMemo<Ctx>(
    () => ({ lang, setLang, softLang, langTouched, institute, setInstitute, ready: ready && hydrated, sel, setBatch, setStudent, L: (en, hi) => (lang === "hi" ? hi : en) }),
    [lang, setLang, softLang, langTouched, institute, setInstitute, ready, hydrated, sel, setBatch, setStudent]
  );
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const c = useContext(AppCtx);
  if (!c) throw new Error("AppProvider missing");
  return c;
}

/** Fetch with the current institute; waits until the demo token is in place. key=null disables. */
export function useApi<T>(path: string | null, parse: (x: unknown) => T): Query<T> {
  const { institute, ready } = useApp();
  return useQuery<T>(ready && path ? `${institute}|${path}` : null, async () => parse(await apiFetch<unknown>(path as string)));
}

/** Load + zod-validate one artifact-shaped file (evidence pages, owner dashboard, data card, ...). */
export function useData<K extends FileKey>(file: K): Query<FileType<K>> {
  const { institute, ready } = useApp();
  return useQuery<FileType<K>>(ready ? `${institute}|file|${file}` : null, () => fetchFile(file, institute));
}
