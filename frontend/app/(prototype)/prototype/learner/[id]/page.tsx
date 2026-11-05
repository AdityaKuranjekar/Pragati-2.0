"use client";
import { LearnerScreen } from "@/components/prototype/learner";
export default function Page({ params }: { params: { id: string } }) {
  return <LearnerScreen learnerId={params.id} />;
}
