"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, Card, CardTitle, Empty, Select, Unavailable } from "@/components/ui";
import { useApp } from "@/lib/app-context";
import { ApiError } from "@/lib/http";
import { fixKey, getFlagged, getTests, type Flagged } from "@/lib/teacher-api";
import { pct } from "@/lib/utils";

type Load<T> = { data: T | null; error: ApiError | null; loading: boolean };

export function FlaggedPanel({ batchId }: { batchId: string }) {
  const { L } = useApp();
  const [tests, setTests] = useState<Load<{ test_id: string; name: string; date?: string }[]>>({ data: null, error: null, loading: true });
  const [testId, setTestId] = useState("");
  const [flagged, setFlagged] = useState<Load<Flagged[]>>({ data: null, error: null, loading: false });
  const [keys, setKeys] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    setTests({ data: null, error: null, loading: true });
    setTestId("");
    getTests(batchId)
      .then((r) => {
        if (!alive) return;
        setTests({ data: r.tests, error: null, loading: false });
        setTestId(r.tests[r.tests.length - 1]?.test_id ?? "");
      })
      .catch((e: ApiError) => alive && setTests({ data: null, error: e, loading: false }));
    return () => {
      alive = false;
    };
  }, [batchId, tick]);

  useEffect(() => {
    if (!testId) return;
    let alive = true;
    setFlagged((f) => ({ ...f, loading: true }));
    setMsg(null);
    setErr(null);
    getFlagged(testId)
      .then((r) => alive && setFlagged({ data: r.flagged, error: null, loading: false }))
      .catch((e: ApiError) => alive && setFlagged({ data: null, error: e, loading: false }));
    return () => {
      alive = false;
    };
  }, [testId]);

  const apply = async (f: Flagged) => {
    const key = (keys[f.question_no] ?? f.suggested_key).toUpperCase();
    setBusy(f.question_no);
    setErr(null);
    setMsg(null);
    try {
      const r = await fixKey(testId, f.question_no, key);
      setFlagged({ data: r.flagged, error: null, loading: false });
      setMsg(L(`Question ${r.question_no}: key is now ${r.key}. ${r.rescored_students} students re-scored.`, `प्रश्न ${r.question_no}: कुंजी अब ${r.key} है। ${r.rescored_students} विद्यार्थियों का दोबारा अंकन हुआ।`));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const editable = true;
  return (
    <Card>
      <CardTitle right={tests.data && tests.data.length > 0 ? <Select label={L("Test", "टेस्ट")} value={testId} onChange={setTestId} options={tests.data.map((t) => ({ value: t.test_id, label: `${t.name}${t.date ? ` · ${t.date}` : ""}` }))} /> : undefined}>
        {L("Answer-key check", "उत्तर-कुंजी जाँच")}
      </CardTitle>
      {tests.loading ? (
        <p className="text-sm text-ink-mute" aria-busy="true">{L("Loading tests…", "टेस्ट लोड हो रहे हैं…")}</p>
      ) : tests.error ? (
        <Unavailable what="tests" detail={tests.error.message} status={tests.error.status} onRetry={() => setTick((t) => t + 1)} />
      ) : tests.data?.length === 0 ? (
        <Empty>{L("No tests have been uploaded for this batch yet.", "इस बैच के लिए अभी कोई टेस्ट अपलोड नहीं हुआ।")}</Empty>
      ) : flagged.loading && !flagged.data ? (
        <p className="text-sm text-ink-mute" aria-busy="true">{L("Checking answer keys…", "उत्तर-कुंजी जाँची जा रही है…")}</p>
      ) : flagged.error ? (
        <Unavailable what="flagged questions" detail={flagged.error.message} status={flagged.error.status} />
      ) : (flagged.data ?? []).length === 0 ? (
        <Empty>{L("No suspicious answer keys on this test.", "इस टेस्ट में कोई संदिग्ध उत्तर-कुंजी नहीं।")}</Empty>
      ) : (
        <ul className="space-y-3" data-testid="flagged-list">
          {flagged.data!.map((f) => (
            <li key={f.question_no} className="rounded-xl border border-line p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-ink">
                  {L("Question", "प्रश्न")} {f.question_no}
                  {f.subject ? ` · ${f.subject}` : ""}
                </span>
                {f.status === "fixed" ? <Badge tone="teal">{L("Key fixed", "कुंजी ठीक की गई")}</Badge> : <Badge tone="amber">{L("Please check", "कृपया जाँचें")}</Badge>}
              </div>
              <p className="mt-1 text-sm text-ink-soft">
                {L(
                  `Key says ${f.current_key}. ${pct(f.share_top_group_chose_suggested ?? 0)} of the strongest students chose ${f.suggested_key}, ${pct(f.share_chose_current_key ?? 0)} chose ${f.current_key}. ${f.n_students ?? "?"} students.`,
                  `कुंजी में ${f.current_key} है। सबसे मज़बूत विद्यार्थियों में से ${pct(f.share_top_group_chose_suggested ?? 0)} ने ${f.suggested_key} चुना, ${pct(f.share_chose_current_key ?? 0)} ने ${f.current_key}। ${f.n_students ?? "?"} विद्यार्थी।`
                )}
              </p>
              {f.status === "open" && editable && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <label className="text-xs text-ink-soft" htmlFor={`k${f.question_no}`}>{L("New key", "नई कुंजी")}</label>
                  <select
                    id={`k${f.question_no}`}
                    value={keys[f.question_no] ?? f.suggested_key}
                    onChange={(e) => setKeys((k) => ({ ...k, [f.question_no]: e.target.value }))}
                    className="rounded-xl border border-line bg-white px-2 py-1.5 text-sm"
                  >
                    {["A", "B", "C", "D"].map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                  <Button variant="soft" disabled={busy !== null} onClick={() => void apply(f)} data-testid={`fix-key-${f.question_no}`}>
                    {busy === f.question_no && <Loader2 size={14} className="animate-spin motion-reduce:animate-none" />}
                    {L("Fix key and re-score", "कुंजी ठीक करें और दोबारा अंकन करें")}
                  </Button>
                </div>
              )}
              {f.status === "open" && !editable && <p className="mt-2 text-xs text-ink-mute">{L("Only the owner or a teacher can change a key.", "केवल मालिक या शिक्षक कुंजी बदल सकते हैं।")}</p>}
            </li>
          ))}
        </ul>
      )}
      {msg && <p role="status" className="mt-3 rounded-xl bg-teal-soft px-3 py-2 text-sm text-[#087f5b]">{msg}</p>}
      {err && <p role="alert" className="mt-3 rounded-xl bg-amber-soft px-3 py-2 text-sm text-[#8a5200]">{err}</p>}
    </Card>
  );
}
