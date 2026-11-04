"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/lib/app-context";
import { apiFetch } from "@/lib/http";
import { Note } from "./ui";

/** After Add data jumps here with ?uploaded=<job id>, say what was saved. */
export function UploadBanner() {
  const { L, ready } = useApp();
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    if (!ready) return;
    const id = new URLSearchParams(window.location.search).get("uploaded");
    if (!id) return;
    window.history.replaceState(null, "", window.location.pathname);
    const omr = apiFetch<{ filename: string }>(`/ingest/omr/${id}`);
    const file = apiFetch<{ filename: string; accepted_count?: number; rejected_rows?: number }>(`/ingest/jobs/${id}`);
    (id.startsWith("omr_") ? omr : file.catch(() => omr))
      .then((j) => {
        const f = j as { filename: string; accepted_count?: number; rejected_rows?: number };
        setText(
          f.accepted_count !== undefined
            ? L(`Saved ${f.accepted_count} rows from ${f.filename} (${f.rejected_rows ?? 0} skipped). Everything below is up to date.`, `${f.filename} से ${f.accepted_count} पंक्तियाँ सहेजी गईं (${f.rejected_rows ?? 0} छोड़ी गईं)। नीचे सब कुछ अद्यतन है।`)
            : L(`OMR sheet ${f.filename} was scored and saved.`, `OMR शीट ${f.filename} का अंकन हुआ और सहेजी गई।`)
        );
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);
  if (!text) return null;
  return (
    <div role="status" className="animate-pop">
      <Note tone="brand">{text}</Note>
    </div>
  );
}
