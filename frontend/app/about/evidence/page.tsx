"use client";

import type { EChartsOption } from "echarts";
import { EChart } from "@/components/echart";
import { Card, CardTitle, Origin, PageHead, PageSkeleton, Unavailable } from "@/components/ui";
import { useApp, useData } from "@/lib/app-context";
import { pct } from "@/lib/utils";

export default function EvidencePage() {
  const { L } = useApp();
  const risk = useData("risk");
  const moat = useData("moat");
  const owner = useData("owner");
  if (risk.loading && moat.loading) return <PageSkeleton />;
  const r = risk.data;
  const rows = r
    ? [
        { key: "b1_attendance_rule", en: "Attendance < 75% rule", hi: "उपस्थिति < 75% नियम" },
        { key: "b2_ranked_rule", en: "Ranked attendance rule", hi: "क्रमबद्ध उपस्थिति नियम" },
        { key: "model", en: "Pragati model", hi: "प्रगति मॉडल" },
      ].filter((x) => r.baselines[x.key])
    : [];
  const cmp: EChartsOption | null = r
    ? {
        legend: { bottom: 0 },
        xAxis: { type: "category", data: rows.map((b) => L(b.en, b.hi)) },
        yAxis: { type: "value", min: 0, max: 1, axisLabel: { formatter: (v: number) => pct(v) } },
        tooltip: { trigger: "axis", valueFormatter: (v) => pct(Number(v), 1) },
        series: [
          { name: L("Precision", "सटीकता"), type: "bar", data: rows.map((b) => r.baselines[b.key].precision) },
          { name: L("Recall", "पकड़"), type: "bar", data: rows.map((b) => r.baselines[b.key].recall) },
        ],
      }
    : null;
  const mo = moat.data;
  const moatOpt: EChartsOption | null = mo
    ? {
        tooltip: { trigger: "axis" },
        xAxis: { type: "category", data: mo.points.map((p) => String(p.n_institutes)), name: L("Institutes pooling item statistics", "आइटम आँकड़े साझा करने वाले संस्थान"), nameLocation: "middle", nameGap: 30 },
        yAxis: { type: "value", name: L("Difficulty calibration error", "कठिनाई अंशांकन त्रुटि"), scale: true },
        series: [
          { name: "low", type: "line", data: mo.points.map((p) => p.ci_low), lineStyle: { opacity: 0 }, stack: "ci", symbol: "none" },
          { name: "band", type: "line", data: mo.points.map((p) => p.ci_high - p.ci_low), lineStyle: { opacity: 0 }, areaStyle: { color: "#3b5bdb", opacity: 0.15 }, stack: "ci", symbol: "none" },
          { name: L("Error", "त्रुटि"), type: "line", data: mo.points.map((p) => p.calibration_error), symbolSize: 9, lineStyle: { width: 3 } },
        ],
      }
    : null;
  const roi = owner.data?.roi;
  return (
    <div className="space-y-6">
      <PageHead sub={L("Numbers for judges and careful owners. Everything here is synthetic data or an assumption, and says so.", "जजों और सावधान मालिकों के लिए संख्याएँ। यहाँ सब कुछ कृत्रिम डेटा या अनुमान है, और ऐसा लिखा है।")} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle right={<Origin origin="synthetic" />}>{L("Model vs your current rule", "मॉडल बनाम आपका मौजूदा नियम")}</CardTitle>
          {cmp ? <EChart option={cmp} height={260} label="Model vs attendance rule" /> : <Unavailable what="risk" detail={risk.error} status={risk.status} onRetry={risk.reload} />}
          <p className="mt-2 text-sm text-ink-soft">{L("Same list size for each method. A real pilot settles the true uplift.", "हर तरीके के लिए सूची का आकार समान। असली लाभ पायलट से तय होगा।")}</p>
        </Card>
        <Card>
          <CardTitle right={<Origin origin={mo?.origin ?? "synthetic"} />}>{L("The data moat", "डेटा मोट")}</CardTitle>
          {moatOpt ? <EChart option={moatOpt} height={260} label="Calibration error vs institutes" /> : <Unavailable what="moat" detail={moat.error} status={moat.status} onRetry={moat.reload} />}
          <p className="mt-1 text-sm text-ink-soft">{L("Only question difficulty is shared across institutes, never student data.", "संस्थानों के बीच केवल प्रश्नों की कठिनाई साझा होती है, विद्यार्थियों का डेटा कभी नहीं।")}</p>
        </Card>
      </div>
      {roi && (
        <Card>
          <CardTitle right={<Origin origin="assumption" />}>{L("Return on fees paid", "दी गई फ़ीस पर रिटर्न")}</CardTitle>
          <div className="grid grid-cols-3 gap-3 text-center">
            {[[L("Low", "कम"), roi.ratio_low], [L("Base", "आधार"), roi.ratio_base], [L("High", "अधिक"), roi.ratio_high]].map(([k, v]) => (
              <div key={String(k)} className="rounded-xl bg-amber-soft p-3">
                <p className="text-sm text-amber-ink">{k}</p>
                <p className="text-2xl font-semibold tabular-nums">{v}×</p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-ink-soft">{roi.note}</p>
          <p className="mt-1 text-xs text-ink-mute">{L("Willingness to pay is untested until a pilot.", "भुगतान की इच्छा पायलट तक परखी नहीं गई है।")}</p>
        </Card>
      )}
    </div>
  );
}
