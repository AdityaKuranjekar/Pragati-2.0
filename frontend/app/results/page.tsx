"use client";

import type { EChartsOption } from "echarts";
import { EChart } from "@/components/echart";
import { Badge, Card, CardTitle, Note, Origin, PageHead, PageSkeleton, Stat, Unavailable } from "@/components/ui";
import { useApp, useData } from "@/lib/app-context";
import { useBatches } from "@/lib/views";
import { pct } from "@/lib/utils";

const REASONS: Record<string, [string, string]> = {
  academic_gap: ["Academic gap", "पढ़ाई में कमी"],
  homesick_relocation: ["Homesick / relocation", "घर की याद / स्थानांतरण"],
  financial: ["Financial", "आर्थिक"],
  switched_institute: ["Switched institute", "दूसरा संस्थान"],
  health_other: ["Health / other", "स्वास्थ्य / अन्य"],
};

export default function ResultsPage() {
  const { L } = useApp();
  const owner = useData("owner");
  const bq = useBatches();

  if (owner.loading) return <PageSkeleton />;
  const o = owner.data;
  if (!o) return <Unavailable what="results" detail={owner.error} status={owner.status} onRetry={owner.reload} />;

  const batchName = (id: string) => bq.data?.find((b) => b.id === id)?.name ?? L("Another batch", "अन्य बैच");
  const months = o.retention.monthly;
  const first = months[0];
  const last = months[months.length - 1];
  const totalDropped = months.reduce((a, m) => a + m.dropped, 0);
  const retained = first ? 1 - totalDropped / first.enrolled : null;
  const roi = o.roi;

  const forest = (rows: typeof o.batch_compare, name: (r: (typeof rows)[number]) => string): EChartsOption => {
    const ok = rows.filter((r) => r.enough_data);
    return {
      grid: { left: 8, right: 24, top: 8, bottom: 28, containLabel: true },
      xAxis: { type: "value", min: 0, max: 1, axisLabel: { formatter: (v: number) => pct(v) }, name: L("Mean test score", "औसत टेस्ट स्कोर"), nameLocation: "middle", nameGap: 28 },
      yAxis: { type: "category", inverse: true, data: rows.map(name) },
      tooltip: {
        formatter: (p: unknown) => {
          const r = rows[(p as { dataIndex: number }).dataIndex];
          return r.enough_data
            ? `${name(r)}<br/>${pct(r.value, 1)} (${pct(r.ci_low, 1)}–${pct(r.ci_high, 1)}) · n=${r.n}`
            : `${name(r)}<br/>${L("Not enough data yet", "अभी पर्याप्त डेटा नहीं")} · n=${r.n}`;
        },
      },
      series: [
        {
          type: "custom",
          renderItem: (_p, api) => {
            const i = api.value(0) as number;
            const r = rows[i];
            if (!r.enough_data) return { type: "group", children: [] };
            const lo = api.coord([r.ci_low, i]);
            const hi = api.coord([r.ci_high, i]);
            const mid = api.coord([r.value, i]);
            return {
              type: "group",
              children: [
                { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: { stroke: "#3b5bdb", lineWidth: 2 } },
                { type: "line", shape: { x1: lo[0], y1: lo[1] - 5, x2: lo[0], y2: lo[1] + 5 }, style: { stroke: "#3b5bdb", lineWidth: 2 } },
                { type: "line", shape: { x1: hi[0], y1: hi[1] - 5, x2: hi[0], y2: hi[1] + 5 }, style: { stroke: "#3b5bdb", lineWidth: 2 } },
                { type: "circle", shape: { cx: mid[0], cy: mid[1], r: 5 }, style: { fill: "#3b5bdb" } },
              ],
            };
          },
          data: rows.map((_, i) => [i]),
          encode: { x: [], y: 0 },
        },
      ],
      graphic: ok.length === 0 ? [{ type: "text", left: "center", top: "middle", style: { text: L("Not enough data yet", "अभी पर्याप्त डेटा नहीं"), fill: "#7886a3" } }] : [],
    };
  };

  const retention: EChartsOption = {
    legend: { bottom: 0 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: months.map((m) => m.month) },
    yAxis: { type: "value" },
    series: [
      { name: L("Enrolled", "नामांकित"), type: "bar", data: months.map((m) => m.enrolled) },
      { name: L("Left", "छोड़ गए"), type: "line", data: months.map((m) => m.dropped), symbolSize: 6, itemStyle: { color: "#d98a0b" } },
    ],
  };
  const reasons = Object.entries(o.retention.by_reason);
  const reasonOpt: EChartsOption = {
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "value" },
    yAxis: { type: "category", inverse: true, data: reasons.map(([k]) => L(...(REASONS[k] ?? [k, k]))) },
    tooltip: { trigger: "axis" },
    series: [{ type: "bar", data: reasons.map(([, v]) => v), itemStyle: { color: "#5b6fb3" }, barMaxWidth: 22 }],
  };

  return (
    <div className="space-y-6">
      <PageHead sub={L("Is it working, and is it worth it?", "क्या यह काम कर रहा है, और क्या यह फ़ायदेमंद है?")} />

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={L("Students enrolled (latest month)", "नामांकित विद्यार्थी (नवीनतम माह)")} value={last ? last.enrolled : "—"} sub={last?.month} origin={o.origin} />
        <Stat
          label={L("Retained since first month", "पहले माह से टिके")}
          value={retained === null ? L("Not enough data yet", "अभी पर्याप्त डेटा नहीं") : pct(retained)}
          sub={L(`${totalDropped} left in ${months.length} months`, `${months.length} माह में ${totalDropped} गए`)}
          origin={o.origin}
        />
        <Stat label={L("Students who left", "जो विद्यार्थी छोड़ गए")} value={totalDropped} sub={L(`in ${months.length} months`, `${months.length} माह में`)} />
        <Stat label={L("Owner return (range)", "मालिक का रिटर्न (सीमा)")} value={`${roi.ratio_low}–${roi.ratio_high}x`} sub={L(`base ${roi.ratio_base}x`, `आधार ${roi.ratio_base}x`)} origin="assumption" />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle right={<Origin origin={o.origin} />}>{L("Batch comparison", "बैच तुलना")}</CardTitle>
          <EChart option={forest(o.batch_compare, (r) => batchName(r.batch_id))} height={Math.max(200, o.batch_compare.length * 38 + 50)} label="Batch forest plot" />
          <p className="text-xs text-ink-soft">{L("Dot = mean, bar = 95% interval. Batches with too few students are not shown as numbers.", "बिंदु = औसत, रेखा = 95% अंतराल। बहुत कम विद्यार्थियों वाले बैच संख्या के रूप में नहीं दिखाए जाते।")}</p>
        </Card>
        <Card>
          <CardTitle>{L("Faculty comparison", "शिक्षक तुलना")}</CardTitle>
          {o.faculty_compare.length === 0 ? (
            <Note tone="calm">{o.faculty_note ?? L("Faculty is not in the data yet.", "शिक्षक का डेटा अभी उपलब्ध नहीं।")}</Note>
          ) : (
            <EChart option={forest(o.faculty_compare, (r) => String((r as { faculty_id?: string }).faculty_id ?? r.batch_id))} height={Math.max(200, o.faculty_compare.length * 38 + 50)} label="Faculty forest plot" />
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle right={<Origin origin={o.origin} />}>{L("Retention by month", "माह के अनुसार नामांकन")}</CardTitle>
          <EChart option={retention} height={260} label="Retention by month" />
        </Card>
        <Card>
          <CardTitle right={<Origin origin={o.origin} />}>{L("Why students leave", "विद्यार्थी क्यों जाते हैं")}</CardTitle>
          <EChart option={reasonOpt} height={260} label="Reasons for leaving" />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle right={<Origin origin="assumption" />}>{L("Return on fees paid", "दी गई फ़ीस पर रिटर्न")}</CardTitle>
          <div className="grid grid-cols-3 gap-3 text-center">
            {[
              [L("Low", "कम"), roi.ratio_low],
              [L("Base", "आधार"), roi.ratio_base],
              [L("High", "अधिक"), roi.ratio_high],
            ].map(([k, v]) => (
              <div key={String(k)} className="rounded-xl bg-amber-soft p-3">
                <p className="text-xs text-[#8a5200]">{k}</p>
                <p className="text-2xl font-semibold tabular-nums text-ink">{v}x</p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-ink-soft">{roi.note}</p>
          <p className="mt-1 text-xs text-ink-mute">{L("Assumption: willingness to pay is untested until a pilot.", "अनुमान: भुगतान की इच्छा पायलट तक परखी नहीं गई है।")}</p>
        </Card>
      </div>
      <Badge tone="neutral">{L("All numbers are synthetic or modelled; a real pilot settles real uplift.", "सभी संख्याएँ कृत्रिम या मॉडल-आधारित हैं; असली लाभ पायलट से तय होगा।")}</Badge>
    </div>
  );
}
