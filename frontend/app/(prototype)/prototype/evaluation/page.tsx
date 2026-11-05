import { ResultsTable } from "@/components/prototype/evaluation";
import { PageHead } from "@/components/prototype/frame";

export default function EvaluationPage() {
  return (
    <>
      <PageHead title="How well does it work?" sub="Every result so far, including the ones that fall short of their target. A result below its target is shown the same way as one that meets it." />
      <ResultsTable />
    </>
  );
}
