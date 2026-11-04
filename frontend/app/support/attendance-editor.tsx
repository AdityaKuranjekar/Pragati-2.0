"use client";

import { Loader2, Pencil } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import { useApp } from "@/lib/app-context";
import { ApiError } from "@/lib/http";
import { patchAttendance, type AttendanceResult } from "@/lib/teacher-api";

/** Inline "edit attendance". The server validates (for example 140 %) and its message is shown as is. */
export function AttendanceEditor({
  studentId,
  current,
  onSaved,
  alwaysOpen = false,
}: {
  studentId: string;
  current?: number;
  onSaved: (r: AttendanceResult) => void;
  alwaysOpen?: boolean;
}) {
  const { L } = useApp();
  const [open, setOpen] = useState(alwaysOpen);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    const v = Number(text.replace("%", "").trim());
    if (text.trim() === "" || Number.isNaN(v)) {
      setError(L("Type a number, for example 82", "संख्या लिखें, जैसे 82"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await patchAttendance(studentId, v);
      onSaved(r);
      setText("");
      if (!alwaysOpen) setOpen(false);
    } catch (e) {
      setError(e instanceof ApiError ? (e.status === 0 ? L("Cannot reach the server. Nothing was saved.", "सर्वर तक नहीं पहुँच सके। कुछ सहेजा नहीं गया।") : e.message) : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!open)
    return (
      <div className="flex items-center gap-2 text-xs text-ink-soft">
        {current !== undefined && (
          <span>
            {L("Attendance", "उपस्थिति")} <b className="text-ink">{current}%</b>
          </span>
        )}
        <button onClick={() => setOpen(true)} className="inline-flex items-center gap-1 rounded-lg px-1.5 py-1 text-brand-dark hover:bg-brand-soft" data-testid="edit-attendance">
          <Pencil size={12} /> {L("Edit attendance", "उपस्थिति बदलें")}
        </button>
      </div>
    );

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor={`att-${studentId}`}>{L("Attendance percent", "उपस्थिति प्रतिशत")}</label>
        <input
          id={`att-${studentId}`}
          data-testid="attendance-input"
          inputMode="decimal"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void save()}
          placeholder={current !== undefined ? String(current) : "%"}
          aria-invalid={!!error}
          aria-describedby={error ? `att-err-${studentId}` : undefined}
          className="w-20 rounded-xl border border-line bg-white px-2 py-1.5 text-sm"
        />
        <Button variant="soft" onClick={() => void save()} disabled={busy} data-testid="attendance-save" className="px-3 py-1.5">
          {busy && <Loader2 size={13} className="animate-spin motion-reduce:animate-none" />}
          {L("Save", "सहेजें")}
        </Button>
        {!alwaysOpen && (
          <Button variant="ghost" onClick={() => { setOpen(false); setError(null); }} className="px-2 py-1.5">
            {L("Cancel", "रद्द करें")}
          </Button>
        )}
      </div>
      {error && (
        <p id={`att-err-${studentId}`} role="alert" data-testid="attendance-error" className="mt-1 text-xs text-[#8a5200]">
          {error}
        </p>
      )}
    </div>
  );
}
