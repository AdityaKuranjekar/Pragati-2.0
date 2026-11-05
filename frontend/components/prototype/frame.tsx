"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { originText } from "@/lib/prototype/origin";
import type { Origin } from "@/lib/prototype/types";

const TABS = [
  { href: "/prototype/teacher", label: "Teacher", match: "/prototype/teacher" },
  { href: "/prototype/learner/a", label: "Learner", match: "/prototype/learner" },
  { href: "/prototype/evaluation", label: "Evaluation", match: "/prototype/evaluation" },
];

export function TopBar() {
  const path = usePathname() ?? "";
  return (
    <header className="p-topbar">
      <div className="p-topbar-in">
        <Link href="/prototype/teacher" className="p-brand">Pragati 2.0 prototype</Link>
        <nav className="p-nav" aria-label="Prototype">
          {TABS.map((t) => (
            <Link key={t.href} href={t.href} aria-current={path.startsWith(t.match) ? "page" : undefined}>{t.label}</Link>
          ))}
        </nav>
        <span className="p-label">Prototype, demo data</span>
      </div>
    </header>
  );
}

export function StatusLine() {
  const [line, setLine] = useState("API status: checking");
  useEffect(() => {
    let live = true;
    fetch("/api/health", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((h: { status: string; version: string }) => live && setLine(`API status: ${h.status}, version ${String(h.version).slice(0, 7)}`))
      .catch(() => live && setLine("API status: not reachable"));
    return () => {
      live = false;
    };
  }, []);
  return <p role="status">{line}</p>;
}

export function OriginTag({ origin }: { origin: Origin }) {
  return <span className="p-origin">{originText(origin)}</span>;
}

export function PageHead({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="p-head">
      <h1 className="p-h1">{title}</h1>
      {sub ? <p className="p-sub">{sub}</p> : null}
    </div>
  );
}

export function Card({ title, origin, children, right }: { title?: string; origin?: Origin | Origin[]; children: ReactNode; right?: ReactNode }) {
  const origins = origin ? (Array.isArray(origin) ? origin : [origin]) : [];
  return (
    <section className="p-card">
      {title || origins.length ? (
        <div className="p-card-head">
          {title ? <h2 className="p-h2">{title}</h2> : <span />}
          <span style={{ display: "inline-flex", gap: 12 }}>
            {right}
            {origins.map((o) => <OriginTag key={o} origin={o} />)}
          </span>
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Warn({ children }: { children: ReactNode }) {
  return (
    <span className="p-warn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        <path d="M12 9v4M12 17h.01" />
      </svg>
      {children}
    </span>
  );
}

import { resetDemo } from "@/lib/prototype/store";
export function ResetDemo() {
  return (
    <p>
      Attempts and decisions live in this browser tab only.{" "}
      <button type="button" className="p-btn link" onClick={resetDemo}>Reset demo state</button>
    </p>
  );
}
