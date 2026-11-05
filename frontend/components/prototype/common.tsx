"use client";
import type { ReactNode } from "react";
import type { ProtoError } from "@/lib/prototype/client";
import { ORIGIN_MEANING, originText } from "@/lib/prototype/labels";
import type { Origin } from "@/lib/prototype/schemas";

/** The literal tag, always visible next to the numbers it covers. */
export function OriginTag({ origin }: { origin: Origin }) {
  return <span className="p-origin" title={ORIGIN_MEANING[origin]}>{originText(origin)}</span>;
}

export function Card({ title, origins, right, children, className = "" }: {
  title?: string; origins?: Origin[]; right?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`p-card ${className}`} aria-label={title}>
      {title || origins?.length ? (
        <div className="p-card-head">
          {title ? <h2 className="p-h2">{title}</h2> : <span />}
          <span style={{ display: "inline-flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {right}
            {origins?.map((o) => <OriginTag key={o} origin={o} />)}
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
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" />
      </svg>
      {children}
    </span>
  );
}

export function Loading({ what }: { what: string }) {
  return (
    <div className="p-state" data-kind="loading" role="status" aria-live="polite">
      <p>Loading {what}…</p>
      <div className="p-skel" style={{ width: "70%" }} /><div className="p-skel" style={{ width: "50%" }} />
    </div>
  );
}

export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="p-state" data-kind="empty">
      <h2>{title}</h2>
      <p className="muted">{children}</p>
    </div>
  );
}

/** Permission-denied and every other error. The message is the API's own wording where it gave one. */
export function ErrorState({ error, onRetry }: { error: ProtoError; onRetry?: () => void }) {
  const denied = error.kind === "denied";
  const title = denied ? "Permission denied" : error.kind === "notfound" ? "Not found" : error.kind === "shape" ? "Unexpected response" : "Could not load";
  return (
    <div className="p-state" data-kind={denied ? "denied" : "error"} role="alert">
      <h2>{title}</h2>
      <p>{error.message}</p>
      {denied ? <p className="muted">This role may not see this data. Nothing was changed.</p> : null}
      {onRetry && !denied ? <div><button type="button" className="p-btn secondary" onClick={onRetry}>Try again</button></div> : null}
    </div>
  );
}

export function PageHead({ title, sub }: { title: string; sub?: ReactNode }) {
  return (
    <div>
      <h1 className="p-h1">{title}</h1>
      {sub ? <p className="p-sub">{sub}</p> : null}
    </div>
  );
}
