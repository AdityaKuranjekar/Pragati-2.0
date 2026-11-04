"use client";

import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import { EChart } from "@/components/echart";
import { EmptyState } from "@/components/flair";
import { BatchPicker } from "@/components/pickers";
import { UploadBanner } from "@/components/upload-banner";
import { Badge, Button, Card, CardTitle, Note, PageHead, PageSkeleton, Unavailable } from "@/components/ui";
import { useApp } from "@/lib/app-context";
import { BAND_COLOR, BAND_LABEL, BAND_TONE, type Band } from "@/lib/bands";
import { useBatchChoice, useHeatmap, useRoster } from "@/lib/views";
import { FlaggedPanel } from "./flagged-panel";

const BANDS: Band[] = ["not_enough_data", "needs_support", "steady", "strong"];
const SCALE = 3; // bar axis on the ability scale; never shown as numbers

export default function WeakTopicsPage() {
  const { L, lang } = useApp();
  const { batch, loading: bl, error: be, status: bs, reload: br } = useBatchChoice();
  const hm = useHeatmap(batch?.id ?? null);
  const { byId, loading: rosterLoading } = useRoster();
  const [sel, setSel] = useState<string | null>(null);
  const [details, setDetails] = useState(false);

  const m = hm.data;
  const tn = (t: { name_en: string; name_hi: string }) => (lang === "hi" ? t.name_hi : t.name_en);
  const bandLabel = (b: Band) => L(...BAND_LABEL[b]);
  const nameOf = (id: string) => byId.get(id)?.name ?? L("Student", "विद्यार्थी");

  const grid = useMemo(() => {
    if (!m) return null;
    const ids = [...(m.batches[0]?.student_ids ?? [])].sort((a, b) => (byId.get(a)?.name ?? a).localeCompare(byId.get(b)?.name ?? b));
    const cell = new Map(m.cells.map((c) => [`${c.student_id}|${c.topic_id}`, c]));
    return { ids, topics: m.topics, cell };
  }, [m, byId]);

  const option = useMemo<EChartsOption | null>(() => {
    if (!grid) return null;
    const bandAt = (sid: string, tid: string): Band => (grid.cell.get(`${sid}|${tid}`)?.band as Band) ?? "not_enough_data";
    const data: unknown[] = [];
    grid.ids.forEach((sid, yi) =>
      grid.topics.forEach((t, xi) => {
        const b = t.probably_untaught ? "not_enough_data" : bandAt(sid, t.topic_id);
        data.push({ value: [xi, yi, BANDS.indexOf(b)], itemStyle: { color: BAND_COLOR[b], opacity: t.probably_untaught ? 0.6 : 1 } });
      })
    );
    return {
      grid: { left: 8, right: 8, top: 8, bottom: 120, containLabel: true },
      tooltip: {
        formatter: (p: unknown) => {
          const v = (p as { value: [number, number, number] }).value;
          const t = grid.topics[v[0]];
          const extra = t.probably_untaught ? `<br/>${L("Probably not taught yet", "शायद अभी पढ़ाया नहीं गया")}` : "";
          return `${nameOf(grid.ids[v[1]])}<br/>${tn(t)}<br/><b>${bandLabel(BANDS[v[2]])}</b>${extra}`;
        },
      },
      xAxis: { type: "category", position: "bottom", data: grid.topics.map(tn), axisLabel: { rotate: 55, interval: 0, fontSize: 11, formatter: (s: string) => (s.length > 24 ? s.slice(0, 23) + "…" : s) }, axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: "category", inverse: true, data: grid.ids.map((s) => nameOf(s)), axisLabel: { fontSize: 12 }, axisLine: { show: false }, axisTick: { show: false } },
      visualMap: { type: "piecewise", show: false, dimension: 2, pieces: BANDS.map((b, i) => ({ value: i, color: BAND_COLOR[b] })) },
      series: [{ type: "heatmap", data, itemStyle: { borderColor: "#fff", borderWidth: 2, borderRadius: 3 } }],
    } as EChartsOption;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grid, lang, byId]);

  if (bl) return <PageSkeleton />;
  if (be || !batch) return <Unavailable what={L("batches", "बैच")} detail={be} status={bs} onRetry={br} />;

  const untaught = m?.topics.filter((t) => t.probably_untaught) ?? [];
  const cells = sel && grid ? grid.topics.map((t) => ({ t, c: grid.cell.get(`${sel}|${t.topic_id}`) })) : [];

  return (
    <div className="space-y-6">
      <UploadBanner />
      <PageHead sub={L("Darker means stronger. A mostly pale column is a topic the whole class finds hard.", "गहरा रंग यानी ज़्यादा मज़बूत। लगभग हल्का कॉलम वह विषय है जो पूरी कक्षा को कठिन लगता है।")} right={<BatchPicker onChange={() => setSel(null)} />} />

      {hm.loading || rosterLoading ? (
        <PageSkeleton />
      ) : !m || !grid || !option ? (
        <Unavailable what={L("topic map", "विषय मानचित्र")} detail={hm.error} status={hm.status} onRetry={hm.reload} />
      ) : grid.ids.length === 0 ? (
        <EmptyState title={L("No students in this batch yet", "इस बैच में अभी कोई विद्यार्थी नहीं")}>{L("Add students and a test result to see the topic map.", "विषय मानचित्र देखने के लिए विद्यार्थी और टेस्ट परिणाम जोड़ें।")}</EmptyState>
      ) : (
        <>
          <Card className="bg-white" data-testid="heatmap-card">
            <CardTitle>{L("Topic by topic, student by student", "विषय-दर-विषय, विद्यार्थी-दर-विद्यार्थी")}</CardTitle>
            <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-soft" aria-label={L("Legend", "संकेत")}>
              {BANDS.map((b) => (
                <span key={b} className="inline-flex items-center gap-1.5">
                  <span className="h-3.5 w-3.5 rounded" style={{ background: BAND_COLOR[b], border: "1px solid #d9d3c8" }} />
                  {bandLabel(b)}
                </span>
              ))}
            </div>
            <div className="overflow-x-auto">
              <div className="min-w-[760px]">
                <EChart
                  option={option}
                  height={Math.max(360, grid.ids.length * 20 + 200)}
                  label={L("Topic mastery map", "विषय दक्षता मानचित्र")}
                  onClick={(p) => {
                    const v = (p.value as unknown[] | undefined) ?? [];
                    if (typeof v[1] === "number") setSel(grid.ids[v[1]]);
                  }}
                />
              </div>
            </div>
            <p className="mt-2 text-sm text-ink-mute">{L("Tap a row to see that student's topics.", "किसी पंक्ति पर टैप करें: उस विद्यार्थी के विषय देखें।")}</p>
          </Card>

          {untaught.length > 0 && (
            <Note>
              <b>{untaught.map(tn).slice(0, 3).join(", ")}</b>
              {untaught.length > 3 ? ` +${untaught.length - 3}` : ""}: {L("the whole batch looks low here. Likely not taught yet, not student weakness. Check the teaching plan first.", "पूरा बैच यहाँ कमज़ोर दिखता है। संभवतः अभी पढ़ाया नहीं गया, विद्यार्थी की कमज़ोरी नहीं। पहले शिक्षण योजना देखें।")}
            </Note>
          )}

          {sel && (
            <Card>
              <CardTitle right={<Button variant="ghost" onClick={() => setSel(null)}>{L("Close", "बंद करें")}</Button>}>
                {nameOf(sel)}
              </CardTitle>
              <ul className="grid gap-x-8 gap-y-2 md:grid-cols-2">
                {cells.map(({ t, c }) => {
                  const b: Band = t.probably_untaught ? "not_enough_data" : ((c?.band as Band) ?? "not_enough_data");
                  const show = c && b !== "not_enough_data";
                  const lo = c ? Math.max(-SCALE, c.theta - 1.28 * c.se) : 0;
                  const hi = c ? Math.min(SCALE, c.theta + 1.28 * c.se) : 0;
                  const at = (x: number) => ((x + SCALE) / (2 * SCALE)) * 100;
                  return (
                    <li key={t.topic_id} className="grid grid-cols-[1fr_auto] items-center gap-2 text-sm">
                      <span className="truncate" title={tn(t)}>{tn(t)}</span>
                      <Badge tone={BAND_TONE[b]} className="justify-center">{bandLabel(b)}</Badge>
                      {details && show && c && (
                        <span className="relative col-span-2 h-2 rounded-full bg-[#ece9e3]" aria-label={L("Likely range", "संभावित सीमा")}>
                          <span className="absolute h-2 rounded-full bg-brand/35" style={{ left: `${at(lo)}%`, width: `${Math.max(2, at(hi) - at(lo))}%` }} />
                          <span className="absolute -top-0.5 h-3 w-1 rounded bg-brand" style={{ left: `${at(c.theta)}%` }} />
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
              <button onClick={() => setDetails((d) => !d)} className="mt-3 text-sm font-medium text-brand-dark underline-offset-2 hover:underline" aria-expanded={details}>
                {details ? L("Hide details", "विवरण छिपाएँ") : L("Show details: how sure we are", "विवरण दिखाएँ: हम कितने निश्चित हैं")}
              </button>
              {details && <p className="mt-1 text-xs text-ink-soft">{L("Bar = likely range, tick = best estimate. A wide bar means we are less sure.", "पट्टी = संभावित सीमा, निशान = सर्वोत्तम अनुमान। चौड़ी पट्टी = कम निश्चितता।")}</p>}
            </Card>
          )}
        </>
      )}

      <FlaggedPanel batchId={batch.id} />
    </div>
  );
}
