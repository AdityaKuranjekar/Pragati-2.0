"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ALL_LEARNERS, CONCEPTS, EDGES, conceptById } from "@/lib/prototype/data";
import { bottleneck, coverage, groupRows, useRows, type Row } from "@/lib/prototype/derive";
import { MIN_EVIDENCE, firstUnmet } from "@/lib/prototype/engine";
import { f2, fmtTime } from "@/lib/prototype/format";
import { NO_ESTIMATE_LONG, NO_ESTIMATE_WORD, STEPS, STEP_RANGE, STEP_WORD } from "@/lib/prototype/mastery-scale";
import { recordDecision, useDemoState } from "@/lib/prototype/store";
import type { Decision, EdgeState, Estimate, Step } from "@/lib/prototype/types";
import { Card, OriginTag, Warn } from "./frame";

const stepClass = (e: Estimate) => (e.insufficient ? "m0" : `m${e.step}`);
const wordOf = (e: Estimate) => (e.insufficient ? NO_ESTIMATE_WORD : STEP_WORD[e.step]);
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/* ---------- summary ---------- */
export function CohortSummary() {
  const rows = useRows();
  const fix = groupRows(rows, "fixture");
  const sim = groupRows(rows, "sim");
  const cf = coverage(fix);
  const cs = coverage(sim);
  const b = bottleneck(rows);
  return (
    <Card title="At a glance">
      <dl className="p-stats">
        <div className="p-stat">
          <dt>Learners</dt>
          <dd><span className="big num">{rows.length}</span> <span className="muted">learners</span></dd>
          <dd className="line num">{fix.length} demo <OriginTag origin="DEMO FIXTURE" /> and {sim.length} simulated <OriginTag origin="SIM" /></dd>
        </div>
        <div className="p-stat">
          <dt>Topics with enough practice to judge</dt>
          <dd><span className="big num">{cf.withEvidence + cs.withEvidence} of {cf.total + cs.total}</span></dd>
          <dd className="line num">Demo learners: {cf.withEvidence} of {cf.total} · Simulated: {cs.withEvidence} of {cs.total}</dd>
        </div>
        <div className="p-stat">
          <dt>Where most learners should start</dt>
          {b ? (
            <>
              <dd className="big">{b.concept.label}</dd>
              <dd className="line num">
                {b.simCount} of {b.simTotal} simulated and {b.fixCount} of {b.fixTotal} demo learners are not yet secure here.
                {b.downstream > 0 ? ` ${plural(b.downstream, "later topic")} in this chain depend${b.downstream === 1 ? "s" : ""} on it.` : ""}
              </dd>
              <dd className="line"><Link href="/prototype/teacher/bottleneck">See where learners get stuck</Link></dd>
            </>
          ) : (
            <dd className="line">Every simulated learner is secure on every topic.</dd>
          )}
        </div>
      </dl>
    </Card>
  );
}

/* ---------- heatmap ---------- */
function Legend() {
  return (
    <div className="p-legend" aria-label="Colour key">
      {STEPS.map((s) => (
        <span key={s} className={`sw m${s}`}>{STEP_WORD[s]}</span>
      ))}
      <span className="sw m0">{NO_ESTIMATE_WORD}</span>
      <span>Too early means fewer than {MIN_EVIDENCE} questions answered.</span>
    </div>
  );
}

function groupSentence(rows: Row[], i: number) {
  const c: Record<Step, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  let none = 0;
  rows.forEach((r) => (r.est[i].insufficient ? none++ : c[r.est[i].step]++));
  const parts = [
    { n: c[4] + c[5], t: "secure or mostly secure" },
    { n: c[3], t: "getting there" },
    { n: c[1] + c[2], t: "just starting or need practice" },
    { n: none, t: "too early to tell" },
  ].filter((p) => p.n > 0);
  return { c, none, text: parts.map((p) => `${p.n} ${p.t}`).join(" · ") || "No learners" };
}

function GroupCell({ rows, i, label }: { rows: Row[]; i: number; label: string }) {
  const { c, none, text } = groupSentence(rows, i);
  return (
    <div>
      <div className="p-dist" role="img" aria-label={`${label}: ${text}`}>
        {none > 0 && <span className="m0" style={{ flexGrow: none }}>{none}</span>}
        {STEPS.filter((s) => c[s] > 0).map((s) => (
          <span key={s} className={`m${s}`} style={{ flexGrow: c[s] }}>{c[s]}</span>
        ))}
      </div>
      <p className="small muted num" style={{ marginTop: 6 }}>{text}</p>
    </div>
  );
}

export function ConceptHeatmap() {
  const rows = useRows();
  const [view, setView] = useState<"group" | "learner">("group");
  const [sel, setSel] = useState<{ learnerId: string; conceptId: string } | null>(null);
  const fix = groupRows(rows, "fixture");
  const sim = groupRows(rows, "sim");
  const selRow = sel ? rows.find((r) => r.learner.id === sel.learnerId) : null;
  const selEst = selRow && sel ? selRow.est.find((e) => e.conceptId === sel.conceptId) : null;

  return (
    <Card
      title="How each topic is going"
      right={
        <div className="p-seg" role="group" aria-label="View">
          <button type="button" aria-pressed={view === "group"} onClick={() => setView("group")}>Whole group</button>
          <button type="button" aria-pressed={view === "learner"} onClick={() => setView("learner")}>Each learner</button>
        </div>
      }
    >
      <Legend />
      {view === "group" ? (
        <table className="p-gtable stack">
          <thead>
            <tr>
              <th scope="col">Topic</th>
              <th scope="col">Demo learners ({fix.length}) <OriginTag origin="DEMO FIXTURE" /></th>
              <th scope="col">Simulated learners ({sim.length}) <OriginTag origin="SIM" /></th>
            </tr>
          </thead>
          <tbody>
            {CONCEPTS.map((c, i) => (
              <tr key={c.id}>
                <th scope="row">{c.label}</th>
                <td data-label={`Demo learners (${fix.length})`}><GroupCell rows={fix} i={i} label={`${c.label}, demo learners`} /></td>
                <td data-label={`Simulated learners (${sim.length})`}><GroupCell rows={sim} i={i} label={`${c.label}, simulated learners`} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <>
          <div className="p-scroll" tabIndex={0} aria-label="Topics by learner, scrolls sideways">
            <table className="p-grid">
              <thead>
                <tr>
                  <th scope="col"><span className="sr-only">Topic</span></th>
                  <th scope="colgroup" colSpan={fix.length} className="grp">Demo <OriginTag origin="DEMO FIXTURE" /></th>
                  <th scope="colgroup" colSpan={sim.length} className="grp" style={{ borderLeft: "1px solid var(--border)" }}>Simulated <OriginTag origin="SIM" /></th>
                </tr>
                <tr>
                  <th scope="col">Topic</th>
                  {ALL_LEARNERS.map((l, i) => (
                    <th key={l.id} scope="col" style={i === fix.length ? { borderLeft: "1px solid var(--border)" } : undefined}>{l.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {CONCEPTS.map((c, ci) => (
                  <tr key={c.id}>
                    <th scope="row">{c.short}</th>
                    {rows.map((r, i) => {
                      const e = r.est[ci];
                      const active = sel?.learnerId === r.learner.id && sel.conceptId === c.id;
                      return (
                        <td key={r.learner.id} style={i === fix.length ? { borderLeft: "1px solid var(--border)" } : undefined}>
                          <button
                            type="button"
                            className={`p-cell ${stepClass(e)}`}
                            aria-pressed={active}
                            aria-label={`${r.learner.label}, ${c.label}: ${e.insufficient ? NO_ESTIMATE_LONG : STEP_WORD[e.step]}, ${plural(e.n, "question")} answered`}
                            onClick={() => setSel(active ? null : { learnerId: r.learner.id, conceptId: c.id })}
                          >
                            <b>{wordOf(e)}</b>
                            <i className="num">{e.n} answered</i>
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div aria-live="polite" style={{ marginTop: 16 }}>
            {selRow && selEst ? (
              <div className="p-stack" style={{ gap: 8 }}>
                <h3 className="p-h2">{selRow.learner.label} <OriginTag origin={selRow.learner.origin} /></h3>
                <p className="p-sentence">
                  <strong>{conceptById(selEst.conceptId).label}:</strong>{" "}
                  {selEst.insufficient
                    ? `${NO_ESTIMATE_LONG}. ${plural(selEst.n, "question")} answered so far; at least ${MIN_EVIDENCE} are needed.`
                    : `${STEP_WORD[selEst.step]}. ${selEst.k} of ${selEst.n} answers were correct.${selEst.early ? " This rests on few questions, so it may change." : ""}`}
                </p>
                {!selEst.insufficient && (
                  <details className="p-more">
                    <summary>Show the numbers</summary>
                    <dl className="p-detail">
                      <div><dt>Estimate</dt><dd className="num">{f2(selEst.mean)}</dd></div>
                      <div><dt>Likely range (80%)</dt><dd className="num">{f2(selEst.lo)} to {f2(selEst.hi)}</dd></div>
                      <div><dt>Level band</dt><dd className="num">{STEP_RANGE[selEst.step]}</dd></div>
                    </dl>
                  </details>
                )}
              </div>
            ) : (
              <p className="muted small">Select a cell to see what is behind it.</p>
            )}
          </div>
        </>
      )}
      <p className="small muted" style={{ marginTop: 16, maxWidth: "75ch" }}>
        Topics follow syllabus order. Learners are not ranked or sorted by score. Simulated learners are made up and say nothing about real students.
      </p>
    </Card>
  );
}

/* ---------- bottleneck ---------- */
const STATE_LABEL: Record<EdgeState, string> = {
  proposed: "Suggested, not yet reviewed by a teacher",
  accepted: "Confirmed by a teacher",
  modified: "Changed by a teacher",
  dismissed: "Removed by a teacher",
};
const stateOf = (edgeId: string, decisions: Decision[]): EdgeState => {
  const last = [...decisions].reverse().find((d) => d.edgeId === edgeId);
  return last ? last.decision : "proposed";
};
const edgeText = (e: (typeof EDGES)[number]) => `${conceptById(e.from).short} comes before ${conceptById(e.to).short}`;

export function BottleneckView() {
  const rows = useRows();
  const { decisions } = useDemoState();
  const b = bottleneck(rows);
  const fixtures = groupRows(rows, "fixture");

  return (
    <div className="p-stack">
      <Card title={b ? `Most learners should start with ${b.concept.label}` : "No common starting point"} origin={["DEMO FIXTURE", "SIM"]}>
        {b ? (
          <>
            <p className="p-sentence num">
              {b.simCount} of {b.simTotal} simulated learners and {b.fixCount} of {b.fixTotal} demo learners are not yet secure on this topic, and it is the first one they need to work on.
              {b.downstream > 0 ? ` ${plural(b.downstream, "later topic")} in this chain depend${b.downstream === 1 ? "s" : ""} on it.` : ""}
            </p>
            <details className="p-more">
              <summary>How this was worked out</summary>
              <p className="muted">For each learner we take the first topic, in syllabus order, that is not yet secure or has too few answers to judge. The topic that is first for the most simulated learners is shown. If two topics tie, the earlier one is shown.</p>
            </details>
          </>
        ) : (
          <p>Every simulated learner is secure on every topic.</p>
        )}
      </Card>

      <Card title="How the topics connect">
        <div className="p-chain">
          {CONCEPTS.map((c, i) => {
            const e = EDGES[i];
            const st = e ? stateOf(e.id, decisions) : null;
            return (
              <div key={c.id}>
                <div className="p-node">{c.label}</div>
                {e && st && (
                  <div className={`p-edge ${st}`}>
                    <span>{conceptById(e.from).short} has to come before {conceptById(e.to).short}</span>
                    {st === "proposed" ? <Warn>{STATE_LABEL[st]}</Warn> : <strong>{STATE_LABEL[st]}</strong>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <p className="small muted" style={{ marginTop: 12 }}>These links are suggestions from the content team. Until a teacher reviews them they are not treated as fact.</p>
      </Card>

      <Card title="Who is stuck, and where" origin={["DEMO FIXTURE", "SIM"]}>
        <ul className="p-stack" style={{ gap: 8 }}>
          {fixtures.map((r) => {
            const t = firstUnmet(r.est);
            return (
              <li key={r.learner.id} className="num">
                <strong>{r.learner.label}</strong> <OriginTag origin="DEMO FIXTURE" />{" "}
                {t ? `should start with ${conceptById(t.conceptId).short} (${t.insufficient ? `${plural(t.n, "question")} answered so far` : `${t.k} of ${t.n} answers correct`}).` : "is secure on every topic."}
              </li>
            );
          })}
          <li className="num">
            <strong>Simulated learners</strong> <OriginTag origin="SIM" />{" "}
            {b ? `should start with: ${CONCEPTS.map((c, i) => `${c.short} (${b.simCounts[i]})`).join(", ")}.` : "are secure on every topic."}
          </li>
        </ul>
      </Card>

      <ReviewForm decisions={decisions} />
    </div>
  );
}

function ReviewForm({ decisions }: { decisions: Decision[] }) {
  const [edgeId, setEdgeId] = useState(EDGES[0].id);
  const [decision, setDecision] = useState<Decision["decision"]>("accepted");
  const [reason, setReason] = useState("");
  const ok = reason.trim().length > 0;
  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    if (!ok) return;
    recordDecision({ edgeId, decision, reason: reason.trim() });
    setReason("");
  };
  const DECISIONS = [
    { v: "accepted", t: "Yes, keep this link" },
    { v: "modified", t: "Change it" },
    { v: "dismissed", t: "No, remove it" },
  ] as const;
  const PAST = { accepted: "Confirmed", modified: "Changed", dismissed: "Removed" } as const;
  return (
    <Card title="Review a suggested link">
      <form className="p-form" onSubmit={submit}>
        <fieldset className="p-fs">
          <legend>Which link?</legend>
          {EDGES.map((e) => (
            <label key={e.id} className="p-radio">
              <input type="radio" name="edge" value={e.id} checked={edgeId === e.id} onChange={() => setEdgeId(e.id)} />
              {edgeText(e)}
            </label>
          ))}
        </fieldset>
        <fieldset className="p-fs">
          <legend>Is this a real prerequisite?</legend>
          {DECISIONS.map((d) => (
            <label key={d.v} className="p-radio">
              <input type="radio" name="decision" value={d.v} checked={decision === d.v} onChange={() => setDecision(d.v)} />
              {d.t}
            </label>
          ))}
        </fieldset>
        <div>
          <label htmlFor="reason" style={{ display: "block", fontWeight: 500, marginBottom: 6 }}>Why? (required)</label>
          <textarea id="reason" className="p-text" value={reason} onChange={(e) => setReason(e.target.value)} aria-describedby="reason-help" />
          <p id="reason-help" className="small muted" style={{ marginTop: 4 }}>If you chose “Change it”, say what the link should be.</p>
        </div>
        <div><button type="submit" className="p-btn primary" disabled={!ok}>Save decision</button></div>
      </form>
      <h3 className="p-h2" style={{ margin: "20px 0 8px" }}>Decisions so far</h3>
      {decisions.length === 0 ? (
        <p className="muted">None yet.</p>
      ) : (
        <ul className="p-stack" style={{ gap: 8 }}>
          {decisions.map((d) => {
            const e = EDGES.find((x) => x.id === d.edgeId)!;
            return (
              <li key={d.id}>
                <strong>{PAST[d.decision]}:</strong> {edgeText(e)}. {d.reason}
                <span className="small muted"> {d.decidedBy}, {fmtTime(d.decidedAt)}</span>
              </li>
            );
          })}
        </ul>
      )}
      <p className="small muted" style={{ marginTop: 12 }}>Decisions are kept in this browser tab only. They do not change how learners are recommended.</p>
    </Card>
  );
}
