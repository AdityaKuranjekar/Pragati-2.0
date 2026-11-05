import { CohortSummary, ConceptHeatmap } from "@/components/prototype/teacher";
import { PageHead } from "@/components/prototype/frame";

export default function TeacherPage() {
  return (
    <>
      <PageHead title="Cohort overview" sub="Concepts in the demo chain, by learner. Group view first; switch to Learner for individual cells." />
      <div className="p-stack">
        <CohortSummary />
        <ConceptHeatmap />
      </div>
    </>
  );
}
