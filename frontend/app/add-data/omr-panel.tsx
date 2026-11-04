"use client";

import { Camera, CheckCircle2, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Badge, Button, Card, CardTitle, Empty, Note } from "@/components/ui";
import { useApp } from "@/lib/app-context";
import { ApiError } from "@/lib/http";
import { confirmOmr, uploadOmr, type OmrDoneT, type OmrJob } from "@/lib/ingest";
import { cn } from "@/lib/utils";

const OPTIONS = ["A", "B", "C", "D"];
const WHY: Record<string, [string, string]> = {
  faint_mark: ["Faint mark", "हल्का निशान"],
  double_mark: ["Two bubbles filled", "दो बबल भरे हैं"],
  ambiguous: ["Hard to tell", "स्पष्ट नहीं"],
  unreadable: ["Could not read", "पढ़ा नहीं जा सका"],
};

export function OmrPanel() {
  const { L } = useApp();
  const router = useRouter();
  const [job, setJob] = useState<OmrJob | null>(null);
  const [fixes, setFixes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"read" | "confirm" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<OmrDoneT | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const fail = (e: unknown) => setErr(e instanceof ApiError ? (e.status === 0 ? L("Cannot reach the server. Nothing was sent.", "सर्वर तक नहीं पहुँच सके। कुछ नहीं भेजा गया।") : e.message) : (e as Error).message);

  const pick = async (f: File | null | undefined) => {
    if (!f) return;
    setErr(null);
    setJob(null);
    setDone(null);
    setFixes({});
    setBusy("read");
    try {
      setJob(await uploadOmr(f));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
      if (input.current) input.current.value = "";
    }
  };

  const unc = (job?.result.uncertain ?? []).filter((u) => u.question_no !== null);
  const decided = unc.filter((u) => fixes[String(u.question_no)]).length;
  const total = job ? Object.keys(job.result.questions).length : 0;

  const confirm = async () => {
    if (!job) return;
    setBusy("confirm");
    setErr(null);
    try {
      const r = await confirmOmr(job.job_id, fixes);
      setDone(r);
      setTimeout(() => router.push(`/weak-topics?uploaded=${job.job_id}`), 1400);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardTitle>{L("Photo of an OMR sheet", "OMR शीट की फ़ोटो")}</CardTitle>
        <label className="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-line bg-white p-8 text-center focus-within:outline focus-within:outline-2 focus-within:outline-brand">
          {busy === "read" ? <Loader2 className="animate-spin text-teal motion-reduce:animate-none" /> : <Camera className="text-teal" />}
          <span className="font-medium">{busy === "read" ? L("Reading the sheet…", "शीट पढ़ी जा रही है…") : L("Take or choose a photo", "फ़ोटो लें या चुनें")}</span>
          <span className="text-sm text-ink-soft">{L("Flat sheet, good light, all four corner marks visible", "सीधी शीट, अच्छी रोशनी, चारों कोने के निशान दिखें")}</span>
          <input ref={input} data-testid="omr-file" type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => void pick(e.target.files?.[0])} />
        </label>
        {err && (
          <p role="alert" className="mt-3 rounded-xl bg-amber-soft px-3 py-2 text-sm text-[#8a5200]">
            {err}
          </p>
        )}
      </Card>

      {job?.status === "retake" && (
        <Card>
          <Note>
            <b>{L("Please retake this photo.", "कृपया यह फ़ोटो दोबारा लें।")}</b> {job.result.quality.reason}
          </Note>
        </Card>
      )}

      {job?.status === "review" && !done && (
        <Card>
          <CardTitle right={<Badge tone="calm">{L("Simulated reader", "अनुकरित रीडर")}</Badge>}>{L("Review the uncertain bubbles", "अनिश्चित बबल जाँचें")}</CardTitle>
          <div className="mb-3 flex flex-wrap gap-2 text-sm">
            <Badge tone="brand">{L("Roll", "रोल")} {job.result.roll_no ?? "?"}</Badge>
            <Badge tone="teal">{total - unc.length} {L("of", "में से")} {total} {L("read clearly", "साफ़ पढ़े गए")}</Badge>
            <Badge tone={unc.length ? "amber" : "neutral"}>{decided}/{unc.length} {L("decided", "तय")}</Badge>
          </div>
          {unc.length === 0 ? (
            <Empty>{L("Every bubble was read clearly. Nothing to review.", "हर बबल साफ़ पढ़ा गया। जाँचने को कुछ नहीं।")}</Empty>
          ) : (
            <ul className="divide-y divide-line" data-testid="omr-uncertain">
              {unc.map((u) => {
                const q = String(u.question_no);
                const why = WHY[u.reason] ?? [u.reason, u.reason];
                return (
                  <li key={q} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                    <div>
                      <span className="mr-2 font-semibold text-ink">{L("Q", "प्र")}{q}</span>
                      <Badge tone="amber">{L(...(why as [string, string]))}</Badge>
                      <span className="ml-2 text-xs text-ink-mute">{L("we saw", "हमें दिखा")}: {u.label}</span>
                    </div>
                    <div role="radiogroup" aria-label={`${L("Answer for question", "प्रश्न का उत्तर")} ${q}`} className="flex gap-1.5">
                      {OPTIONS.map((o) => (
                        <button
                          key={o}
                          role="radio"
                          aria-checked={fixes[q] === o}
                          onClick={() => setFixes((f) => ({ ...f, [q]: o }))}
                          className={cn("h-9 w-9 rounded-full border text-sm font-medium transition-colors", fixes[q] === o ? "border-brand bg-brand text-white" : "border-line bg-white text-ink-soft hover:bg-brand-soft")}
                        >
                          {o}
                        </button>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={confirm} disabled={busy !== null || decided < unc.length} data-testid="omr-confirm">
              {busy === "confirm" && <Loader2 size={15} className="animate-spin motion-reduce:animate-none" />}
              {L("Confirm sheet", "शीट की पुष्टि करें")}
            </Button>
            {decided < unc.length && <span className="text-sm text-ink-soft">{L("Pick an answer for each question above.", "ऊपर हर प्रश्न का उत्तर चुनें।")}</span>}
          </div>
        </Card>
      )}

      {done && (
        <Card>
          <p className="flex items-center gap-1.5 font-medium text-[#087f5b]" role="status"><CheckCircle2 size={16} /> {L("Sheet scored. Opening the heatmap…", "शीट का अंकन हुआ। हीटमैप खुल रहा है…")}</p>
          <p className="mt-1 text-sm text-ink-soft">
            {L("Correct", "सही")} {done.scored.correct} · {L("wrong", "गलत")} {done.scored.wrong} · {L("blank", "खाली")} {done.scored.blank} · {L("marks", "अंक")} {done.scored.marks}/{done.scored.max_marks}
          </p>
        </Card>
      )}
    </div>
  );
}
