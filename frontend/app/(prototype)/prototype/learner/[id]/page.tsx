import { notFound } from "next/navigation";
import { LearnerView } from "@/components/prototype/learner";
import { PageHead } from "@/components/prototype/frame";
import { FIXTURES } from "@/lib/prototype/data";

export const dynamicParams = false;
export function generateStaticParams() {
  return FIXTURES.map((l) => ({ id: l.id }));
}

export default function LearnerPage({ params }: { params: { id: string } }) {
  if (!FIXTURES.some((l) => l.id === params.id)) notFound();
  return (
    <>
      <PageHead title="Learner view" sub="What this learner should do next and why, then how each topic is going." />
      <LearnerView id={params.id} />
    </>
  );
}
