import Link from "next/link";
import { BottleneckView } from "@/components/prototype/teacher";
import { PageHead } from "@/components/prototype/frame";

export default function BottleneckPage() {
  return (
    <>
      <p className="small" style={{ marginBottom: 8 }}><Link href="/prototype/teacher">Back to cohort overview</Link></p>
      <PageHead title="Bottleneck" sub="The concept that most often comes first for learners in this cohort, the prerequisite edges involved, and their review state." />
      <BottleneckView />
    </>
  );
}
