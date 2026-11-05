"use client";

import { useEffect, useState } from "react";

type Health = { status: string; version: string };

export default function PrototypePage() {
  const [line, setLine] = useState("Checking status…");

  useEffect(() => {
    fetch("/api/health", { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<Health>) : Promise.reject(new Error(String(r.status)))))
      .then((h) => setLine(`API status: ${h.status} · version ${h.version.slice(0, 7)}`))
      .catch(() => setLine("API status: unreachable"));
  }, []);

  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">Pragati 2.0 prototype</h1>
      <p className="mt-2 inline-block rounded border px-2 py-0.5 text-sm">Prototype, demo data</p>
      <p className="mt-6 text-sm" role="status">{line}</p>
    </main>
  );
}
