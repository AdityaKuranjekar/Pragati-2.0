"use client";

import { ArrowRight } from "lucide-react";
import type { EChartsOption } from "echarts";
import { EChart } from "@/components/echart";
import { Badge, Card, CardTitle, Note, Origin, PageHead, PageSkeleton, Unavailable } from "@/components/ui";
import { useApp, useData } from "@/lib/app-context";

const PAIN: { pain: [string, string]; feature: [string, string]; model: string; view: [string, string] }[] = [
  { pain: ["Messy data from OMR, Excel and WhatsApp", "OMR, Excel और WhatsApp का अव्यवस्थित डेटा"], feature: ["Capture and cleaning", "डेटा जोड़ना और सफ़ाई"], model: "Rules + OpenCV", view: ["Capture", "डेटा जोड़ें"] },
  { pain: ["Nobody knows which topics are weak", "किस विषय में कमज़ोरी है, पता नहीं"], feature: ["Topic mastery heatmap", "विषय-वार दक्षता हीटमैप"], model: "Hierarchical IRT", view: ["Teacher", "शिक्षक"] },
  { pain: ["Students drop out without warning", "विद्यार्थी बिना चेतावनी छोड़ देते हैं"], feature: ["Early warning with reasons", "कारणों सहित पूर्व चेतावनी"], model: "LightGBM + SHAP", view: ["Teacher, Owner", "शिक्षक, मालिक"] },
  { pain: ["Parents hear little, too late", "अभिभावकों को कम और देर से पता चलता है"], feature: ["Verified Hindi/English reports", "सत्यापित हिंदी/अंग्रेज़ी रिपोर्ट"], model: "Templates + local LLM + verifier", view: ["Parent", "अभिभावक"] },
  { pain: ["Owner cannot see what works", "मालिक देख नहीं पाता क्या काम करता है"], feature: ["Batch comparison and ROI range", "बैच तुलना और ROI सीमा"], model: "Intervals + conformal bands", view: ["Owner", "मालिक"] },
];

const RULES: [string, string][] = [
  ["No leaderboards, no ranks, never sorted by score or risk", "कोई लीडरबोर्ड या रैंक नहीं, स्कोर या जोखिम के क्रम में नहीं"],
  ["Students and parents never see a risk probability", "विद्यार्थी और अभिभावक कभी जोखिम की प्रायिकता नहीं देखते"],
  ["Minors get academic support only, never behaviour tracking", "नाबालिगों के लिए केवल शैक्षिक सहयोग, व्यवहार की निगरानी कभी नहीं"],
  ["Calm colours, supportive actions, counsellor always reachable", "शांत रंग, सहायक कदम, काउंसलर हमेशा उपलब्ध"],
  ["Too little data shows as “Not enough data yet”", "कम डेटा पर “अभी पर्याप्त डेटा नहीं” दिखता है"],
];

export default function HowItWorksPage() {
  const { L } = useApp();
  const sc = useData("scaling");
  const md = useData("models");
  if (sc.loading) return <PageSkeleton />;
  const s = sc.data;
  if (!s) return <Unavailable what="scaling" detail={sc.error} status={sc.status} />;

  const lineKeys = Array.from(new Set(s.cost_per_student.flatMap((c) => Object.keys(c.lines))));
  const cost: EChartsOption = {
    legend: { bottom: 0 },
    tooltip: { trigger: "axis", valueFormatter: (v) => `₹${Number(v).toFixed(2)}` },
    xAxis: { type: "category", data: s.cost_per_student.map((c) => c.students.toLocaleString("en-IN")), name: L("Students", "विद्यार्थी"), nameLocation: "middle", nameGap: 28 },
    yAxis: { type: "value", name: L("₹ per student", "₹ प्रति विद्यार्थी") },
    series: lineKeys.map((k) => ({ name: k.replace(/_/g, " "), type: "bar" as const, stack: "c", data: s.cost_per_student.map((c) => c.lines[k] ?? 0) })),
  };
  const m = md.data;

  return (
    <div className="space-y-6">
      <PageHead sub={L("From a pain point to a model to a screen, and how it grows.", "समस्या से मॉडल, मॉडल से स्क्रीन, और यह कैसे बढ़ता है।")} right={<Origin origin={s.origin} />} />

      <Card>
        <CardTitle>{L("Five pain points", "पाँच समस्याएँ")}</CardTitle>
        <ul className="divide-y divide-line">
          {PAIN.map((p, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2 py-3 text-sm">
              <span className="min-w-[220px] flex-1 font-medium">{L(...p.pain)}</span>
              <ArrowRight size={14} className="text-ink-mute" />
              <Badge tone="brand">{L(...p.feature)}</Badge>
              <ArrowRight size={14} className="text-ink-mute" />
              <Badge tone="calm">{p.model}</Badge>
              <ArrowRight size={14} className="text-ink-mute" />
              <Badge tone="teal">{L(...p.view)}</Badge>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardTitle>{L("Pilot, seed, scale", "पायलट, सीड, स्केल")}</CardTitle>
        <ol className="grid gap-3 md:grid-cols-3">
          {s.stages.map((st, i) => (
            <li key={st.name} className="relative rounded-xl border border-line bg-bg p-4">
              <p className="text-xs text-ink-mute">{L("Stage", "चरण")} {i + 1}</p>
              <p className="text-lg font-semibold">{st.name}</p>
              <p className="text-sm text-brand-dark">{st.students} {L("students", "विद्यार्थी")}</p>
              <p className="mt-1 text-sm text-ink-soft">{st.stack}</p>
            </li>
          ))}
        </ol>
        <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
          <Note tone="brand">{L("Tenant isolation: every institute's rows are separated by row-level security; only item difficulty is ever shared.", "टेनेंट अलगाव: हर संस्थान की पंक्तियाँ रो-लेवल सिक्योरिटी से अलग हैं; केवल प्रश्नों की कठिनाई साझा होती है।")}</Note>
          <Note tone="brand">{L("Offline-first: capture works without internet and syncs later; reports fall back to templates when no model is available.", "ऑफ़लाइन-फ़र्स्ट: बिना इंटरनेट डेटा जुड़ता है और बाद में सिंक होता है; मॉडल न हो तो रिपोर्ट टेम्पलेट से बनती है।")}</Note>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle right={<Origin origin="assumption" />}>{L("Cost per student", "प्रति विद्यार्थी लागत")}</CardTitle>
          <EChart option={cost} height={280} label="Cost per student" />
          {s.cost_note && <p className="mt-1 text-xs text-ink-soft">{s.cost_note}</p>}
        </Card>
        <Card>
          <CardTitle>{L("What can go wrong", "क्या गलत हो सकता है")}</CardTitle>
          <ul className="space-y-3 text-sm">
            {s.failure_modes.map((f) => (
              <li key={f.case}>
                <p className="font-medium">{f.case}</p>
                <p className="text-ink-soft">→ {f.response}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <CardTitle right={<Origin origin="synthetic" />}>{L("Honest results", "ईमानदार नतीजे")}</CardTitle>
        {m ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="text-xs text-ink-mute">
                <tr>
                  <th className="pb-2 font-medium">{L("Early-warning method", "पूर्व-चेतावनी विधि")}</th>
                  <th className="pb-2 font-medium">{L("Precision", "सटीकता")}</th>
                  <th className="pb-2 font-medium">{L("Recall", "पकड़")}</th>
                  <th className="pb-2 font-medium">AUC</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {[
                  ["Attendance < 75% rule", m.risk.b1_attendance_rule, null],
                  ["Ranked attendance rule", m.risk.b2_ranked_attendance, m.risk.b2_ranked_attendance.auc],
                  ["Pragati, academic only (minors)", m.risk.academic_lgbm, m.risk.academic_lgbm.auc],
                  ["Pragati, full (18+, own consent)", m.risk.full_lgbm, m.risk.full_lgbm.auc],
                ].map(([name, v, auc]) => {
                  const r = v as { precision: number; recall: number };
                  return (
                    <tr key={String(name)}>
                      <td className="py-2">{String(name)}</td>
                      <td className="py-2 tabular-nums">{(r.precision * 100).toFixed(0)}%</td>
                      <td className="py-2 tabular-nums">{(r.recall * 100).toFixed(0)}%</td>
                      <td className="py-2 tabular-nums">{auc === null ? "—" : (auc as number).toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-ink-soft">
              {L("Base rate", "आधार दर")} {(m.risk.base_rate * 100).toFixed(0)}%. {L("Ability recovery (θ vs planted truth), per institute:", "क्षमता पुनर्प्राप्ति (θ बनाम असली मान), संस्थान-वार:")}{" "}
              {m.irt.map((x) => `${x.institute} r=${x.theta_r_rasch.toFixed(2)}`).join(" · ")}
            </p>
            <Note tone="calm">{L("These are synthetic-data results. We show weak numbers too. A real pilot settles the true uplift over the attendance rule.", "ये कृत्रिम डेटा के नतीजे हैं। कमज़ोर संख्याएँ भी दिखाई गई हैं। असली लाभ पायलट से तय होगा।")}</Note>
          </div>
        ) : (
          <Unavailable what="models" detail={md.error} status={md.status} />
        )}
      </Card>

      <Card>
        <CardTitle>{L("What each person sees", "हर व्यक्ति को क्या दिखता है")}</CardTitle>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="text-xs text-ink-mute">
              <tr>
                <th className="pb-2 font-medium">{L("Behind the scenes", "पर्दे के पीछे")}</th>
                <th className="pb-2 font-medium">{L("Teacher", "शिक्षक")}</th>
                <th className="pb-2 font-medium">{L("Student / parent", "विद्यार्थी / अभिभावक")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              <tr><td className="py-2">{L("Ability score (θ) and its error", "क्षमता अंक (θ) और उसकी त्रुटि")}</td><td className="py-2">{L("Bands plus a likely-range bar", "बैंड और संभावित सीमा की पट्टी")}</td><td className="py-2">{L("Building / Steady / Strong, and “right lately” %", "सीख रहे हैं / स्थिर / मज़बूत, और “हाल में सही” %")}</td></tr>
              <tr><td className="py-2">{L("Dropout model weights", "ड्रॉपआउट मॉडल के भार")}</td><td className="py-2">{L("Plain reasons and a supportive action", "सरल कारण और सहायक कदम")}</td><td className="py-2">{L("Never shown; a counsellor invitation instead", "कभी नहीं दिखता; इसके बजाय काउंसलर का निमंत्रण")}</td></tr>
              <tr><td className="py-2">{L("Percentile band and mapping table", "पर्सेंटाइल सीमा और मैपिंग तालिका")}</td><td className="py-2">{L("Range with assumption tag", "अनुमान टैग सहित सीमा")}</td><td className="py-2">{L("Range with “how to read it”", "“कैसे पढ़ें” सहित सीमा")}</td></tr>
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <CardTitle>{L("Well-being rules", "विद्यार्थी-हित के नियम")}</CardTitle>
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink-soft">
          {RULES.map((r, i) => (
            <li key={i}>{L(...r)}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
