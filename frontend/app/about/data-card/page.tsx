"use client";

import { AlertTriangle } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, Button, Card, CardTitle, Origin, PageHead, PageSkeleton, Unavailable } from "@/components/ui";
import { figureUrl } from "@/lib/api";
import { useApp, useData } from "@/lib/app-context";
import { cn } from "@/lib/utils";

export default function DataCardPage() {
  const { L } = useApp();
  const { data: d, loading, error, status } = useData("datacard");
  const [step, setStep] = useState(0);
  const [q, setQ] = useState("");
  const [missing, setMissing] = useState<Set<string>>(new Set());

  const attrs = useMemo(() => {
    const s = q.trim().toLowerCase();
    return (d?.attributes ?? []).filter((a) => !s || Object.values(a).some((v) => String(v).toLowerCase().includes(s)));
  }, [d, q]);

  if (loading) return <PageSkeleton />;
  if (!d) return <Unavailable what="datacard" detail={error} status={status} />;
  const st = d.story_steps[Math.min(step, d.story_steps.length - 1)];
  const tone = (c: string) => (c === "high" ? "teal" : c === "medium" ? "amber" : "calm");

  return (
    <div className="space-y-6">
      <PageHead
        title={L("Data card", "डेटा कार्ड")}
        sub={L("How the synthetic data was made, what it can and cannot tell us.", "कृत्रिम डेटा कैसे बना, वह क्या बता सकता है और क्या नहीं।")}
        right={<Origin origin={d.origin} />}
      />

      <Card className="border-amber/40 bg-amber-soft">
        <CardTitle>
          <span className="inline-flex items-center gap-2">
            <AlertTriangle size={16} /> {L("Limits", "सीमाएँ")}
          </span>
        </CardTitle>
        <ul className="list-disc space-y-1 pl-5 text-sm text-[#5f3d04]">
          {d.limits.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardTitle>{L("How the data was generated", "डेटा कैसे बनाया गया")}</CardTitle>
        <ol className="mb-4 flex flex-wrap gap-2" aria-label="Steps">
          {d.story_steps.map((s, i) => (
            <li key={s.id}>
              <button
                onClick={() => setStep(i)}
                aria-current={i === step}
                className={cn("h-8 w-8 rounded-full text-sm font-medium", i === step ? "bg-brand text-white" : i < step ? "bg-brand-soft text-brand-dark" : "bg-bg text-ink-soft")}
              >
                {s.id}
              </button>
            </li>
          ))}
        </ol>
        <p className="font-medium text-ink">{st.title}</p>
        <div className="mt-3 flex gap-2">
          <Button variant="ghost" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
            {L("Back", "पीछे")}
          </Button>
          <Button variant="soft" disabled={step >= d.story_steps.length - 1} onClick={() => setStep((s) => s + 1)}>
            {L("Next", "आगे")}
          </Button>
        </div>
      </Card>

      <Card>
        <CardTitle
          right={
            <input
              aria-label="Search attributes"
              placeholder={L("Search attributes…", "विशेषताएँ खोजें…")}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-44 rounded-xl border border-line px-3 py-1.5 text-sm"
            />
          }
        >
          {L("Attributes", "विशेषताएँ")} ({attrs.length})
        </CardTitle>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs text-ink-mute">
              <tr>
                {["Attribute", "Source", "Decision", "Model", "Privacy class"].map((h) => (
                  <th key={h} className="pb-2 pr-3 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {attrs.map((a) => (
                <tr key={a.name} className="align-top">
                  <td className="py-2 pr-3 font-medium">{a.name}</td>
                  <td className="py-2 pr-3 text-ink-soft">{a.real_world_source}</td>
                  <td className="py-2 pr-3 text-ink-soft">{a.decision}</td>
                  <td className="py-2 pr-3 text-ink-soft">{a.model}</td>
                  <td className="py-2 pr-3">
                    <Badge tone="neutral">{a.privacy_class}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {attrs.length === 0 && <p className="py-4 text-sm text-ink-soft">{L("No attribute matches.", "कोई विशेषता नहीं मिली।")}</p>}
        </div>
      </Card>

      <Card>
        <CardTitle>{L("Realism checklist", "यथार्थता जाँच-सूची")}</CardTitle>
        <ul className="divide-y divide-line text-sm">
          {d.checklist.map((c) => (
            <li key={c.parameter} className="flex flex-wrap items-start justify-between gap-2 py-2">
              <div>
                <p className="font-medium">{c.parameter}</p>
                <p className="text-ink-soft">
                  {c.our_value} <span className="text-ink-mute">· {c.source}</span>
                </p>
              </div>
              <Badge tone={tone(c.confidence)}>{c.confidence} {L("confidence", "विश्वास")}</Badge>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardTitle>{L("Figures", "चित्र")}</CardTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {d.figures.map((f) => (
            <figure key={f.path} className="rounded-xl border border-line p-2">
              {missing.has(f.path) ? (
                <div className="grid h-40 place-items-center rounded-lg bg-bg text-xs text-ink-mute">{L("Figure not generated yet", "चित्र अभी बना नहीं")}</div>
              ) : (
                <img src={figureUrl(f.path)} alt={f.caption} className="h-40 w-full rounded-lg object-contain" onError={() => setMissing((m) => new Set(m).add(f.path))} />
              )}
              <figcaption className="mt-2 flex items-start justify-between gap-2 text-xs text-ink-soft">
                {f.caption}
                <Origin origin={f.origin} />
              </figcaption>
            </figure>
          ))}
        </div>
      </Card>

      <Card>
        <CardTitle>{L("Name cleaning examples", "नाम सफ़ाई के उदाहरण")}</CardTitle>
        <ul className="space-y-1 text-sm">
          {d.cleaning.examples.map((e, i) => (
            <li key={i} className="flex items-center gap-3">
              <code className="rounded bg-bg px-2 py-0.5">{e.raw}</code>→<code className="rounded bg-teal-soft px-2 py-0.5">{e.clean}</code>
            </li>
          ))}
        </ul>
        {d.cleaning.note && <p className="mt-2 text-xs text-ink-soft">{d.cleaning.note}</p>}
      </Card>
    </div>
  );
}
