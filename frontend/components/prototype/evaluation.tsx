"use client";
import { getEvaluation } from "@/lib/prototype/client";
import type { EvalRow, Evaluation } from "@/lib/prototype/schemas";
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

export function EvaluationView() {
  const r = useResource(getEvaluation, "evaluation");
  const head = <PageHead title="Evaluation" sub="Every row is a simulation result [SIM] compared with the fixed-path baseline, read against the pre-registered decision rule. Misses are shown the same way as passes." />;
  if (r.status === "loading") return <>{head}<Loading what="the results" /></>;
  if (r.status === "error") return <>{head}<ErrorState error={r.error} onRetry={r.reload} /></>;
  const ev: Evaluation = r.data;
  if (ev.rows.length === 0) return <>{head}<Empty title="No results">The result files contain no rows.</Empty></>;
  return (
    <>
      {head}
      <p className="label">None of this is evidence that the adaptive path improves learning for real students. No public-dataset [PUB] or expert-label [EXP] result is shown here because none is computed by this build.</p>
      {ev.runs.map((run) => (
        <Card key={run.id} title={run.title} origins={["SIM"]}>
          <p className="muted">{run.note}</p>
          <ResultsTable rows={ev.rows.filter((x) => x.run === run.id)} />
        </Card>
      ))}
    </>
  );
}
