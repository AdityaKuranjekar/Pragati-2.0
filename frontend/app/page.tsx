"use client";

import { ArrowRight, Check, GraduationCap, HeartHandshake, LayoutGrid, Sparkles, Smartphone, Upload, Users, Building2, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CountUp, IconTile, Ring } from "@/components/flair";
import { Card, PageSkeleton, Unavailable } from "@/components/ui";
import { useApp, useData } from "@/lib/app-context";
import { useBatches, useWeeklyActions } from "@/lib/views";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: "data", href: "/add-data", icon: Upload, tone: "bg-tint-add", en: "Add data", hi: "डेटा जोड़ें", den: "Upload new test results or attendance.", dhi: "नए टेस्ट परिणाम या उपस्थिति अपलोड करें।" },
  { id: "topics", href: "/weak-topics", icon: LayoutGrid, tone: "bg-tint-weak", en: "See weak topics", hi: "कमज़ोर विषय देखें", den: "See which topics the class is weak in.", dhi: "देखें कि कक्षा किन विषयों में कमज़ोर है।" },
  { id: "help", href: "/support", icon: HeartHandshake, tone: "bg-tint-support", en: "Follow up", hi: "विद्यार्थियों से बात करें", den: "Talk to the students on the list.", dhi: "सूची के विद्यार्थियों से बात करें।" },
  { id: "parents", href: "/parents", icon: Smartphone, tone: "bg-tint-parent", en: "Tell parents", hi: "अभिभावकों को बताएँ", den: "Send parents the monthly report.", dhi: "अभिभावकों को मासिक रिपोर्ट भेजें।" },
  { id: "results", href: "/results", icon: Building2, tone: "bg-tint-results", en: "Check results", hi: "नतीजे देखें", den: "See how many students are staying.", dhi: "देखें कितने विद्यार्थी टिके हुए हैं।" },
];

export default function HomePage() {
  const { L, institute } = useApp();
  const owner = useData("owner");
  const batches = useBatches();
  const weekly = useWeeklyActions();
  const [done, setDone] = useState<string[]>([]);
  useEffect(() => {
    try {
      setDone(JSON.parse(localStorage.getItem(`pragati.flow.${institute}`) ?? "[]"));
    } catch {}
  }, [institute]);
  const toggle = (id: string) =>
    setDone((d) => {
      const n = d.includes(id) ? d.filter((x) => x !== id) : [...d, id];
      try {
        localStorage.setItem(`pragati.flow.${institute}`, JSON.stringify(n));
      } catch {}
      return n;
    });

  if (owner.loading && batches.loading) return <PageSkeleton />;
  const next = STEPS.find((s) => !done.includes(s.id)) ?? STEPS[STEPS.length - 1];
  const months = owner.data?.retention.monthly ?? [];
  const first = months[0];
  const dropped = months.reduce((a, m) => a + m.dropped, 0);
  const retained = first ? 1 - dropped / first.enrolled : null;
  const students = (batches.data ?? []).reduce((a, b) => a + (b.students ?? 0), 0);
  const roi = owner.data?.roi;

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand to-[#5c7cfa] p-6 text-white shadow-lift sm:p-8">
        <div className="absolute -right-10 -top-10 h-44 w-44 rounded-full bg-white/10" aria-hidden />
        <div className="absolute -bottom-16 right-24 h-40 w-40 rounded-full bg-white/10" aria-hidden />
        <p className="flex items-center gap-2 text-sm font-medium text-white/85"><Sparkles size={16} /> {L("This week", "इस सप्ताह")}</p>
        <h2 className="mt-1 max-w-xl text-2xl font-semibold leading-snug sm:text-3xl">
          {weekly.data !== null ? L(`${weekly.data} students need a follow-up this week.`, `इस सप्ताह ${weekly.data} विद्यार्थियों से बात करनी है।`) : L("Plan this week", "इस सप्ताह की योजना")}
        </h2>
        <Link
          href={next.href}
          data-testid="primary-cta"
          className="mt-5 inline-flex min-h-[48px] items-center gap-2 rounded-xl bg-white px-5 py-3 text-base font-semibold text-brand-dark shadow-soft transition-transform hover:-translate-y-0.5"
        >
          {L(`Next step: ${next.en}`, `अगला कदम: ${next.hi}`)} <ArrowRight size={18} />
        </Link>
      </section>

      <section aria-label={L("Headline numbers", "मुख्य संख्याएँ")} className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="headline-numbers">
        <Card className="card-lift flex items-center gap-3 p-4">
          <IconTile icon={Users} tone="sky" size={44} />
          <div>
            <p className="text-sm text-ink-soft">{L("Students enrolled", "नामांकित विद्यार्थी")}</p>
            <p className="text-2xl font-semibold text-ink"><CountUp value={students} /></p>
          </div>
        </Card>
        <Card className="card-lift flex items-center gap-3 p-4">
          {retained !== null ? (
            <Ring value={retained} size={52} stroke={7} color="#0ca678"><span className="text-xs font-semibold text-teal-ink">{Math.round(retained * 100)}%</span></Ring>
          ) : (
            <IconTile icon={TrendingUp} tone="teal" size={44} />
          )}
          <div>
            <p className="text-sm text-ink-soft">{L("Still enrolled", "अब भी नामांकित")}</p>
            <p className="text-sm font-medium text-ink">{retained !== null ? L(`${dropped} left in ${months.length} months`, `${months.length} माह में ${dropped} छोड़ गए`) : L("Not enough data yet", "अभी पर्याप्त डेटा नहीं")}</p>
          </div>
        </Card>
        <Card className="card-lift flex items-center gap-3 p-4">
          <IconTile icon={HeartHandshake} tone="amber" size={44} />
          <div>
            <p className="text-sm text-ink-soft">{L("On this week's list", "इस सप्ताह की सूची में")}</p>
            <p className="text-2xl font-semibold text-ink">{weekly.data !== null ? <CountUp value={weekly.data} /> : "—"}</p>
          </div>
        </Card>
        <Card className="card-lift flex items-center gap-3 p-4">
          <IconTile icon={TrendingUp} tone="calm" size={44} />
          <div>
            <p className="text-sm text-ink-soft">{L("Return on fees", "फ़ीस पर रिटर्न")}</p>
            <p className="text-lg font-semibold text-ink">{roi ? `${roi.ratio_low}–${roi.ratio_high}×` : "—"}</p>
            <p className="text-xs text-ink-mute">{L("estimate, not yet tested", "अनुमान, अभी परखा नहीं")}</p>
          </div>
        </Card>
      </section>
      {owner.error && !owner.data && <Unavailable what="results" detail={owner.error} status={owner.status} onRetry={owner.reload} />}

      <section aria-label={L("Weekly steps", "साप्ताहिक कदम")}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">{L("This week's checklist", "इस सप्ताह की चेकलिस्ट")}</h2>
          <span className="text-sm text-ink-soft">{done.length}/5 {L("done", "पूरे")}</span>
        </div>
        <ol className="grid gap-3 md:grid-cols-2 lg:grid-cols-3" data-testid="flow">
          {STEPS.map((s, i) => {
            const isDone = done.includes(s.id);
            const isNext = next.id === s.id && !isDone;
            return (
              <li key={s.id} className={cn("relative rounded-2xl border p-4 shadow-soft transition-shadow", s.tone, isNext ? "border-brand ring-2 ring-brand/30" : "border-line")} data-step={s.id} data-next={isNext}>
                {isNext && <span className="absolute -top-2.5 left-4 rounded-full bg-brand px-2.5 py-0.5 text-xs font-semibold text-white">{L("Next", "अगला")}</span>}
                <div className="flex items-start gap-3">
                  <IconTile icon={s.icon} tone="brand" />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-ink">{i + 1}. {L(s.en, s.hi)}</p>
                    <p className="text-sm text-ink-soft">{L(s.den, s.dhi)}</p>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between gap-2">
                  <Link href={s.href} className="inline-flex min-h-[44px] items-center gap-1 rounded-xl bg-white px-4 text-[15px] font-medium text-brand-dark shadow-soft hover:bg-brand-soft">
                    {L("Open", "खोलें")} <ArrowRight size={16} />
                  </Link>
                  <button
                    onClick={() => toggle(s.id)}
                    aria-pressed={isDone}
                    className={cn("inline-flex min-h-[44px] items-center gap-1.5 rounded-xl px-3 text-sm font-medium", isDone ? "bg-teal text-white" : "bg-white/70 text-ink-soft hover:bg-white")}
                  >
                    <Check size={16} /> {isDone ? L("Done", "हो गया") : L("Mark done", "पूरा करें")}
                  </button>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="grid gap-3 sm:grid-cols-2">
        <Link href="/students" className="card-lift flex items-center gap-3 rounded-2xl border border-line bg-tint-student p-4 shadow-soft">
          <IconTile icon={GraduationCap} tone="sky" />
          <span><span className="block font-semibold text-ink">{L("Student page", "विद्यार्थी पेज")}</span><span className="text-sm text-ink-soft">{L("One student's progress and study plan.", "एक विद्यार्थी की प्रगति और पढ़ाई की योजना।")}</span></span>
        </Link>
        <Link href="/parents" className="card-lift flex items-center gap-3 rounded-2xl border border-line bg-tint-parent p-4 shadow-soft">
          <IconTile icon={Smartphone} tone="amber" />
          <span><span className="block font-semibold text-ink">{L("Parent page", "अभिभावक पेज")}</span><span className="text-sm text-ink-soft">{L("The WhatsApp message and the monthly report.", "WhatsApp संदेश और मासिक रिपोर्ट।")}</span></span>
        </Link>
      </section>
    </div>
  );
}
