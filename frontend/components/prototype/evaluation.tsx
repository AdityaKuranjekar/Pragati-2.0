import { NOT_RUN, RESULTS } from "@/lib/prototype/results";
import { Card, OriginTag } from "./frame";

export function ResultsTable() {
  return (
    <div className="p-stack">
      <Card title="Results so far">
        <div className="p-scroll" tabIndex={0} aria-label="Results table, scrolls sideways">
          <table className="p-rtable">
            <thead>
              <tr>
                <th scope="col">What was tested</th>
                <th scope="col">Data</th>
                <th scope="col">Compared with</th>
                <th scope="col">Result</th>
                <th scope="col">Uncertainty</th>
                <th scope="col">Target</th>
                <th scope="col">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {RESULTS.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.test}
                    <span className="note">{r.how}</span>
                    <span className="note">{r.note}</span>
                  </td>
                  <td><OriginTag origin={r.origin} /></td>
                  <td className="num">{r.comparedWith}</td>
                  <td className="num"><strong>{r.result}</strong></td>
                  <td className="num">{r.uncertainty}</td>
                  <td>{r.target}</td>
                  <td>{r.verdict}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Not tested yet">
        <table className="p-gtable stack">
          <thead>
            <tr>
              <th scope="col">Question</th>
              <th scope="col">Data</th>
              <th scope="col">Why not yet</th>
            </tr>
          </thead>
          <tbody>
            {NOT_RUN.map((n) => (
              <tr key={n.id}>
                <th scope="row" style={{ minWidth: 0, fontWeight: 400 }}>{n.question}</th>
                <td data-label="Data"><OriginTag origin={n.origin} /></td>
                <td data-label="Why not yet">{n.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <p className="small muted" style={{ maxWidth: "75ch" }}>
        These are the results recorded in the repository from earlier work, shown as recorded. Each row tests something different, so the scores are not combined or compared with each other.
        None of them shows that learners learn more, and none comes from JEE learners.
      </p>
    </div>
  );
}
