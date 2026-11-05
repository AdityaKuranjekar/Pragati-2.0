import { ResultsTable } from "@/components/prototype/evaluation";
import { PageHead } from "@/components/prototype/frame";

export default function EvaluationPage() {
  return (
    <>
      <PageHead title="Evaluation" sub="Each result with its task, origin, baseline, interval and bar. A result that misses its bar is shown in the same way as one that meets it." />
      <ResultsTable />
    </>
  );
}
