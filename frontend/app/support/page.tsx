"use client";

import { Check, ChevronDown, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/flair";
import { BatchPicker } from "@/components/pickers";
import { UploadBanner } from "@/components/upload-banner";
import { Badge, Button, Card, CardTitle, PageHead, PageSkeleton, Select, Unavailable } from "@/components/ui";
import { useApp } from "@/lib/app-context";
import type { AttendanceResult } from "@/lib/teacher-api";
import { useBatchChoice, useRoster, useSupportList } from "@/lib/views";
import { cn } from "@/lib/utils";
import { AttendanceEditor } from "./attendance-editor";

export default function SupportPage() {
  const { L, lang, institute } = useApp();
  const { batch, loading: bl, error: be, status: bs, reload: br } = useBatchChoice();
  const sl = useSupportList(batch?.id ?? null);
  const { byId, loading: rosterLoading } = useRoster();
  const [done, setDone] = useState<string[]>([]);
  const [note, setNote] = useState<{ en: string; hi: string } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [whatIf, setWhatIf] = useState("");

  useEffect(() => {
    try {
      setDone(JSON.parse(localStorage.getItem(`pragati.done.${institute}`) ?? "[]"));
    } catch {}
  }, [institute]);
  const toggle = (id: string) =>
    setDone((d) => {
      const n = d.includes(id) ? d.filter((x) => x !== id) : [...d, id];
      try {
        localStorage.setItem(`pragati.done.${institute}`, JSON.stringify(n));
      } catch {}
      return n;
    });

  const name = (id: string) => byId.get(id)?.name ?? L("Student", "विद्यार्थी");
  const rows = useMemo(() => [...(sl.data?.list ?? [])].sort((a, b) => name(a.student_id).localeCompare(name(b.student_id))), // by name, never by score
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sl.data, byId]);
  const att = new Map((sl.data?.list ?? []).map((x) => [x.student_id, x.attendance_pct]));
  const inBatch = [...byId.values()].filter((p) => p.batchId === batch?.id).sort((a, b) => a.name.localeCompare(b.name));
  const whatId = whatIf || inBatch[0]?.id || "";

  const saved = (r: AttendanceResult) => {
    setNote({ en: r.message_en, hi: r.message_hi ?? r.message_en });
    if (r.support_list) sl.mutate(r.support_list);
    else sl.reload();
  };

  if (bl) return <PageSkeleton />;
  if (be || !batch) return <Unavailable what={L("batches", "बैच")} detail={be} status={bs} onRetry={br} />;
  const doneCount = rows.filter((r) => done.includes(r.student_id)).length;

  return (
    <div className="space-y-5">
      <UploadBanner />
      <PageHead sub={L("A short list sized to your mentors' time. Each name shows the reason and one next step. Sorted by name.", "मेंटरों के समय के हिसाब से छोटी सूची। हर नाम के साथ कारण और एक अगला कदम। नाम के क्रम में।")} right={<BatchPicker />} />

      <Card className="bg-white">
        <CardTitle
          right={
            <Button variant="ghost" className="border border-line" onClick={sl.reload} disabled={sl.refreshing} data-testid="refresh-list" aria-label={L("Refresh the list", "सूची ताज़ा करें")}>
              <RefreshCw size={16} className={sl.refreshing ? "animate-spin motion-reduce:animate-none" : ""} /> {L("Refresh", "ताज़ा करें")}
            </Button>
          }
        >
          {L("This week", "इस सप्ताह")} · {doneCount}/{rows.length} {L("done", "पूरे")}
        </CardTitle>
        {note && (
          <p role="status" data-testid="edit-note" className="mb-3 rounded-xl bg-teal-soft px-3 py-2 text-sm text-teal-ink">
            {L(note.en, note.hi)}
          </p>
        )}
        {sl.loading || rosterLoading ? (
          <PageSkeleton />
        ) : !sl.data ? (
          <Unavailable what={L("support list", "सहयोग सूची")} detail={sl.error} status={sl.status} onRetry={sl.reload} />
        ) : rows.length === 0 ? (
          <EmptyState title={L("No one is on the list this week", "इस सप्ताह सूची में कोई नहीं है")} tone="teal">
            {L("Check again after the next test.", "अगले टेस्ट के बाद फिर देखें।")}
          </EmptyState>
        ) : (
          <ul className="space-y-3" data-testid="support-list">
            {rows.map((row) => {
              const isDone = done.includes(row.student_id);
              const isOpen = open === row.student_id;
              return (
                <li key={row.student_id} data-student={row.student_id} data-track={row.track} className={cn("rounded-2xl border p-4 transition-colors", isDone ? "border-teal/40 bg-teal-soft/60" : "border-line bg-white")}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2 text-lg font-semibold text-ink">
                        {name(row.student_id)}
                        <Badge tone={row.track === "full" ? "teal" : "calm"}>{row.track === "full" ? L("Adult, own consent", "वयस्क, स्वयं की सहमति") : L("Academic support", "शैक्षिक सहयोग")}</Badge>
                      </p>
                      <ul className="mt-1 list-disc pl-5 text-ink-soft">
                        {row.reasons.slice(0, 3).map((x) => (
                          <li key={x.code}>{lang === "hi" ? x.text_hi : x.text_en}</li>
                        ))}
                      </ul>
                      <p className="mt-2 rounded-xl bg-brand-soft px-3 py-2 font-medium text-brand-dark">→ {lang === "hi" ? row.supportive_action.text_hi : row.supportive_action.text_en}</p>
                    </div>
                    <Button variant={isDone ? "primary" : "soft"} aria-pressed={isDone} onClick={() => toggle(row.student_id)} className={isDone ? "bg-teal hover:bg-teal-ink" : ""}>
                      <Check size={16} /> {isDone ? L("Done", "हो गया") : L("Mark as done", "हो गया चिह्नित करें")}
                    </Button>
                  </div>
                  <button onClick={() => setOpen(isOpen ? null : row.student_id)} aria-expanded={isOpen} className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-brand-dark" data-testid="row-details">
                    <ChevronDown size={16} className={cn("transition-transform", isOpen && "rotate-180")} /> {isOpen ? L("Hide details", "विवरण छिपाएँ") : L("Show details", "विवरण दिखाएँ")}
                  </button>
                  {isOpen && (
                    <div className="mt-2 rounded-xl bg-bg p-3">
                      <p className="mb-1 text-sm text-ink-soft">{L("If the attendance record is wrong, correct it here.", "उपस्थिति रिकॉर्ड गलत हो तो यहाँ सुधारें।")}</p>
                      <AttendanceEditor studentId={row.student_id} current={row.attendance_pct} onSaved={saved} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card>
        <CardTitle>{L("Correct attendance", "उपस्थिति सुधारें")}</CardTitle>
        <p className="mb-3 text-sm text-ink-soft">{L("Choose a student and enter the correct attendance %. The list above updates. For students under 18 the attendance is saved, but it is not used to build the list.", "विद्यार्थी चुनें और सही उपस्थिति % लिखें। ऊपर की सूची बदल जाएगी। 18 से कम उम्र के विद्यार्थियों की उपस्थिति सहेजी जाती है, पर सूची बनाने में इस्तेमाल नहीं होती।")}</p>
        {inBatch.length === 0 ? (
          <p className="text-sm text-ink-soft">{L("No students in this batch yet.", "इस बैच में अभी कोई विद्यार्थी नहीं।")}</p>
        ) : (
          <>
            <Select label={L("Student", "विद्यार्थी")} value={whatId} onChange={setWhatIf} options={inBatch.map((p) => ({ value: p.id, label: `${p.name} · ${p.roll}` }))} />
            <div className="mt-3">
              <AttendanceEditor key={whatId} studentId={whatId} current={att.get(whatId)} onSaved={saved} alwaysOpen />
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
