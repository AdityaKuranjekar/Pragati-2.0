import { NOT_RUN, RESULTS } from "@/lib/prototype/results";
import { Card, OriginTag } from "./frame";

export function ResultsTable() {
  return (
    <div className="p-stack">
      <Card title="Recorded results">
        <div className="p-scroll" tabIndex={0} aria-label="Results table, scrolls sideways">
          <table className="p-rtable">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Task</th>
                <th scope="col">Origin</th>
                <th scope="col">Baseline</th>
                <th scope="col">Result</th>
                <th scope="col">95% CI</th>
                <th scope="col">Bar</th>
                <th scope="col">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {RESULTS.map((r) => (
                <tr key={r.id}>
                  <td>{r.metric}</td>
                  <td>
                    {r.task}
                    <span className="note">{r.note}</span>
                  </td>
                  <td>
                    <OriginTag origin={r.origin} />
                    {r.origin === "PUB" && <span className="note">public dataset</span>}
                  </td>
                  <td className="num">{r.baseline}</td>
                  <td className="num">{r.result}</td>
                  <td className="num">{r.ci}</td>
                  <td>{r.bar}</td>
                  <td>{r.outcome}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Not run yet">
        <table className="p-gtable">
          <thead>
            <tr>
              <th scope="col">Set</th>
              <th scope="col">Task</th>
              <th scope="col">Origin</th>
              <th scope="col">Reason</th>
            </tr>
          </thead>
          <tbody>
            {NOT_RUN.map((n) => (
              <tr key={n.id}>
                <th scope="row" style={{ minWidth: 0 }}>{n.set}</th>
                <td>{n.task}</td>
                <td><OriginTag origin={n.origin} /></td>
                <td>{n.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <p className="small muted" style={{ maxWidth: "75ch" }}>
        Figures are those recorded in the repository from the earlier work, shown as recorded. Each row is a different task and origin, so no row is combined with another.
        None of these results measures learning gain, and none comes from JEE learners. Re-runs under the pre-registered protocol are pending.
      </p>
    </div>
  );
}
