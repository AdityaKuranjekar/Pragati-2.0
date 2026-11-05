"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { OriginTag } from "./common";
import { ORIGIN_MEANING } from "@/lib/prototype/labels";
import type { Origin } from "@/lib/prototype/schemas";

const TABS = [
  { href: "/prototype/teacher", label: "Teacher", match: "/prototype/teacher" },
  { href: "/prototype/learner", label: "Learner", match: "/prototype/learner" },
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
        <span className="label">Prototype, stub sign-in</span>
      </div>
    </header>
  );
}

/** Reads the API's health route through the app's own forwarder, so the host is not in browser code. */
export function ServiceStatus() {
  const [line, setLine] = useState("Service: checking");
  useEffect(() => {
    let live = true;
    fetch("/api/proto/as/teacher/api/prototype/health", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((h: { status: string; policy_version: string }) => live && setLine(`Service: ${h.status} (policy ${h.policy_version})`))
      .catch(() => live && setLine("Service: not reachable"));
    return () => { live = false; };
  }, []);
  return <p role="status">{line}</p>;
}

export function Footer() {
  const origins: Origin[] = ["DEMO FIXTURE", "SIM", "PUB", "EXP"];
  return (
    <>
      <p>Prototype. Every learner here is made up. Mastery, bands and recommendations are computed by the API; this page only displays them.</p>
      <details>
        <summary>What the origin tags mean</summary>
        <ul style={{ display: "grid", gap: 6, marginTop: 8 }}>
          {origins.map((o) => <li key={o}><OriginTag origin={o} /> {ORIGIN_MEANING[o]}</li>)}
        </ul>
      </details>
      <ServiceStatus />
    </>
  );
}
