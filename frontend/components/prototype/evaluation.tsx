"use client";
import { getEvaluation } from "@/lib/prototype/client";
import type { EvalRow, EvalSet, Evaluation, SetRow } from "@/lib/prototype/schemas";
import { useResource } from "@/lib/prototype/useResource";
import { Card, Empty, ErrorState, Loading, OriginTag, PageHead } from "./common";

const SETTING_LABEL: Record<string, string> = {
  P_primary_neutral: "Primary setting",
  S1_zone_learning: "Zone-learning assumption",
  S2_no_forgetting: "No forgetting",
  S3_short_budget: "Short budget (36 items)",
};

/** Pass and miss use the same row style; the verdict is printed as text. */
export function ResultsTable({ rows }: { rows: EvalRow[] }) {
  return (
    <div className="p-scroll" tabIndex={0} role="region" aria-label="Evaluation results">
      <table className="p-table" data-testid="eval-table">
        <thead>
          <tr>
            <th scope="col">Metric</th><th scope="col">Task</th><th scope="col">Origin</th><th scope="col">Baseline</th>
            <th scope="col">Result</th><th scope="col">Interval</th><th scope="col">Pass or miss</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-testid="eval-row" data-verdict={r.verdict}>
              <th scope="row">
                {r.metric}
                <div className="label">{SETTING_LABEL[r.setting] ?? r.setting}; {r.better} is better{r.primary ? "; primary claim" : ""}</div>
              </th>
              <td>{r.task}</td>
              <td><OriginTag origin={r.origin} /></td>
              <td className="num">{r.baseline}</td>
              <td className="num">{r.result}</td>
              <td className="num">{r.interval}</td>
              <td>
                <b data-testid="verdict">{r.verdict === "pass" ? "Pass" : "Miss"}</b>
                <div className="label">{r.verdict_detail}</div>
                {r.named_miss ? <div className="label" data-testid="named-miss">Named as a miss in the S2 log.</div> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Every evaluation set in the plan, with its status. "not computed" is shown in words, never as a number. */
export function SetsTable({ sets }: { sets: EvalSet[] }) {
  return (
    <div className="p-scroll" tabIndex={0} role="region" aria-label="Evaluation sets">
      <table className="p-table" data-testid="set-table">
        <thead>
          <tr>
            <th scope="col">Set</th><th scope="col">Origin</th><th scope="col">Task</th><th scope="col">Status</th><th scope="col">Reason</th>
          </tr>
        </thead>
        <tbody>
          {sets.map((st) => (
            <tr key={st.id} data-testid="set-row" data-status={st.status}>
              <th scope="row">{st.id}: {st.name}</th>
              <td><OriginTag origin={st.origin} /></td>
              <td>{st.task}</td>
              <td><b data-testid="set-status">{st.status}</b></td>
              <td className="label">{st.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The E3 rows. The verdict is printed as text and the detail says which part of the rule failed. */
export function E3Table({ rows }: { rows: SetRow[] }) {
  return (
    <div className="p-scroll" tabIndex={0} role="region" aria-label="E3 mastery recovery results">
      <table className="p-table" data-testid="e3-table">
        <thead>
          <tr>
            <th scope="col">Setting</th><th scope="col">Baseline: raw share correct</th><th scope="col">Estimate (engine)</th>
            <th scope="col">Interval</th><th scope="col">Pre-registered verdict</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-testid="e3-row" data-verdict={r.verdict}>
              <th scope="row">{r.setting}</th>
              <td className="num">{r.baseline}</td>
              <td className="num">{r.result}</td>
              <td className="num">{r.interval}</td>
              <td>
                <b data-testid="e3-verdict">{r.verdict === "pass" ? "Pass" : r.verdict === "miss" ? "Miss" : "Descriptive"}</b>
                <div className="label">{r.detail}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EvaluationView() {
  const r = useResource(getEvaluation, "evaluation");
  const head = <PageHead title="Evaluation" sub="Every evaluation set in the plan is listed. A set is computed only when its result file exists; otherwise it reads not computed. Misses are shown the same way as passes." />;
  if (r.status === "loading") return <>{head}<Loading what="the results" /></>;
  if (r.status === "error") return <>{head}<ErrorState error={r.error} onRetry={r.reload} /></>;
  const ev: Evaluation = r.data;
  const e3 = ev.sets.find((x) => x.id === "E3");
  return (
    <>
      {head}
      <p className="label">None of this is evidence that the adaptive path improves learning for real students. No [PUB] or [EXP] result is shown unless its result file exists; until then those sets read not computed.</p>
      <Card title="Evaluation sets" origins={["SIM", "PUB", "EXP"]}>
        <SetsTable sets={ev.sets} />
      </Card>
      {ev.runs.map((run) => {
        const rows = ev.rows.filter((x) => x.run === run.id);
        return (
          <Card key={run.id} title={run.title} origins={["SIM"]}>
            <p className="muted">{run.note}</p>
            {rows.length > 0
              ? <ResultsTable rows={rows} />
              : <p className="label" data-testid="not-computed">not computed: the result file for this run is missing or unreadable.</p>}
          </Card>
        );
      })}
      <Card title="E3: mastery recovery on simulated learners" origins={["SIM"]}>
        <p className="muted">{e3?.task}</p>
        {e3?.status === "computed"
          ? <E3Table rows={e3.rows} />
          : <p className="label" data-testid="not-computed">not computed: {e3?.reason}</p>}
      </Card>
    </>
  );
}
