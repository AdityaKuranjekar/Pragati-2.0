"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { CONCEPTS, FIXTURES, conceptById, itemsFor } from "@/lib/prototype/data";
import { EARLY_EVIDENCE, MASTERED_AT, MIN_EVIDENCE, estimatesFor, nextStepFor } from "@/lib/prototype/engine";
import { f2 } from "@/lib/prototype/format";
import { NO_ESTIMATE_LONG, STEP_WORD } from "@/lib/prototype/mastery-scale";
import { recordAttempt, useDemoState } from "@/lib/prototype/store";
import type { Estimate, NextStep } from "@/lib/prototype/types";
import { Card, OriginTag } from "./frame";

type Result = { correct: boolean; conceptLabel: string; correctText: string; before: NextStep | null; after: NextStep | null };
const plural = (n: number, one: string) => `${n} ${n === 1 ? one : `${one}s`}`;

export function LearnerSwitch({ id }: { id: string }) {
  return (
    <div className="p-seg" role="group" aria-label="Learner">
      {FIXTURES.map((l) => (
        <Link key={l.id} href={`/prototype/learner/${l.id}`} aria-current={l.id === id ? "page" : undefined}>{l.label}</Link>
      ))}
    </div>
  );
}

function Level({ e }: { e: Estimate }) {
  const on = e.insufficient ? 0 : e.step;
  return (
    <span className="p-level" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((i) => <i key={i} className={i <= on ? "on" : ""} />)}
    </span>
  );
}

function ConceptCard({ e }: { e: Estimate }) {
  const c = conceptById(e.conceptId);
  return (
    <section className="p-card">
      <h3 className="p-h2" style={{ marginBottom: 10 }}>{c.label}</h3>
      {e.insufficient ? (
        <>
          <p className="p-est" style={{ fontSize: 20 }}>{NO_ESTIMATE_LONG}</p>
          <p className="muted" style={{ marginTop: 6 }}>{plural(e.n, "question")} answered so far. At least {MIN_EVIDENCE} are needed.</p>
        </>
      ) : (
        <>
          <p className="p-est" style={{ fontSize: 22 }}>{STEP_WORD[e.step]}</p>
          <p style={{ margin: "8px 0" }}><Level e={e} /></p>
          <p className="muted num">{e.k} of {e.n} answers correct.{e.early ? " This rests on few questions, so it may change." : ""}</p>
          <details className="p-more">
            <summary>Show the numbers</summary>
            <dl className="p-detail">
              <div><dt>Estimate</dt><dd className="num">{f2(e.mean)}</dd></div>
              <div><dt>Likely range (80%)</dt><dd className="num">{f2(e.lo)} to {f2(e.hi)}</dd></div>
            </dl>
          </details>
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

  const changed = result ? result.before?.conceptId !== result.after?.conceptId || result.before?.action !== result.after?.action : false;

  return (
    <div className="p-stack">
      <div className="p-row">
        <LearnerSwitch id={id} />
        <span className="small muted">A demo learner, with made-up answers so far</span>
      </div>

      <section className="p-card p-next" aria-labelledby="next-h">
        <div className="p-card-head">
          <span className="small muted" id="next-h">What to do next</span>
          <OriginTag origin="DEMO FIXTURE" />
        </div>
        {next ? (
          <>
            <h2>{next.title}</h2>
            <dl className="p-kv">
              <div><dt>Why</dt><dd>{next.reason}</dd></div>
              <div>
                <dt>Based on</dt>
                <dd className="num">{next.evidence.map((e) => `${plural(e.attempts, "question")} answered on ${e.label}`).join(" · ")}</dd>
              </div>
            </dl>
            {phase === "idle" && (
              <button type="button" className="p-btn primary" onClick={() => setPhase("answering")}>Start practice</button>
            )}
            <details className="p-more">
              <summary>How this was decided</summary>
              <p className="muted" style={{ maxWidth: "70ch" }}>{next.rule} <span className="num">(Rule version {next.policyVersion}.)</span></p>
            </details>
          </>
        ) : (
          <>
            <h2>Nothing more to practise in this chain</h2>
            <p>Every topic has at least {MIN_EVIDENCE} questions answered and an estimate of {f2(MASTERED_AT)} or higher.</p>
          </>
        )}
      </section>

      {(phase === "answering" || phase === "result") && (
        <Card title="Practice" origin="DEMO FIXTURE">
          <p className="small muted" style={{ marginBottom: 8 }}>These are demo questions written for this prototype. They have not been reviewed.</p>
          {phase === "answering" && item && (
            <>
              <p className="small muted num">{conceptById(item.conceptId).label} · question {(done % items.length) + 1} of {items.length}</p>
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
              <p><strong>{result.correct ? "Correct." : `Not correct. The answer is ${result.correctText}.`}</strong> Saved as one more answer on {result.conceptLabel}.</p>
              <p>
                {result.after
                  ? changed
                    ? `The next step has changed: ${result.after.title}. ${result.after.reason}`
                    : `The next step stays the same. ${result.after.reason}`
                  : "There is nothing more to practise in this chain."}
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
        <h2 className="p-h2" style={{ marginBottom: 12 }}>How each topic is going <OriginTag origin="DEMO FIXTURE" /></h2>
        <div className="p-cards">{est.map((e) => <ConceptCard key={e.conceptId} e={e} />)}</div>
      </div>
    </div>
  );
}
