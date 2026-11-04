"use client";

import { Check, Loader2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useApp, type Lang } from "@/lib/app-context";
import { ApiError } from "@/lib/http";
import { generateReport, type GeneratedReport } from "@/lib/reports-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardTitle, Note } from "./ui";

const REASON: Record<string, [string, string]> = {
  local_model_not_running: ["The local language model is not running, so the safe template was used.", "स्थानीय भाषा-मॉडल चालू नहीं है, इसलिए सुरक्षित टेम्पलेट इस्तेमाल हुआ।"],
  model_failed_verification: ["The model's text failed a check, so the safe template was used.", "मॉडल का पाठ एक जाँच में विफल रहा, इसलिए सुरक्षित टेम्पलेट इस्तेमाल हुआ।"],
};

/** Generate a Hindi or English monthly report. Shows what the verifier checked and whether the template fallback was used. */
export function ReportGenerator({ studentId }: { studentId: string }) {
  const { L, lang } = useApp();
  const [language, setLanguage] = useState<Lang>(lang);
  const [useLlm, setUseLlm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState<GeneratedReport | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      setR(await generateReport(studentId, language, useLlm));
    } catch (e) {
      setR(null);
      setErr(e instanceof ApiError ? (e.status === 0 ? L("Cannot reach the server. No report was made.", "सर्वर तक नहीं पहुँच सके। कोई रिपोर्ट नहीं बनी।") : e.message) : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const passed = r ? r.checks.filter((c) => c.passed).length : 0;
  return (
    <Card>
      <CardTitle>{L("Monthly report", "मासिक रिपोर्ट")}</CardTitle>
      <div className="flex flex-wrap items-center gap-3">
        <div role="radiogroup" aria-label={L("Report language", "रिपोर्ट की भाषा")} className="flex rounded-xl border border-line p-0.5 text-sm">
          {(["en", "hi"] as const).map((l) => (
            <button key={l} role="radio" aria-checked={language === l} onClick={() => setLanguage(l)} className={cn("rounded-lg px-3 py-1 font-medium", language === l ? "bg-brand text-white" : "text-ink-soft")}>
              {l === "en" ? "English" : "हिन्दी"}
            </button>
          ))}
        </div>
        <Button onClick={run} disabled={busy} data-testid="make-report">
          {busy && <Loader2 size={14} className="animate-spin motion-reduce:animate-none" />}
          {busy ? L("Writing and checking…", "लिख रहे हैं और जाँच रहे हैं…") : L("Generate report", "रिपोर्ट बनाएँ")}
        </Button>
        <label className="inline-flex items-center gap-2 text-xs text-ink-soft">
          <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
          {L("Try the local language model first", "पहले स्थानीय भाषा-मॉडल आज़माएँ")}
        </label>
      </div>
      {err && <p role="alert" className="mt-3 rounded-xl bg-amber-soft px-3 py-2 text-sm text-[#8a5200]">{err}</p>}

      {r && (
        <div className="mt-4 space-y-3" data-testid="report-result" aria-live="polite">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={r.verified ? "teal" : "amber"} data-testid="verified-badge">
              <ShieldCheck size={12} /> {r.verified ? L(`${passed} of ${r.checks.length} checks passed`, `${r.checks.length} में से ${passed} जाँच सफल`) : L("Held back for a person to read", "किसी व्यक्ति के पढ़ने के लिए रोका गया")}
            </Badge>
            <Badge tone={r.source === "template" ? "calm" : "brand"} data-testid="source-badge">
              {r.source === "template" ? L("Written from a template", "टेम्पलेट से लिखा गया") : L("Written by the local model", "स्थानीय मॉडल ने लिखा")}
            </Badge>
            {r.latency_ms != null && <span className="text-xs text-ink-mute">{(r.latency_ms / 1000).toFixed(1)} s</span>}
          </div>
          {r.fallback_used && (
            <div data-testid="fallback-note">
              <Note tone="calm">{REASON[r.fallback_reason ?? ""] ? L(...REASON[r.fallback_reason ?? ""]) : L("The local language model is not available, so the safe template was used.", "स्थानीय भाषा-मॉडल उपलब्ध नहीं है, इसलिए सुरक्षित टेम्पलेट इस्तेमाल हुआ।")}</Note>
            </div>
          )}
          {r.verified ? (
            <p className="whitespace-pre-line rounded-2xl bg-bg p-4 text-sm leading-relaxed text-ink" lang={r.language} data-testid="report-body">
              {r.body}
            </p>
          ) : (
            <Note>{L("A check did not pass, so this text is not shown to parents. A teacher can read it first.", "एक जाँच सफल नहीं हुई, इसलिए यह पाठ अभिभावकों को नहीं दिखाया जाता। पहले शिक्षक इसे पढ़ सकते हैं।")}</Note>
          )}
          {r.language === "hi" && r.hi_reviewed === false && <Note>{L("Hindi text is pending review by a native speaker.", "हिंदी पाठ की मूल-भाषी समीक्षा बाकी है।")}</Note>}
          <details className="text-sm">
            <summary className="cursor-pointer text-ink-soft">{L("What was checked", "क्या जाँचा गया")}</summary>
            <ul className="mt-2 space-y-1" data-testid="check-list">
              {r.checks.map((c) => (
                <li key={c.id} className="flex items-center gap-2 text-sm">
                  <span className={cn("grid h-4 w-4 place-items-center rounded-full", c.passed ? "bg-teal-soft text-[#087f5b]" : "bg-amber-soft text-[#8a5200]")}>{c.passed ? <Check size={11} /> : "!"}</span>
                  {c.label ?? c.id}
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </Card>
  );
}
