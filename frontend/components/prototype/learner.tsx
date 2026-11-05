"use client";
import Link from "next/link";
import { useState } from "react";
import { ProtoError, getConfig, getNextStep, getState, newEventId, postAttempt } from "@/lib/prototype/client";
import { ACTION_LABEL, BAND_LABEL, STEP_LABEL, conceptName, f2 } from "@/lib/prototype/labels";
import type { ConceptState, LearnerState, NextStep, Origin } from "@/lib/prototype/schemas";
import { useResource } from "@/lib/prototype/useResource";
import { Card, Empty, ErrorState, Loading, OriginTag, PageHead, Warn } from "./common";

/** The one primary action, built only from fields the next-step response carries. */
export function primaryAction(step: NextStep): string {
  const rec = step.recommendation;
  if (step.kind === "recheck") return `${STEP_LABEL.recheck}: ${conceptName(step.concept_id ?? "")}`;
  if (rec) {
    const label = ACTION_LABEL[rec.action] ?? rec.action;
    const cid = rec.concept_id ?? step.concept_id;
    return cid ? `${label}: ${conceptName(cid)}` : label;
  }
  return step.concept_id ? `${STEP_LABEL[step.kind] ?? step.kind}: ${conceptName(step.concept_id)}` : "Nothing to do now";
}

export function NextStepCard({ step, origin }: { step: NextStep; origin: Origin }) {
  const rec = step.recommendation;
  const chain = rec?.trace.chain ?? [];
  return (
    <Card title="Next step" origins={[origin]} className="p-next">
      <p className="p-action" data-testid="primary-action">{primaryAction(step)}</p>
      <div>
        <h3 className="p-h3">Reason</h3>
        <p data-testid="reason">{rec ? rec.reason : step.reason}</p>
        {rec && step.reason !== rec.reason ? <p className="muted" data-testid="item-status">{step.reason}</p> : null}
      </div>
      <div>
        <h3 className="p-h3">Evidence used</h3>
        {chain.length === 0 ? <p className="muted">No evidence listed for this step.</p> : (
          <ul data-testid="evidence">
            {chain.map((c) => {
              const n = rec!.trace.n[c] ?? 0;
              return <li key={c} className="num">{conceptName(c)}: {n} {n === 1 ? "answer" : "answers"}</li>;
            })}
          </ul>
        )}
      </div>
      <p className="label" data-testid="policy">Policy version: {step.policy_version}</p>
    </Card>
  );
}

export function ConceptCards({ state, origin }: { state: LearnerState; origin: Origin }) {
  return (
    <section aria-label="Concepts">
      <div className="p-card-head" style={{ marginBottom: 8 }}>
        <h2 className="p-h2">Concepts</h2><OriginTag origin={origin} />
      </div>
      <div className="p-cards">
        {state.concepts.map((c) => <ConceptCard key={c.concept_id} c={c} />)}
      </div>
      <p className="label" style={{ marginTop: 8 }}>{state.uncertainty_note}. Policy version: {state.policy_version}.</p>
    </section>
  );
}

export function ConceptCard({ c }: { c: ConceptState }) {
  const early = c.band === "insufficient";
  return (
    <div className="p-card" data-testid="concept-card">
      <h3 className="p-h3">{conceptName(c.concept_id)}</h3>
      <div><span className="p-band" data-band={c.band}>{BAND_LABEL[c.band]}</span></div>
      <dl className="p-dl">
        <dt>p_known</dt>
        <dd className="num">{early ? <Warn>early estimate</Warn> : `${f2(c.p_known)} ± ${f2(c.uncertainty)}`}</dd>
        <dt>Evidence</dt>
        <dd className="num">{c.evidence_count} {c.evidence_count === 1 ? "answer" : "answers"}</dd>
      </dl>
    </div>
  );
}

export function PracticePanel({ step, mode, onSubmit, busy, refusal }: {
  step: NextStep; mode: "learner" | "teacher";
  onSubmit?: (correct: boolean) => void; busy?: boolean; refusal?: string | null;
}) {
  const approvedNone = step.selection?.trace.approved_in_pool === 0 && !step.demo_unapproved_allowed;
  return (
    <Card title="Practice">
      {step.item_id === null ? (
        <>
          <Empty title={approvedNone ? "No practice item is available" : "Nothing to practise right now"}>
            {approvedNone
              ? "The item bank has no approved items yet, so the API served none. No question is shown until reviewers approve items."
              : "The API served no item for this step."}
          </Empty>
          <p className="muted" data-testid="practice-api-reason">API reason: {step.reason}</p>
        </>
      ) : (
        <>
          <dl className="p-dl">
            <dt>Item</dt><dd data-testid="item-id">{step.item_id}</dd>
            <dt>Concept</dt><dd>{conceptName(step.concept_id ?? "")}</dd>
          </dl>
          <p className="muted">The API does not serve question text or an answer key yet.</p>
          {mode === "learner" && step.demo_unapproved_allowed ? (
            <div style={{ display: "grid", gap: 8 }}>
              <p><span className="p-demo-label">[DEMO FIXTURE]</span> Record the result of this item by hand. The state is then re-read from the API.</p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="p-btn" disabled={busy} onClick={() => onSubmit?.(true)}>Record as correct</button>
                <button type="button" className="p-btn secondary" disabled={busy} onClick={() => onSubmit?.(false)}>Record as incorrect</button>
              </div>
            </div>
          ) : null}
        </>
      )}
      {refusal ? <p role="alert" className="p-warn-text" data-testid="refusal">Attempt refused by the API: {refusal}</p> : null}
    </Card>
  );
}

/** State, next step and practice for one learner. mode "teacher" is read-only: no attempt control exists. */
export function LearnerPanel({ learnerId, principal, mode, origin }: { learnerId: string; principal: string; mode: "learner" | "teacher"; origin: Origin }) {
  const state = useResource(() => getState(principal, learnerId), `s:${principal}:${learnerId}`);
  const step = useResource(() => getNextStep(principal, learnerId), `n:${principal}:${learnerId}`);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  async function submit(correct: boolean) {
    if (step.status !== "ready" || !step.data.item_id || !step.data.concept_id) return;
    setBusy(true); setRefusal(null);
    try {
      await postAttempt(principal, learnerId, { event_id: newEventId(), concept_id: step.data.concept_id, item_id: step.data.item_id, correct });
      state.reload(); step.reload();           // the state shown is always the API's, re-read
    } catch (e) {
      setRefusal(e instanceof ProtoError ? e.message : "Unexpected error.");
    } finally { setBusy(false); }
  }

  if (state.status === "error") return <ErrorState error={state.error} onRetry={state.reload} />;
  if (step.status === "error") return <ErrorState error={step.error} onRetry={step.reload} />;
  if (state.status === "loading" || step.status === "loading") return <Loading what="the learner" />;
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <NextStepCard step={step.data} origin={origin} />
      <ConceptCards state={state.data} origin={origin} />
      <PracticePanel step={step.data} mode={mode} onSubmit={submit} busy={busy} refusal={refusal} />
    </div>
  );
}

/** The learner screen. Demo fixtures only, and the page says so. */
export function LearnerScreen({ learnerId }: { learnerId: string }) {
  const cfg = useResource(getConfig, "config");
  const head = <PageHead title="Learner next step" sub={<><span className="p-demo-label" data-testid="demo-label">[DEMO FIXTURE]</span> Demo learners only. Signed in as this learner (stub sign-in).</>} />;
  if (cfg.status === "loading") return <>{head}<Loading what="the learner" /></>;
  if (cfg.status === "error") return <>{head}<ErrorState error={cfg.error} onRetry={cfg.reload} /></>;
  const entry = cfg.data.roster.find((r) => r.id === learnerId);
  if (!entry || entry.origin !== "DEMO FIXTURE" || !cfg.data.principals.includes(learnerId)) {
    return <>{head}<ErrorState error={new ProtoError("denied", "This screen is open to demo learners only.")} /></>;
  }
  return <>{head}<LearnerPanel learnerId={learnerId} principal={learnerId} mode="learner" origin={entry.origin} /></>;
}

export function LearnerIndex() {
  const cfg = useResource(getConfig, "config");
  const head = <PageHead title="Learner next step" sub={<><span className="p-demo-label">[DEMO FIXTURE]</span> Choose a demo learner.</>} />;
  if (cfg.status === "loading") return <>{head}<Loading what="the learners" /></>;
  if (cfg.status === "error") return <>{head}<ErrorState error={cfg.error} onRetry={cfg.reload} /></>;
  const demo = cfg.data.roster.filter((r) => r.origin === "DEMO FIXTURE" && cfg.data.principals.includes(r.id));
  if (demo.length === 0) return <>{head}<Empty title="No demo learners">No demo learner has a stub sign-in configured.</Empty></>;
  return (
    <>
      {head}
      <ul style={{ display: "grid", gap: 8 }}>
        {demo.map((r) => <li key={r.id}><Link className="p-btn secondary" style={{ display: "inline-block", textDecoration: "none" }} href={`/prototype/learner/${r.id}`}>{r.label}</Link></li>)}
      </ul>
    </>
  );
}
