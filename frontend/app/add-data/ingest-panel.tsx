"use client";

import { CheckCircle2, FileSpreadsheet, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Badge, Button, Card, CardTitle, Empty, Note } from "@/components/ui";
import { useApp } from "@/lib/app-context";
import { ApiError } from "@/lib/http";
import { commitJob, getJob, KINDS, setMapping, uploadFile, type Job, type Kind } from "@/lib/ingest";
import { cn } from "@/lib/utils";

const STAGES: [string, string, string][] = [
  ["reading", "Reading rows", "पंक्तियाँ पढ़ी जा रही हैं"],
  ["cleaning", "Cleaning and checking", "सफ़ाई और जाँच"],
  ["scoring", "Scoring", "अंकन"],
  ["recompute", "Updating heatmap and list", "हीटमैप और सूची अपडेट"],
];

export function IngestPanel() {
  const { L, lang } = useApp();
  const router = useRouter();
  const [kind, setKind] = useState<Kind>("attendance");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState<"upload" | "mapping" | "commit" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const fail = (e: unknown) =>
    setErr(e instanceof ApiError ? (e.status === 0 ? L("Cannot reach the server. Nothing was uploaded.", "सर्वर तक नहीं पहुँच सके। कुछ अपलोड नहीं हुआ।") : e.message) : (e as Error).message);

  const pick = async (f: File | null | undefined) => {
    if (!f) return;
    setErr(null);
    setJob(null);
    setBusy("upload");
    try {
      setJob(await uploadFile(kind, f));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
      if (input.current) input.current.value = "";
    }
  };

  const remap = async (source: string, target: string) => {
    if (!job) return;
    const mapping = Object.fromEntries(job.columns.map((c) => [c.source, c.source === source ? target || null : c.target]));
    // a field can only come from one column: moving it clears the previous column
    if (target) for (const c of job.columns) if (c.source !== source && c.target === target) mapping[c.source] = null;
    setBusy("mapping");
    setErr(null);
    try {
      setJob(await setMapping(job.job_id, mapping));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const commit = async () => {
    if (!job) return;
    setBusy("commit");
    setErr(null);
    try {
      setJob(await commitJob(job.job_id));
    } catch (e) {
      fail(e);
      setBusy(null);
    }
  };

  // Poll the job while it runs, then jump to the heatmap.
  useEffect(() => {
    if (!job || job.status !== "running") return;
    let alive = true;
    const t = setInterval(async () => {
      try {
        const j = await getJob(job.job_id);
        if (!alive) return;
        setJob(j);
        if (j.status === "done") {
          clearInterval(t);
          setBusy(null);
        }
      } catch (e) {
        if (alive) {
          clearInterval(t);
          setBusy(null);
          fail(e);
        }
      }
    }, 400);
    return () => {
      alive = false;
      clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.job_id, job?.status]);

  const done = job?.status === "done";
  useEffect(() => {
    if (done && job) {
      const t = setTimeout(() => router.push(`/weak-topics?uploaded=${job.job_id}`), 900);
      return () => clearTimeout(t);
    }
  }, [done, job, router]);

  const kindInfo = KINDS.find((k) => k.id === kind)!;
  const label = (id: string) => {
    const t = job?.targets.find((x) => x.id === id);
    return t ? (lang === "hi" && t.label_hi ? t.label_hi : t.label_en) : id;
  };
  const stageIdx = job ? STAGES.findIndex(([s]) => s === job.stage) : -1;

  return (
    <div className="space-y-4">
      <Card>
        <CardTitle>{L("1. What are you uploading?", "1. आप क्या अपलोड कर रहे हैं?")}</CardTitle>
        <div role="radiogroup" aria-label={L("File type", "फ़ाइल का प्रकार")} className="flex flex-wrap gap-2">
          {KINDS.map((k) => (
            <button
              key={k.id}
              role="radio"
              aria-checked={kind === k.id}
              onClick={() => {
                setKind(k.id);
                setJob(null);
                setErr(null);
              }}
              disabled={busy !== null}
              className={cn("rounded-full border px-3 py-1.5 text-sm transition-colors", kind === k.id ? "border-brand bg-brand-soft font-medium text-brand-dark" : "border-line bg-white text-ink-soft hover:bg-bg")}
            >
              {L(k.en, k.hi)}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-ink-mute">
          {L("Expected columns", "अपेक्षित कॉलम")}: {L(kindInfo.hint_en, kindInfo.hint_hi)}. {L("Other column names are matched for you; you can fix any match before saving.", "अन्य कॉलम नाम अपने आप मिलाए जाते हैं; सहेजने से पहले आप कोई भी मिलान बदल सकते हैं।")}
        </p>
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            void pick(e.dataTransfer.files[0]);
          }}
          className={cn("mt-4 flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed p-8 text-center transition-colors focus-within:outline focus-within:outline-2 focus-within:outline-brand", drag ? "border-brand bg-brand-soft" : "border-line bg-white")}
        >
          {busy === "upload" ? <Loader2 className="animate-spin text-brand motion-reduce:animate-none" /> : <FileSpreadsheet className="text-brand" />}
          <span className="font-medium">{busy === "upload" ? L("Reading the file…", "फ़ाइल पढ़ी जा रही है…") : L("CSV or Excel file", "CSV या Excel फ़ाइल")}</span>
          <span className="text-sm text-ink-soft">{L("Drag and drop, or tap to choose", "खींचकर छोड़ें, या चुनने के लिए टैप करें")}</span>
          <input ref={input} data-testid="ingest-file" type="file" accept=".csv,.tsv,.xlsx,.xls" className="sr-only" disabled={busy !== null && busy !== undefined} onChange={(e) => void pick(e.target.files?.[0])} />
        </label>
        {err && (
          <p role="alert" className="mt-3 rounded-xl bg-amber-soft px-3 py-2 text-sm text-[#8a5200]">
            {err}
          </p>
        )}
      </Card>

      {job && (
        <>
          <Card>
            <CardTitle right={<Badge tone="calm">{L("Simulated server", "अनुकरित सर्वर")}</Badge>}>{L("2. Check the column match", "2. कॉलम मिलान जाँचें")} · {job.filename}</CardTitle>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-sm" data-testid="mapping-table">
                <thead>
                  <tr className="text-xs text-ink-mute">
                    <th className="py-1 pr-3 font-medium">{L("Column in your file", "आपकी फ़ाइल का कॉलम")}</th>
                    <th className="py-1 pr-3 font-medium">{L("Example", "उदाहरण")}</th>
                    <th className="py-1 pr-3 font-medium">{L("We read it as", "हमने इसे ऐसे पढ़ा")}</th>
                    <th className="py-1 font-medium">{L("Match", "मिलान")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {job.columns.map((c) => (
                    <tr key={c.source}>
                      <td className="py-2 pr-3 font-medium text-ink">{c.source}</td>
                      <td className="max-w-[140px] truncate py-2 pr-3 text-ink-soft">{job.sample_rows[0]?.[c.source] ?? ""}</td>
                      <td className="py-2 pr-3">
                        <select
                          aria-label={`${L("Field for column", "कॉलम का फ़ील्ड")} ${c.source}`}
                          value={c.target ?? ""}
                          disabled={busy !== null || job.status !== "preview"}
                          onChange={(e) => void remap(c.source, e.target.value)}
                          className="rounded-xl border border-line bg-white px-2 py-1.5 text-sm"
                        >
                          <option value="">{L("Ignore this column", "यह कॉलम छोड़ें")}</option>
                          {job.targets.map((t) => (
                            <option key={t.id} value={t.id}>
                              {label(t.id)}
                              {t.required ? " *" : ""}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2">
                        {!c.target ? (
                          <Badge>{L("Ignored", "छोड़ा गया")}</Badge>
                        ) : c.confidence >= 0.9 ? (
                          <Badge tone="teal">{Math.round(c.confidence * 100)}% · {L("sure", "पक्का")}</Badge>
                        ) : (
                          <Badge tone="amber">{Math.round(c.confidence * 100)}% · {L("please check", "कृपया जाँचें")}</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(job.missing_required.length > 0 || job.one_of_missing) && (
              <div className="mt-3">
                <Note>
                  {job.missing_required.length > 0 && (
                    <span>
                      {L("Still needed", "अभी भी चाहिए")}: <b>{job.missing_required.map(label).join(", ")}</b>.{" "}
                    </span>
                  )}
                  {job.one_of_missing && job.one_of && (
                    <span>
                      {L("Map at least one of", "इनमें से कम से कम एक चुनें")}: <b>{job.one_of.map(label).join(" / ")}</b>.
                    </span>
                  )}
                </Note>
              </div>
            )}
          </Card>

          <Card>
            <CardTitle>{L("3. Rows that need attention", "3. ध्यान देने योग्य पंक्तियाँ")}</CardTitle>
            <div className="mb-3 flex flex-wrap gap-2 text-sm" aria-live="polite">
              <Badge tone="brand">{job.row_count} {L("rows", "पंक्तियाँ")}</Badge>
              <Badge tone="teal">{job.accepted_count} {L("will be saved", "सहेजी जाएँगी")}</Badge>
              <Badge tone={job.rejected_rows ? "amber" : "neutral"} data-testid="rejected-count">{job.rejected_rows} {L("skipped", "छोड़ी जाएँगी")}</Badge>
              {job.warning_count > 0 && <Badge tone="calm">{job.warning_count} {L("notes", "टिप्पणियाँ")}</Badge>}
            </div>
            {job.errors.length === 0 ? (
              <Empty>{L("No problems found in the rows.", "पंक्तियों में कोई समस्या नहीं मिली।")}</Empty>
            ) : (
              <div className="max-h-72 overflow-auto rounded-xl border border-line">
                <table className="w-full min-w-[480px] text-left text-sm" data-testid="row-errors">
                  <thead className="sticky top-0 bg-bg text-xs text-ink-mute">
                    <tr>
                      <th className="px-3 py-1.5 font-medium">{L("Row", "पंक्ति")}</th>
                      <th className="px-3 py-1.5 font-medium">{L("Column", "कॉलम")}</th>
                      <th className="px-3 py-1.5 font-medium">{L("Value", "मान")}</th>
                      <th className="px-3 py-1.5 font-medium">{L("What is wrong", "क्या गड़बड़ है")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {job.errors.map((e, i) => (
                      <tr key={i}>
                        <td className="px-3 py-1.5 tabular-nums">{e.row}</td>
                        <td className="px-3 py-1.5">{e.column}</td>
                        <td className="max-w-[120px] truncate px-3 py-1.5 text-ink-soft">{e.value || "—"}</td>
                        <td className="px-3 py-1.5">
                          <Badge tone={e.severity === "error" ? "amber" : "calm"} className="mr-1.5">{e.severity === "error" ? L("skipped", "छोड़ी") : L("note", "टिप्पणी")}</Badge>
                          {lang === "hi" && e.message_hi ? e.message_hi : e.message_en}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {job.errors_truncated && <p className="mt-2 text-xs text-ink-mute">{L("Showing the first 200 problems.", "पहली 200 समस्याएँ दिखाई गई हैं।")}</p>}
            <p className="mt-2 text-xs text-ink-mute">{L("Skipped rows are not saved. Fix them in your file and upload again; saving the same rows twice is safe.", "छोड़ी गई पंक्तियाँ सहेजी नहीं जातीं। अपनी फ़ाइल में ठीक करके फिर अपलोड करें; वही पंक्तियाँ दोबारा सहेजना सुरक्षित है।")}</p>
          </Card>

          <Card>
            <CardTitle>{L("4. Save", "4. सहेजें")}</CardTitle>
            {job.status === "preview" ? (
              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={commit} disabled={!job.can_commit || busy !== null} data-testid="commit">
                  {busy === "commit" ? <Loader2 size={15} className="animate-spin motion-reduce:animate-none" /> : null}
                  {L(`Save ${job.accepted_count} rows`, `${job.accepted_count} पंक्तियाँ सहेजें`)}
                </Button>
                {!job.can_commit && <span className="text-sm text-ink-soft">{L("Fix the column match above first.", "पहले ऊपर का कॉलम मिलान ठीक करें।")}</span>}
              </div>
            ) : (
              <div aria-live="polite" data-testid="progress">
                <ol className="mb-3 flex flex-wrap gap-2">
                  {STAGES.map(([s, en, hi], i) => (
                    <li key={s}>
                      <Badge tone={done || i <= stageIdx ? "brand" : "neutral"}>{L(en, hi)}</Badge>
                    </li>
                  ))}
                </ol>
                <div className="h-2 overflow-hidden rounded-full bg-[#e9edf4]" role="progressbar" aria-valuenow={Math.round(job.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
                  <div className="h-2 rounded-full bg-brand transition-all" style={{ width: `${Math.round(job.progress * 100)}%` }} />
                </div>
                {job.status === "failed" ? (
                  <p role="alert" className="mt-3 text-sm text-[#8a5200]">{job.error}</p>
                ) : done ? (
                  <p className="mt-3 flex items-center gap-1.5 text-sm font-medium text-[#087f5b]"><CheckCircle2 size={16} /> {(job as { duplicate?: boolean }).duplicate ? L("This exact file was already saved earlier, so nothing changed. Opening the topic map…", "यही फ़ाइल पहले ही सहेजी जा चुकी है, इसलिए कुछ नहीं बदला। विषय मानचित्र खुल रहा है…") : L("Saved. Opening the topic map…", "सहेजा गया। विषय मानचित्र खुल रहा है…")}</p>
                ) : null}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
