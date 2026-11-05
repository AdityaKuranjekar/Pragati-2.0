"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { CONCEPTS, FIXTURES, conceptById, itemsFor } from "@/lib/prototype/data";
import { EARLY_EVIDENCE, MASTERED_AT, MIN_EVIDENCE, estimatesFor, nextStepFor } from "@/lib/prototype/engine";
import { f2 } from "@/lib/prototype/format";
import { recordAttempt, useDemoState } from "@/lib/prototype/store";
import type { Estimate, NextStep } from "@/lib/prototype/types";
import { Card, OriginTag, Warn } from "./frame";

type Result = { correct: boolean; conceptLabel: string; correctText: string; before: NextStep | null; after: NextStep | null };

export function LearnerSwitch({ id }: { id: string }) {
  return (
    <div className="p-seg" role="group" aria-label="Learner">
      {FIXTURES.map((l) => (
        <Link key={l.id} href={`/prototype/learner/${l.id}`} aria-current={l.id === id ? "page" : undefined}>{l.label}</Link>
      ))}
    </div>
  );
}

function MasteryRange({ e }: { e: Estimate }) {
  return (
    <div className="p-range" aria-hidden="true">
      <div className="band" style={{ left: `${e.lo * 100}%`, width: `${Math.max(1, (e.hi - e.lo) * 100)}%` }} />
      <div className="tick" style={{ left: `calc(${e.mean * 100}% - 1px)` }} />
    </div>
  );
}

function ConceptCard({ e }: { e: Estimate }) {
  const c = conceptById(e.conceptId);
  return (
    <section className="p-card">
      <h3 className="p-h2" style={{ marginBottom: 8 }}>{c.label}</h3>
      {e.insufficient ? (
        <>
          <p className="p-est num">--</p>
          <p className="num small muted" style={{ marginTop: 4 }}>{e.n} attempt{e.n === 1 ? "" : "s"}</p>
          <p style={{ marginTop: 8 }}><Warn>Insufficient evidence (fewer than {MIN_EVIDENCE} attempts)</Warn></p>
        </>
      ) : (
        <>
          <p className="p-est num">{f2(e.mean)}</p>
          <MasteryRange e={e} />
          <p className="num small muted">Range {f2(e.lo)} to {f2(e.hi)} · {e.n} attempts</p>
          {e.early && <p className="small" style={{ marginTop: 8 }}>Early estimate (fewer than {EARLY_EVIDENCE} attempts)</p>}
        </>
      )}
    </section>
  );
}

export function LearnerView({ id }: { id: string }) {
  const learner = FIXTURES.find((l) => l.id === id)!;
  const { attempts } = useDemoState();
  const est = useMemo(() => estimatesFor(learner, CONCEPTS, attempts), [learner, attempts]);
  const next = useMemo(() => nextStepFor(est, CONCEPTS), [est]);
  const [phase, setPhase] = useState<"idle" | "answering" | "result">("idle");
  const [choice, setChoice] = useState<number | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  const items = next ? itemsFor(next.conceptId) : [];
  const done = next ? attempts.filter((a) => a.learnerId === id && a.conceptId === next.conceptId).length : 0;
  const item = items.length ? items[done % items.length] : null;

  const submit = () => {
    if (!item || choice === null || !next) return;
    const correct = choice === item.answer;
    const probe = { id: "probe", learnerId: id, itemId: item.id, conceptId: item.conceptId, answer: choice, correct };
    const after = nextStepFor(estimatesFor(learner, CONCEPTS, [...attempts, probe]), CONCEPTS);
    recordAttempt({ learnerId: id, itemId: item.id, conceptId: item.conceptId, answer: choice, correct });
    setResult({ correct, conceptLabel: conceptById(item.conceptId).label, correctText: item.options[item.answer], before: next, after });
    setPhase("result");
    setChoice(null);
  };

  const changed = result ? (result.before?.conceptId !== result.after?.conceptId || result.before?.action !== result.after?.action) : false;

  return (
    <div className="p-stack">
      <div className="p-row">
        <LearnerSwitch id={id} />
        <span className="small muted">Fixture learner, starting counts are simulator inputs</span>
      </div>

      <section className="p-card p-next" aria-labelledby="next-h">
        <div className="p-card-head">
          <span className="small muted" id="next-h">Next step</span>
          <OriginTag origin="DEMO FIXTURE" />
        </div>
        {next ? (
          <>
            <h2>{next.title}</h2>
            <dl className="p-kv">
              <div><dt>Reason</dt><dd>{next.reason}</dd></div>
              <div>
                <dt>Evidence used</dt>
                <dd className="num">{next.evidence.map((e) => `${e.attempts} attempt${e.attempts === 1 ? "" : "s"} on ${e.label}`).join(" · ")}</dd>
              </div>
              <div><dt>Policy version</dt><dd>{next.policyVersion}</dd></div>
            </dl>
            {phase === "idle" && (
              <button type="button" className="p-btn primary" onClick={() => setPhase("answering")}>Start practice</button>
            )}
          </>
        ) : (
          <>
            <h2>No next step</h2>
            <p>Every concept in this chain has at least {MIN_EVIDENCE} attempts and an estimate of {f2(MASTERED_AT)} or above.</p>
          </>
        )}
      </section>

      {(phase === "answering" || phase === "result") && (
        <Card title="Practice" origin="DEMO FIXTURE">
          <p className="small muted" style={{ marginBottom: 8 }}>Demo items written for this interface. They are not reviewed content.</p>
          {phase === "answering" && item && (
            <>
              <p className="small muted num">{conceptById(item.conceptId).label} · item {(done % items.length) + 1} of {items.length}</p>
              <fieldset className="p-opts">
                <legend style={{ fontWeight: 500, marginBottom: 8 }}>{item.stem}</legend>
                {item.options.map((o, i) => (
                  <label key={i}>
                    <input type="radio" name="answer" checked={choice === i} onChange={() => setChoice(i)} />
                    <span><span className="muted">{String.fromCharCode(65 + i)}.</span> {o}</span>
                  </label>
                ))}
              </fieldset>
              <button type="button" className="p-btn primary" disabled={choice === null} onClick={submit}>Submit answer</button>
            </>
          )}
          {phase === "result" && result && (
            <div aria-live="polite" className="p-stack" style={{ gap: 12 }}>
              <p><strong>{result.correct ? "Correct." : `Incorrect. Correct answer: ${result.correctText}.`}</strong> Recorded as 1 attempt on {result.conceptLabel}.</p>
              <p>
                {changed
                  ? `Next step changed to: ${result.after ? result.after.title : "no next step"}.`
                  : "Next step unchanged."}
                {" "}{result.after ? result.after.reason : ""}
              </p>
              <div>
                {result.after ? (
                  <button type="button" className="p-btn primary" onClick={() => setPhase("answering")}>Next question</button>
                ) : (
                  <button type="button" className="p-btn" onClick={() => setPhase("idle")}>Close</button>
                )}
              </div>
            </div>
          )}
        </Card>
      )}

      <div>
        <h2 className="p-h2" style={{ marginBottom: 12 }}>Concepts <OriginTag origin="DEMO FIXTURE" /></h2>
        <div className="p-cards">{est.map((e) => <ConceptCard key={e.conceptId} e={e} />)}</div>
      </div>
    </div>
  );
}
