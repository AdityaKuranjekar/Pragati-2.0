import { CohortSummary, ConceptHeatmap } from "@/components/prototype/teacher";
import { PageHead } from "@/components/prototype/frame";

export default function TeacherPage() {
  return (
    <>
      <PageHead title="Class overview" sub="How learners are doing on each topic in the demo chain. Start with the whole group; switch to each learner when you need detail." />
      <div className="p-stack">
        <CohortSummary />
        <ConceptHeatmap />
      </div>
    </>
  );
}
