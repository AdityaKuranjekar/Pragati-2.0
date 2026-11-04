"use client";

import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Number that counts up once on mount (instant with reduced motion). */
export function CountUp({ value, suffix = "", decimals = 0, className }: { value: number; suffix?: string; decimals?: number; className?: string }) {
  const [v, setV] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    if (reduced()) {
      setV(value);
      return;
    }
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / 800);
      setV(value * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value]);
  return (
    <span className={cn("tabular-nums", className)} data-value={value}>
      {v.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/** Circular progress. `value` 0..1. */
export function Ring({ value, size = 72, stroke = 9, color = "#3b5bdb", children }: { value: number; size?: number; stroke?: number; color?: string; children?: ReactNode }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const [k, setK] = useState(0);
  useEffect(() => {
    if (reduced()) return setK(value);
    const id = requestAnimationFrame(() => setK(value));
    return () => cancelAnimationFrame(id);
  }, [value]);
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e8e3db" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - Math.max(0, Math.min(1, k)))} style={{ transition: "stroke-dashoffset .9s ease-out" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}

const TILE = {
  brand: "bg-brand-soft text-brand",
  teal: "bg-teal-soft text-teal-ink",
  amber: "bg-amber-soft text-amber-ink",
  calm: "bg-calm-soft text-calm-ink",
  sky: "bg-sky-soft text-sky",
} as const;
export function IconTile({ icon: Icon, tone = "brand", size = 40 }: { icon: LucideIcon; tone?: keyof typeof TILE; size?: number }) {
  return (
    <span className={cn("grid shrink-0 place-items-center rounded-xl", TILE[tone])} style={{ width: size, height: size }}>
      <Icon size={size * 0.5} aria-hidden />
    </span>
  );
}

/** Friendly empty state with a small drawn illustration. */
export function EmptyState({ title, children, tone = "brand" }: { title: string; children?: ReactNode; tone?: "brand" | "teal" | "amber" | "calm" }) {
  const c = { brand: "#3b5bdb", teal: "#0ca678", amber: "#f08c00", calm: "#7048e8" }[tone];
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-line bg-white/60 px-4 py-8 text-center animate-pop" data-testid="empty-state">
      <svg width="88" height="64" viewBox="0 0 88 64" aria-hidden>
        <rect x="8" y="14" width="72" height="42" rx="10" fill={c} opacity=".12" />
        <rect x="18" y="24" width="30" height="6" rx="3" fill={c} opacity=".55" />
        <rect x="18" y="36" width="50" height="6" rx="3" fill={c} opacity=".3" />
        <circle cx="66" cy="16" r="10" fill={c} opacity=".9" />
        <path d="M61 16l4 4 6-8" stroke="#fff" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <p className="font-semibold text-ink">{title}</p>
      {children && <div className="max-w-md text-sm text-ink-soft">{children}</div>}
    </div>
  );
}

/** Pragati logo mark: a rising bar chart inside a rounded tile. */
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" aria-hidden>
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5c7cfa" />
          <stop offset="1" stopColor="#3b5bdb" />
        </linearGradient>
      </defs>
      <rect width="36" height="36" rx="10" fill="url(#lg)" />
      <rect x="8" y="20" width="5" height="8" rx="2" fill="#fff" opacity=".7" />
      <rect x="15.5" y="14" width="5" height="14" rx="2" fill="#fff" opacity=".85" />
      <rect x="23" y="8" width="5" height="20" rx="2" fill="#fff" />
      <circle cx="25.5" cy="6" r="2.2" fill="#ffd43b" />
    </svg>
  );
}
