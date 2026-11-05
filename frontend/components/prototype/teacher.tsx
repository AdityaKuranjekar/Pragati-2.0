"use client";
import { useState } from "react";
import { ProtoError, getBottlenecks, getConfig, getState } from "@/lib/prototype/client";
import { BAND_LABEL, BAND_ORDER, conceptName } from "@/lib/prototype/labels";
import type { Band, Bottlenecks, Config, LearnerState, Origin } from "@/lib/prototype/schemas";
import { useResource } from "@/lib/prototype/useResource";
import { Card, Empty, ErrorState, Loading, OriginTag, PageHead, Warn } from "./common";
import { LearnerPanel } from "./learner";

export type StateMap = Record<string, LearnerState | ProtoError>;
const isState = (v: LearnerState | ProtoError | undefined): v is LearnerState => !!v && !(v instanceof ProtoError);

const TEACHER = "teacher";

/** Config, bottlenecks and every roster learner's state, all read from the API as the teacher. */
async function loadCohort() {
  const config = await getConfig();
  const [bottlenecks, settled] = await Promise.all([
    getBottlenecks(TEACHER, config.cohort_id),
    Promise.allSettled(config.roster.map((r) => getState(TEACHER, r.id))),
  ]);
  const states: StateMap = {};
  config.roster.forEach((r, i) => {
    const s = settled[i];
    states[r.id] = s.status === "fulfilled" ? s.value : s.reason instanceof ProtoError ? s.reason : new ProtoError("unavailable", "Unexpected error.");
  });
  return { config, bottlenecks, states };
}

export function conceptOrder(states: StateMap): string[] {
  const out: string[] = [];
  for (const s of Object.values(states)) if (isState(s)) for (const c of s.concepts) if (!out.includes(c.concept_id)) out.push(c.concept_id);
  return out;
}
const cellOf = (s: LearnerState | ProtoError | undefined, concept: string) => (isState(s) ? s.concepts.find((c) => c.concept_id === concept) : undefined);
const originsOf = (config: Config): Origin[] => Array.from(new Set(config.roster.map((r) => r.origin)));

export function CohortSummary({ config, bottlenecks, states }: { config: Config; bottlenecks: Bottlenecks; states: StateMap }) {
  const concepts = conceptOrder(states);
  let withBand = 0, total = 0;
  for (const r of config.roster) for (const c of concepts) {
    const cell = cellOf(states[r.id], c);
    if (cell) { total += 1; if (cell.band !== "insufficient") withBand += 1; }
  }
  const top = bottlenecks.bottlenecks[0];
  return (
    <Card title="Cohort summary" origins={originsOf(config)}>
      <div className="p-grid">
        <div className="p-stat"><span className="label">Learners</span><b data-testid="learner-count">{bottlenecks.learner_count}</b></div>
        <div className="p-stat">
          <span className="label">Evidence coverage</span>
          <b data-testid="coverage">{withBand} of {total}</b>
          <span className="label">learner and concept pairs have enough evidence for a band</span>
        </div>
        <div className="p-stat">
          <span className="label">Bottleneck concept</span>
          {top ? (
            <>
              <b data-testid="bottleneck-name" style={{ fontSize: 18 }}>{conceptName(top.concept_id)}</b>
              <span data-testid="bottleneck-count">{top.learners_blocked} of {bottlenecks.learner_count} learners blocked</span>
            </>
          ) : <b style={{ fontSize: 18 }}>None on current evidence</b>}
        </div>
      </div>
    </Card>
  );
}

export function GroupTable({ config, states }: { config: Config; states: StateMap }) {
  const concepts = conceptOrder(states);
  return (
    <div className="p-scroll" tabIndex={0} role="region" aria-label="Group view: learners per band for each concept">
      <table className="p-table">
        <caption className="sr-only">Number of learners in each band, per concept</caption>
        <thead>
          <tr><th scope="col">Concept</th>{BAND_ORDER.map((b) => <th scope="col" key={b}>{BAND_LABEL[b]}</th>)}</tr>
        </thead>
        <tbody>
          {concepts.map((c) => (
            <tr key={c}>
              <th scope="row">{conceptName(c)}</th>
              {BAND_ORDER.map((b) => {
                const n = config.roster.filter((r) => cellOf(states[r.id], c)?.band === b).length;
                return <td key={b} className="num" data-testid={`group-${b}`}>{n} {n === 1 ? "learner" : "learners"}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Heatmap({ config, states, selected, onSelect }: {
  config: Config; states: StateMap; selected?: string | null; onSelect?: (id: string) => void;
}) {
  const concepts = conceptOrder(states);
  return (
    <div className="p-scroll" tabIndex={0} role="region" aria-label="Concept heatmap, concepts by learners">
      <table className="p-table p-heat" data-testid="heatmap">
        <caption className="sr-only">Band and answer count for each concept and learner. Select a learner name for detail.</caption>
        <thead>
          <tr>
            <th scope="col">Concept</th>
            {config.roster.map((r) => (
              <th scope="col" key={r.id}>
                <button type="button" className="p-linkbtn" aria-pressed={selected === r.id} onClick={() => onSelect?.(r.id)} data-testid={`col-${r.id}`}>{r.label}</button>
                <div><OriginTag origin={r.origin} /></div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {concepts.map((c) => (
            <tr key={c}>
              <th scope="row">{conceptName(c)}</th>
              {config.roster.map((r) => {
                const s = states[r.id];
                const cell = cellOf(s, c);
                if (!cell) return <td key={r.id}><span className="p-warn-text">Unavailable</span></td>;
                return (
                  <td key={r.id}>
                    <div className="p-cell" data-band={cell.band} data-testid={`cell-${r.id}-${c.split(".").pop()}`}>
                      <b>{BAND_LABEL[cell.band as Band]}</b>
                      <span className="num">{cell.evidence_count} {cell.evidence_count === 1 ? "answer" : "answers"}</span>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A band legend: colour never stands alone. */
function Legend() {
  return (
    <ul style={{ display: "flex", flexWrap: "wrap", gap: 8 }} aria-label="Legend">
      {BAND_ORDER.map((b) => <li key={b}><span className="p-band" data-band={b}>{BAND_LABEL[b]}</span></li>)}
    </ul>
  );
}

export function BottleneckPanel({ data }: { data: Bottlenecks }) {
  if (data.bottlenecks.length === 0) {
    return <Empty title="No bottleneck on current evidence">No concept is blocking a dependent concept for any learner in this cohort.</Empty>;
  }
  return (
    <ul style={{ display: "grid", gap: 12 }} aria-label="Bottleneck concepts">
      {data.bottlenecks.map((b) => (
        <li key={b.concept_id} className="p-edge" data-testid="bottleneck-row">
          <h3 className="p-h3">{conceptName(b.concept_id)}</h3>
          <p className="num">{b.learners_blocked} of {data.learner_count} learners blocked</p>
          <ul style={{ display: "grid", gap: 8 }}>
            {b.dependents.map((d, i) => {
              const state = b.edge_review[i] ?? "unknown";
              const proposed = state === "proposed";
              return (
                <li key={d} className="p-edge" data-review={state} data-testid="edge">
                  <span>Prerequisite: {conceptName(b.concept_id)} → {conceptName(d)}</span>
                  {proposed ? <Warn>proposed, not yet reviewed</Warn> : <span className="label">Review state: {state}</span>}
                </li>
              );
            })}
          </ul>
        </li>
      ))}
      <li className="label">Counted as: learners for whom the concept is not mastered or uncertain and at least one dependent is not mastered. Teachers can view this; they cannot submit attempts.</li>
    </ul>
  );
}

export function CohortView() {
  const r = useResource(loadCohort, "cohort");
  const [selected, setSelected] = useState<string | null>(null);
  if (r.status === "loading") return <><PageHead title="Teacher cohort view" /><Loading what="the cohort" /></>;
  if (r.status === "error") return <><PageHead title="Teacher cohort view" /><ErrorState error={r.error} onRetry={r.reload} /></>;
  const { config, bottlenecks, states } = r.data;
  return (
    <>
      <PageHead title="Teacher cohort view" sub="Group first. Select a learner for detail. Teachers see bottlenecks and cohort data only." />
      {config.roster.length === 0 ? <Empty title="No learners">The cohort has no learners configured.</Empty> : (
        <>
          <CohortSummary config={config} bottlenecks={bottlenecks} states={states} />
          <Card title="Group view" origins={originsOf(config)}>
            <GroupTable config={config} states={states} />
          </Card>
          <Card title="Concept heatmap" origins={originsOf(config)}>
            <Legend />
            <Heatmap config={config} states={states} selected={selected} onSelect={setSelected} />
          </Card>
          {selected ? <LearnerDetail config={config} id={selected} onClose={() => setSelected(null)} /> : null}
        </>
      )}
      <Card title="Bottleneck panel" origins={originsOf(config)}>
        <BottleneckPanel data={bottlenecks} />
      </Card>
    </>
  );
}

function LearnerDetail({ config, id, onClose }: { config: Config; id: string; onClose: () => void }) {
  const entry = config.roster.find((x) => x.id === id)!;
  return (
    <Card title={`Learner detail: ${entry.label}`} origins={[entry.origin]} right={<button type="button" className="p-btn secondary" onClick={onClose}>Close</button>}>
      <LearnerPanel learnerId={id} principal={TEACHER} mode="teacher" origin={entry.origin} />
    </Card>
  );
}

export function BottleneckOnly() {
  const r = useResource(async () => {
    const config = await getConfig();
    return { config, data: await getBottlenecks(TEACHER, config.cohort_id) };
  }, "bottleneck");
  return (
    <>
      <PageHead title="Bottleneck panel" />
      {r.status === "loading" ? <Loading what="the bottlenecks" /> : r.status === "error" ? <ErrorState error={r.error} onRetry={r.reload} /> : (
        <Card title="Prerequisite edges" origins={originsOf(r.data.config)}><BottleneckPanel data={r.data.data} /></Card>
      )}
    </>
  );
}

