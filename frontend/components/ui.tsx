"use client";

import { Info } from "lucide-react";
import { createContext, useContext, type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from "react";
import { useApp } from "@/lib/app-context";
import { cn } from "@/lib/utils";

export function Card({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-2xl border border-line bg-card p-5 shadow-soft", className)} {...p} />;
}

export function CardTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
      <h3 className="text-[15px] font-semibold text-ink">{children}</h3>
      {right}
    </div>
  );
}

export function Button({
  className,
  variant = "primary",
  ...p
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "soft" }) {
  return (
    <button
      className={cn(
        "inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-xl px-4 py-2 text-[15px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-50",
        variant === "primary" && "bg-brand text-white hover:bg-brand-dark",
        variant === "soft" && "bg-brand-soft text-brand-dark hover:bg-[#dbe4ff]",
        variant === "ghost" && "text-ink-soft hover:bg-brand-soft",
        className
      )}
      {...p}
    />
  );
}

const TONES = {
  neutral: "bg-[#eef1f6] text-ink-soft",
  brand: "bg-brand-soft text-brand-dark",
  teal: "bg-teal-soft text-[#087f5b]",
  amber: "bg-amber-soft text-[#8a5200]",
  calm: "bg-calm-soft text-[#5f3dc4]",
} as const;
export function Badge({ tone = "neutral", className, ...p }: HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof TONES }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", TONES[tone], className)}
      {...p}
    />
  );
}

const ORIGIN_TONE: Record<string, keyof typeof TONES> = {
  synthetic: "calm",
  public: "teal",
  model: "brand",
  assumption: "amber",
  real_photo: "teal",
};
/** Origin chip: synthetic / public / model / assumption. */
export const EvidenceContext = createContext(false);
export function Origin({ origin, className }: { origin?: string; className?: string }) {
  const evidence = useContext(EvidenceContext);
  if (!origin || !evidence) return null;
  return (
    <Badge tone={ORIGIN_TONE[origin] ?? "neutral"} className={className} data-testid="origin-chip">
      {origin.replace("_", " ")}
    </Badge>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-[#e9edf4] motion-reduce:animate-none", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Skeleton className="h-10 w-1/3" />
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

export function Unavailable({ what, detail, status, onRetry }: { what: string; detail?: string | null; status?: number | null; onRetry?: () => void }) {
  const { L } = useApp();
  const [title, body] =
    status === 403
      ? [L("Not available for your role", "आपकी भूमिका के लिए उपलब्ध नहीं"), L("Sign in with a role that can see this screen.", "ऐसी भूमिका से साइन इन करें जो यह स्क्रीन देख सके।")]
      : status === 0
      ? [L("Cannot reach the server", "सर्वर तक नहीं पहुँच सके"), L("Check that the app server is running, then try again.", "देखें कि ऐप सर्वर चल रहा है, फिर दोबारा कोशिश करें।")]
      : status === 404
      ? [L(`Nothing here yet: ${what}`, `यहाँ अभी कुछ नहीं: ${what}`), L("No data has been loaded for this view.", "इस दृश्य के लिए अभी कोई डेटा नहीं जोड़ा गया।")]
      : [L(`Data not available: ${what}`, `डेटा उपलब्ध नहीं: ${what}`), L("We could not load this view.", "हम यह दृश्य लोड नहीं कर सके।")];
  return (
    <Card className="mx-auto max-w-md text-center" role="alert">
      <Info className="mx-auto mb-2 text-ink-mute" />
      <p className="font-medium text-ink">{title}</p>
      <p className="mt-1 text-sm text-ink-soft">{body}</p>
      {detail && <p className="mt-2 text-xs text-ink-mute">{detail}</p>}
      {onRetry && (
        <Button variant="soft" className="mt-3" onClick={onRetry}>
          {L("Try again", "फिर कोशिश करें")}
        </Button>
      )}
    </Card>
  );
}

/** Calm empty state: text, never a red label. */
export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-xl bg-bg px-3 py-4 text-center text-sm text-ink-soft">{children}</p>;
}

export function Note({ children, tone = "amber" }: { children: ReactNode; tone?: "amber" | "brand" | "calm" }) {
  const c = tone === "amber" ? "bg-amber-soft text-[#8a5200]" : tone === "brand" ? "bg-brand-soft text-brand-dark" : "bg-calm-soft text-[#5f3dc4]";
  return (
    <div className={cn("flex gap-2 rounded-xl px-3 py-2 text-sm leading-snug", c)}>
      <Info size={15} className="mt-0.5 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

/** Lead line under the top-bar title. `title` (optional) is a subheading, not a second page title. */
export function PageHead({ title, sub, right }: { title?: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {title && <h2 className="text-xl font-semibold tracking-tight text-ink">{title}</h2>}
        {sub && <p className="mt-1 max-w-2xl text-[15px] text-ink-soft">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Select({
  value,
  onChange,
  options,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  label: string;
}) {
  return (
    <label className="inline-flex max-w-full items-center gap-2 text-sm text-ink-soft">
      <span className="sr-only sm:not-sr-only">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[44px] min-w-0 max-w-full rounded-xl border border-line bg-white px-3 py-2 text-sm text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Stat({ label, value, sub, origin }: { label: string; value: ReactNode; sub?: ReactNode; origin?: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-ink-mute">{label}</p>
        <Origin origin={origin} />
      </div>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-ink">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-ink-soft">{sub}</p>}
    </Card>
  );
}
