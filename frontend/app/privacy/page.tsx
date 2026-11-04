"use client";

import { Loader2, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, CardTitle, Empty, Note, Origin, PageHead, PageSkeleton, Unavailable } from "@/components/ui";
import { useApp } from "@/lib/app-context";
import { ApiError } from "@/lib/http";
import { addConsent, getConsents, getTier, putTier, withdrawConsent, type Consent, type Tier } from "@/lib/privacy-api";
import { cn, pct } from "@/lib/utils";

const PAGE = 10;
const errText = (e: unknown) => (e instanceof ApiError ? e.message : (e as Error).message);

function TierCard() {
  const { L } = useApp();
  const [tier, setTier] = useState<Tier | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [choice, setChoice] = useState<Tier["tier"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    getTier().then(setTier).catch((e: ApiError) => setError(e));
  }, []);
  useEffect(load, [load]);

  if (error) return <Unavailable what="privacy tier" detail={error.message} status={error.status} onRetry={load} />;
  if (!tier) return <p className="text-sm text-ink-mute" aria-busy="true">{L("Loading…", "लोड हो रहा है…")}</p>;

  const cur = tier.options.find((o) => o.tier === tier.tier)!;
  const pick = choice ?? tier.tier;
  const next = tier.options.find((o) => o.tier === pick)!;
  const owner = true;
  const apply = async () => {
    setBusy(true);
    setErr(null);
    setResult(null);
    const before = tier.list_size;
    try {
      const t = await putTier(pick);
      setTier(t);
      setChoice(null);
      setResult(L(`Switched. The weekly support list went from ${before} to ${t.list_size} students.`, `बदल दिया गया। साप्ताहिक सहयोग सूची ${before} से ${t.list_size} विद्यार्थियों की हो गई।`));
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };
  const fmt = (v: number | null, p = false) => (v === null ? "—" : p ? pct(v) : v.toFixed(3));

  return (
    <Card>
      <CardTitle right={<Origin origin={tier.origin} />}>{L("What the early-warning model may use", "अर्ली-वार्निंग मॉडल क्या इस्तेमाल कर सकता है")}</CardTitle>
      <div role="radiogroup" aria-label={L("Privacy tier", "गोपनीयता स्तर")} className="grid gap-2 sm:grid-cols-2">
        {tier.options.map((o) => (
          <label key={o.tier} className={cn("cursor-pointer rounded-xl border p-3 text-sm focus-within:outline focus-within:outline-2 focus-within:outline-brand", pick === o.tier ? "border-brand bg-brand-soft" : "border-line bg-white hover:bg-bg")}>
            <input type="radio" name="tier" className="sr-only" checked={pick === o.tier} disabled={!owner} onChange={() => { setChoice(o.tier); setResult(null); }} />
            <span className="flex items-center justify-between gap-2">
              <span className="font-medium text-ink">{L(o.label_en, o.label_hi ?? o.label_en)}</span>
              {tier.tier === o.tier && <Badge tone="teal">{L("Now", "अभी")}</Badge>}
            </span>
          </label>
        ))}
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[420px] text-left text-sm" data-testid="tier-table">
          <thead className="text-xs text-ink-mute">
            <tr>
              <th className="py-1 pr-3 font-medium">{L("Accuracy (synthetic test cohort)", "सटीकता (कृत्रिम टेस्ट समूह)")}</th>
              <th className="py-1 pr-3 font-medium">{L("Full", "पूर्ण")}</th>
              <th className="py-1 pr-3 font-medium">{L("Academic only", "केवल शैक्षिक")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {([["auc", "How well it separates (AUC)", "अलग पहचानने की क्षमता (AUC)", false], ["precision", "Of those listed, share who really needed help", "सूची में से जिन्हें सच में मदद चाहिए थी", true], ["recall", "Share of all who needed help that we caught", "मदद चाहने वालों में से जितनों को पकड़ा", true], ["lead_time_days", "Days of warning (average)", "चेतावनी के दिन (औसत)", false]] as const).map(([k, en, hi, isPct]) => (
              <tr key={k}>
                <td className="py-2 pr-3 text-ink-soft">{L(en, hi)}</td>
                {tier.options.map((o) => (
                  <td key={o.tier} className={cn("py-2 pr-3 tabular-nums", o.tier === pick && "font-semibold text-ink")}>
                    {k === "lead_time_days" ? (o.metrics.lead_time_days === null ? "—" : o.metrics.lead_time_days.toFixed(1)) : fmt(o.metrics[k], isPct)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pick !== tier.tier && (
        <div className="mt-3" data-testid="tier-cost">
          <Note>
            {pick === "academic_only" ? (
              <>
                <b>{L("The honest cost of going academic-only:", "केवल शैक्षिक पर जाने की ईमानदार कीमत:")}</b>{" "}
                {L(
                  `of the students listed, ${fmt(next.metrics.precision, true)} instead of ${fmt(cur.metrics.precision, true)} really needed help, and we would catch ${fmt(next.metrics.recall, true)} instead of ${fmt(cur.metrics.recall, true)} of those who do. The list would still be sized to mentor capacity (${tier.capacity_per_week ?? "?"}/week), so more of it would be false alarms.`,
                  `सूची के विद्यार्थियों में से ${fmt(next.metrics.precision, true)} (पहले ${fmt(cur.metrics.precision, true)}) को सच में मदद चाहिए, और मदद चाहने वालों में से ${fmt(next.metrics.recall, true)} (पहले ${fmt(cur.metrics.recall, true)}) पकड़े जाएँगे। सूची फिर भी मेंटर क्षमता (${tier.capacity_per_week ?? "?"}/सप्ताह) जितनी रहेगी, इसलिए उसमें गलत चेतावनियाँ ज़्यादा होंगी।`
                )}
              </>
            ) : (
              L("Full uses attendance and engagement for adults who gave their own consent. Students under 18 stay on the academic track either way.", "पूर्ण स्तर उन वयस्कों की उपस्थिति और सक्रियता इस्तेमाल करता है जिन्होंने स्वयं सहमति दी। 18 से कम उम्र के विद्यार्थी दोनों स्थितियों में शैक्षिक ट्रैक पर रहते हैं।")
            )}
          </Note>
        </div>
      )}
      <p className="mt-3 flex items-start gap-1.5 text-xs text-ink-soft">
        <ShieldCheck size={14} className="mt-0.5 shrink-0" />
        {L("Students under 18 are always on the academic-support track (tests only), whatever this switch says. Their attendance and engagement are never used by the model.", "18 से कम उम्र के विद्यार्थी इस स्विच की परवाह किए बिना हमेशा शैक्षिक-सहयोग ट्रैक (केवल टेस्ट) पर रहते हैं। उनकी उपस्थिति और सक्रियता मॉडल कभी इस्तेमाल नहीं करता।")}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button onClick={apply} disabled={!owner || busy || pick === tier.tier} data-testid="apply-tier">
          {busy && <Loader2 size={14} className="animate-spin motion-reduce:animate-none" />}
          {L("Apply this setting", "यह सेटिंग लागू करें")}
        </Button>
        
      </div>
      {result && <p role="status" data-testid="tier-result" className="mt-3 rounded-xl bg-teal-soft px-3 py-2 text-sm text-[#087f5b]">{result}</p>}
      {err && <p role="alert" className="mt-3 rounded-xl bg-amber-soft px-3 py-2 text-sm text-[#8a5200]">{err}</p>}
      <p className="mt-3 text-xs text-ink-mute">{L("Numbers come from the synthetic 2026 test cohort (3 snapshots, 45-day horizon, capacity 5% of active students). A real pilot settles the true values.", "आँकड़े कृत्रिम 2026 टेस्ट समूह के हैं (3 स्नैपशॉट, 45 दिन की अवधि, क्षमता सक्रिय विद्यार्थियों का 5%)। असली मान पायलट से तय होंगे।")}</p>
    </Card>
  );
}

function Ledger() {
  const { L } = useApp();
  const owner = true;
  const [q, setQ] = useState("");
  const [data, setData] = useState<{ items: Consent[]; summary: { total: number; active: number; withdrawn: number } } | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [page, setPage] = useState(0);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [roll, setRoll] = useState("");
  const [guardian, setGuardian] = useState("");
  const [method, setMethod] = useState("in_person_id_check");

  const load = useCallback(() => {
    setError(null);
    getConsents(q).then((d) => setData(d)).catch((e: ApiError) => setError(e));
  }, [q]);
  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  const run = async (fn: () => Promise<string>) => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      setMsg(await fn());
      load();
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };

  if (error) return <Unavailable what="consents" detail={error.message} status={error.status} onRetry={load} />;
  if (!data) return <p className="text-sm text-ink-mute" aria-busy="true">{L("Loading…", "लोड हो रहा है…")}</p>;
  const pages = Math.max(1, Math.ceil(data.items.length / PAGE));
  const sp = Math.min(page, pages - 1);
  const rows = data.items.slice(sp * PAGE, sp * PAGE + PAGE);

  return (
    <Card>
      <CardTitle right={<Badge tone="calm">{data.summary.active} {L("active", "सक्रिय")} · {data.summary.withdrawn} {L("withdrawn", "वापस")}</Badge>}>{L("Parent consent ledger", "अभिभावक सहमति बही")}</CardTitle>
      <p className="mb-3 text-sm text-ink-soft">{L("Every student under 18 needs a verified parent or guardian consent. Withdrawing it stops all processing for that student at once.", "18 से कम उम्र के हर विद्यार्थी के लिए सत्यापित अभिभावक सहमति ज़रूरी है। उसे वापस लेने पर उस विद्यार्थी की सारी प्रोसेसिंग तुरंत रुक जाती है।")}</p>
      <label className="mb-3 block">
        <span className="sr-only">{L("Search by roll number or guardian", "रोल नंबर या अभिभावक से खोजें")}</span>
        <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} placeholder={L("Search roll number or guardian", "रोल नंबर या अभिभावक खोजें")} className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm sm:w-72" />
      </label>
      {rows.length === 0 ? (
        <Empty>{L("No consent records match.", "कोई सहमति रिकॉर्ड नहीं मिला।")}</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm" data-testid="consent-table">
            <thead className="text-xs text-ink-mute">
              <tr>
                <th className="py-1 pr-3 font-medium">{L("Roll", "रोल")}</th>
                <th className="py-1 pr-3 font-medium">{L("Guardian", "अभिभावक")}</th>
                <th className="py-1 pr-3 font-medium">{L("How verified", "कैसे सत्यापित")}</th>
                <th className="py-1 pr-3 font-medium">{L("Date", "तिथि")}</th>
                <th className="py-1 font-medium">{L("Status", "स्थिति")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((c) => (
                <tr key={c.consent_id} data-status={c.status}>
                  <td className="py-2 pr-3 font-medium text-brand-dark">{c.roll_no || "—"}</td>
                  <td className="py-2 pr-3">{c.guardian_display}</td>
                  <td className="py-2 pr-3 text-ink-soft">{c.method === "digilocker" ? "DigiLocker" : L("In person, ID checked", "व्यक्तिगत रूप से, ID जाँची")}</td>
                  <td className="py-2 pr-3 tabular-nums text-ink-soft">{c.date}</td>
                  <td className="py-2">
                    {c.status === "withdrawn" ? (
                      <Badge tone="calm">{L("Withdrawn · processing halted", "वापस · प्रोसेसिंग बंद")}</Badge>
                    ) : confirmId === c.consent_id ? (
                      <span className="inline-flex items-center gap-1">
                        <Button variant="soft" className="px-2.5 py-1" disabled={busy} onClick={() => { setConfirmId(null); void run(async () => (await withdrawConsent(c.consent_id)).effect); }} data-testid="confirm-withdraw">
                          {L("Yes, withdraw", "हाँ, वापस लें")}
                        </Button>
                        <Button variant="ghost" className="px-2 py-1" onClick={() => setConfirmId(null)}>{L("No", "नहीं")}</Button>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        <Badge tone="teal">{L("Active", "सक्रिय")}</Badge>
                        {owner && (
                          <button onClick={() => setConfirmId(c.consent_id)} className="text-xs text-brand-dark underline-offset-2 hover:underline" data-testid="withdraw">
                            {L("Withdraw", "वापस लें")}
                          </button>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <div className="mt-3 flex items-center justify-between text-sm">
          <Button variant="ghost" disabled={sp === 0} onClick={() => setPage(sp - 1)}>{L("Previous", "पिछला")}</Button>
          <span className="text-ink-mute">{sp + 1} / {pages}</span>
          <Button variant="ghost" disabled={sp >= pages - 1} onClick={() => setPage(sp + 1)}>{L("Next", "अगला")}</Button>
        </div>
      )}
      {msg && <p role="status" data-testid="consent-msg" className="mt-3 rounded-xl bg-teal-soft px-3 py-2 text-sm text-[#087f5b]">{msg}</p>}
      {err && <p role="alert" className="mt-3 rounded-xl bg-amber-soft px-3 py-2 text-sm text-[#8a5200]">{err}</p>}

      {owner && (
        <form
          className="mt-5 border-t border-line pt-4"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              const c = await addConsent(roll.trim(), guardian.trim(), method);
              setRoll("");
              setGuardian("");
              return L(`Consent recorded for ${c.roll_no}.`, `${c.roll_no} के लिए सहमति दर्ज हुई।`);
            });
          }}
        >
          <p className="mb-2 text-sm font-medium">{L("Record a new consent", "नई सहमति दर्ज करें")}</p>
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs text-ink-soft">
              {L("Roll number", "रोल नंबर")}
              <input value={roll} onChange={(e) => setRoll(e.target.value)} className="mt-1 block w-36 rounded-xl border border-line bg-white px-3 py-2 text-sm text-ink" />
            </label>
            <label className="text-xs text-ink-soft">
              {L("Guardian name", "अभिभावक का नाम")}
              <input value={guardian} onChange={(e) => setGuardian(e.target.value)} className="mt-1 block w-48 rounded-xl border border-line bg-white px-3 py-2 text-sm text-ink" />
            </label>
            <label className="text-xs text-ink-soft">
              {L("Verified by", "सत्यापन")}
              <select value={method} onChange={(e) => setMethod(e.target.value)} className="mt-1 block rounded-xl border border-line bg-white px-3 py-2 text-sm text-ink">
                <option value="in_person_id_check">{L("In person, ID checked", "व्यक्तिगत रूप से, ID जाँची")}</option>
                <option value="digilocker">DigiLocker</option>
              </select>
            </label>
            <Button type="submit" disabled={busy || !roll.trim() || !guardian.trim()}>{L("Record consent", "सहमति दर्ज करें")}</Button>
          </div>
        </form>
      )}
    </Card>
  );
}

export default function PrivacyPage() {
  const { L } = useApp();
  return (
    <div className="space-y-6">
      <PageHead sub={L("Who has agreed, and what the early-warning model is allowed to see.", "किसने सहमति दी है और अर्ली-वार्निंग मॉडल क्या देख सकता है।")} />
      <TierCard />
      <Ledger />
    </div>
  );
}
