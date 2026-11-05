"use client";
import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";
import { ALL_LEARNERS, CONCEPTS, EDGES, SIM_COUNT, SIM_SEED, conceptById } from "@/lib/prototype/data";
import { bottleneck, coverage, groupRows, useRows, type Row } from "@/lib/prototype/derive";
import { MASTERED_AT, MIN_EVIDENCE, firstUnmet } from "@/lib/prototype/engine";
import { f2, fmtTime } from "@/lib/prototype/format";
import { STEPS, STEP_LABEL } from "@/lib/prototype/mastery-scale";
import { recordDecision, useDemoState } from "@/lib/prototype/store";
import type { Decision, EdgeState, Estimate, Step } from "@/lib/prototype/types";
import { Card, OriginTag, Warn } from "./frame";

const stepClass = (e: Estimate) => (e.insufficient ? "m0" : `m${e.step}`);

/* ---------- cohort summary ---------- */
export function CohortSummary() {
  const rows = useRows();
  const fix = groupRows(rows, "fixture");
  const sim = groupRows(rows, "sim");
  const cf = coverage(fix);
  const cs = coverage(sim);
  const b = bottleneck(rows);
  return (
    <Card title="Cohort summary">
      <dl className="p-stats">
        <div className="p-stat">
          <dt>Learners</dt>
          <dd className="num"><span className="big">{fix.length}</span> <span className="muted">fixtures</span> <OriginTag origin="DEMO FIXTURE" /></dd>
          <dd className="num"><span className="big">{sim.length}</span> <span className="muted">simulated</span> <OriginTag origin="SIM" /></dd>
        </div>
        <div className="p-stat">
          <dt>Concepts with enough evidence ({MIN_EVIDENCE} or more attempts)</dt>
          <dd className="num"><span className="big">{cf.withEvidence} of {cf.total}</span> <span className="muted">fixtures</span> <OriginTag origin="DEMO FIXTURE" /></dd>
          <dd className="num"><span className="big">{cs.withEvidence} of {cs.total}</span> <span className="muted">simulated</span> <OriginTag origin="SIM" /></dd>
        </div>
        <div className="p-stat">
          <dt>Bottleneck concept</dt>
          {b ? (
            <>
              <dd className="big">{b.concept.label}</dd>
              <dd className="line num">
                First unmet concept for {b.simCount} of {b.simTotal} simulated <OriginTag origin="SIM" /> and {b.fixCount} of {b.fixTotal} fixture <OriginTag origin="DEMO FIXTURE" /> learners.
                {b.downstream > 0 ? ` Blocks ${b.downstream} later concept${b.downstream === 1 ? "" : "s"} in this chain.` : ""}
              </dd>
              <dd className="line"><Link href="/prototype/teacher/bottleneck">Open bottleneck panel</Link></dd>
            </>
          ) : (
            <dd className="line">No concept is the first unmet concept for any simulated learner.</dd>
          )}
        </div>
      </dl>
    </Card>
  );
}

/* ---------- heatmap ---------- */
function Legend() {
  return (
    <div className="p-legend" aria-label="Mastery scale">
      <span>Estimate:</span>
      {STEPS.map((s) => (
        <span key={s} className={`sw m${s}`}>{STEP_LABEL[s]}</span>
      ))}
      <span className="sw m0">--</span>
      <span>Fewer than {MIN_EVIDENCE} attempts: no estimate</span>
    </div>
  );
}

function DistBar({ rows, conceptIndex, label }: { rows: Row[]; conceptIndex: number; label: string }) {
  const counts: Record<Step, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  let none = 0;
  rows.forEach((r) => {
    const e = r.est[conceptIndex];
    if (e.insufficient) none++;
    else counts[e.step]++;
  });
  const summary = [...STEPS.map((s) => `${STEP_LABEL[s]}: ${counts[s]}`), `fewer than ${MIN_EVIDENCE} attempts: ${none}`].join(", ");
  return (
    <div>
      <div className="p-dist" role="img" aria-label={`${label}. ${summary}`}>
        {none > 0 && <span className="m0" style={{ flexGrow: none }}>{none}</span>}
        {STEPS.filter((s) => counts[s] > 0).map((s) => (
          <span key={s} className={`m${s}`} style={{ flexGrow: counts[s] }}>{counts[s]}</span>
        ))}
      </div>
      <p className="cap small muted num" style={{ marginTop: 4 }}>{summary}</p>
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
      title="Concept by learner"
      right={
        <div className="p-seg" role="group" aria-label="View">
          <button type="button" aria-pressed={view === "group"} onClick={() => setView("group")}>Group</button>
          <button type="button" aria-pressed={view === "learner"} onClick={() => setView("learner")}>Learner</button>
        </div>
      }
    >
      <Legend />
      {view === "group" ? (
        <table className="p-gtable stack">
          <thead>
            <tr>
              <th scope="col">Concept (syllabus order)</th>
              <th scope="col">Fixtures ({fix.length}) <OriginTag origin="DEMO FIXTURE" /></th>
              <th scope="col">Simulated ({sim.length}) <OriginTag origin="SIM" /></th>
            </tr>
          </thead>
          <tbody>
            {CONCEPTS.map((c, i) => (
              <tr key={c.id}>
                <th scope="row">{c.label}</th>
                <td data-label={`Fixtures (${fix.length}) [DEMO FIXTURE]`}><DistBar rows={fix} conceptIndex={i} label={`${c.label}, fixtures`} /></td>
                <td data-label={`Simulated (${sim.length}) [SIM]`}><DistBar rows={sim} conceptIndex={i} label={`${c.label}, simulated`} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <>
          <div className="p-scroll" tabIndex={0} aria-label="Concept by learner table, scrolls sideways">
            <table className="p-grid">
              <thead>
                <tr>
                  <th scope="col"><span className="sr-only">Concept</span></th>
                  <th scope="colgroup" colSpan={fix.length} className="grp">Fixtures <OriginTag origin="DEMO FIXTURE" /></th>
                  <th scope="colgroup" colSpan={sim.length} className="grp" style={{ borderLeft: "1px solid var(--border)" }}>Simulated <OriginTag origin="SIM" /></th>
                </tr>
                <tr>
                  <th scope="col">Concept</th>
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
                            aria-label={`${r.learner.label}, ${c.label}: ${e.insufficient ? "no estimate" : `estimate ${f2(e.mean)}`}, ${e.n} attempts`}
                            onClick={() => setSel(active ? null : { learnerId: r.learner.id, conceptId: c.id })}
                          >
                            <b className="num">{e.insufficient ? "--" : f2(e.mean)}</b>
                            <i className="num">n={e.n}</i>
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
              <>
                <h3 className="p-h2" style={{ marginBottom: 8 }}>{selRow.learner.label} <OriginTag origin={selRow.learner.origin} /></h3>
                <dl className="p-detail">
                  <div><dt>Concept</dt><dd>{conceptById(selEst.conceptId).label}</dd></div>
                  <div><dt>Estimate</dt><dd className="num">{selEst.insufficient ? "No estimate" : f2(selEst.mean)}</dd></div>
                  <div><dt>Range (80%)</dt><dd className="num">{selEst.insufficient ? "Not shown" : `${f2(selEst.lo)} to ${f2(selEst.hi)}`}</dd></div>
                  <div><dt>Attempts</dt><dd className="num">{selEst.n}</dd></div>
                  <div><dt>Status</dt><dd>{selEst.insufficient ? <Warn>Insufficient evidence</Warn> : selEst.early ? "Early estimate" : "Enough evidence"}</dd></div>
                </dl>
              </>
            ) : (
              <p className="muted small">Select a cell to see the range and evidence for that learner and concept.</p>
            )}
          </div>
        </>
      )}
      <p className="small muted" style={{ marginTop: 16, maxWidth: "75ch" }}>
        Rows follow syllabus order. Columns are not sorted by score. Simulated learners come from a fixed seed ({SIM_SEED}, {SIM_COUNT} learners) in a generator separate from the estimate function; they say nothing about real learners.
        Estimates here are the share-correct rule used by this prototype, not the Pragati engine.
      </p>
    </Card>
  );
}

/* ---------- bottleneck panel ---------- */
const STATE_LABEL: Record<EdgeState, string> = {
  proposed: "Proposed, unreviewed",
  accepted: "Accepted",
  modified: "Modified",
  dismissed: "Dismissed",
};
const stateOf = (edgeId: string, decisions: Decision[]): EdgeState => {
  const last = [...decisions].reverse().find((d) => d.edgeId === edgeId);
  return last ? last.decision : "proposed";
};

export function BottleneckView() {
  const rows = useRows();
  const { decisions } = useDemoState();
  const b = bottleneck(rows);
  const fixtures = groupRows(rows, "fixture");
  const sim = groupRows(rows, "sim");

  return (
    <div className="p-stack">
      <Card title={b ? `Bottleneck: ${b.concept.label}` : "No bottleneck"} origin={["DEMO FIXTURE", "SIM"]}>
        {b ? (
          <>
            <p className="num">
              First unmet concept for {b.simCount} of {b.simTotal} simulated learners <OriginTag origin="SIM" /> and {b.fixCount} of {b.fixTotal} fixture learners <OriginTag origin="DEMO FIXTURE" />.
              {b.downstream > 0 ? ` It blocks ${b.downstream} later concept${b.downstream === 1 ? "" : "s"} in this chain.` : ""}
            </p>
            <p className="small muted" style={{ marginTop: 8 }}>
              Method: count of learners whose first concept in chain order with an estimate below {f2(MASTERED_AT)}, or with fewer than {MIN_EVIDENCE} attempts, is this one. Ties go to the earlier concept.
            </p>
          </>
        ) : (
          <p>No concept is the first unmet concept for any simulated learner.</p>
        )}
      </Card>

      <Card title="Prerequisite path">
        <div className="p-chain">
          {CONCEPTS.map((c, i) => {
            const e = EDGES[i];
            const st = e ? stateOf(e.id, decisions) : null;
            return (
              <div key={c.id}>
                <div className="p-node">{c.label}</div>
                {e && st && (
                  <div className={`p-edge ${st}`}>
                    <span>Prerequisite edge: {conceptById(e.from).short} before {conceptById(e.to).short}</span>
                    {st === "proposed" ? <Warn>{STATE_LABEL[st]}</Warn> : <strong>{STATE_LABEL[st]}</strong>}
                    <span>{e.source}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <p className="small muted" style={{ marginTop: 12 }}>Edges marked proposed are suggestions, not confirmed facts.</p>
      </Card>

      <Card title="Why this concept is flagged" origin={["DEMO FIXTURE", "SIM"]}>
        <ul className="p-stack" style={{ gap: 8 }}>
          {fixtures.map((r) => {
            const t = firstUnmet(r.est);
            const e = b ? r.est[b.index] : null;
            return (
              <li key={r.learner.id} className="num">
                <strong>{r.learner.label}</strong> <OriginTag origin="DEMO FIXTURE" />:{" "}
                {e ? (e.insufficient ? <>no estimate on {b!.concept.short} ({e.n} attempts)</> : <>{f2(e.mean)} on {b!.concept.short} ({e.n} attempts)</>) : "no data"}
                {t ? `. First unmet concept: ${conceptById(t.conceptId).short}.` : ". No unmet concept."}
              </li>
            );
          })}
          <li className="num">
            <strong>Simulated learners</strong> <OriginTag origin="SIM" />: {b ? `${b.simCounts.map((n, i) => `${CONCEPTS[i].short} ${n}`).join(", ")} of ${sim.length} (count of learners whose first unmet concept is that one)` : "none"}.
          </li>
        </ul>
      </Card>

      <OverrideForm decisions={decisions} />
    </div>
  );
}

function OverrideForm({ decisions }: { decisions: Decision[] }) {
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
  const edge = useMemo(() => EDGES.find((e) => e.id === edgeId)!, [edgeId]);
  return (
    <Card title="Review a suggested edge">
      <form className="p-form" onSubmit={submit}>
        <fieldset className="p-fs">
          <legend>Edge</legend>
          {EDGES.map((e) => (
            <label key={e.id} className="p-radio">
              <input type="radio" name="edge" value={e.id} checked={edgeId === e.id} onChange={() => setEdgeId(e.id)} />
              {conceptById(e.from).short} before {conceptById(e.to).short}
            </label>
          ))}
        </fieldset>
        <fieldset className="p-fs">
          <legend>Decision for “{conceptById(edge.from).short} before {conceptById(edge.to).short}”</legend>
          {(["accepted", "modified", "dismissed"] as const).map((d) => (
            <label key={d} className="p-radio">
              <input type="radio" name="decision" value={d} checked={decision === d} onChange={() => setDecision(d)} />
              {d === "accepted" ? "Accept" : d === "modified" ? "Modify" : "Dismiss"}
            </label>
          ))}
        </fieldset>
        <div>
          <label htmlFor="reason" style={{ display: "block", fontWeight: 500, marginBottom: 6 }}>Reason (required)</label>
          <textarea id="reason" className="p-text" value={reason} onChange={(e) => setReason(e.target.value)} aria-describedby="reason-help" />
          <p id="reason-help" className="small muted" style={{ marginTop: 4 }}>For Modify, describe the change you want.</p>
        </div>
        <div><button type="submit" className="p-btn primary" disabled={!ok}>Save decision</button></div>
      </form>
      <h3 className="p-h2" style={{ margin: "20px 0 8px" }}>Saved decisions</h3>
      {decisions.length === 0 ? (
        <p className="muted">None.</p>
      ) : (
        <ul className="p-stack" style={{ gap: 8 }}>
          {decisions.map((d) => {
            const e = EDGES.find((x) => x.id === d.edgeId)!;
            return (
              <li key={d.id}>
                <strong>{d.decision === "accepted" ? "Accepted" : d.decision === "modified" ? "Modified" : "Dismissed"}</strong>: {conceptById(e.from).short} before {conceptById(e.to).short}. {d.reason}
                <span className="small muted"> {d.decidedBy}, {fmtTime(d.decidedAt)}</span>
              </li>
            );
          })}
        </ul>
      )}
      <p className="small muted" style={{ marginTop: 12 }}>Decisions are kept in this browser session only. They do not change the engine.</p>
    </Card>
  );
}
