"use client";
export default function PrototypeError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="p-card" role="alert">
      <h1 className="p-h2">This page could not be shown</h1>
      <p className="muted" style={{ margin: "4px 0 12px" }}>Something went wrong while loading it.</p>
      <button type="button" className="p-btn" onClick={reset}>Try again</button>
    </div>
  );
}
