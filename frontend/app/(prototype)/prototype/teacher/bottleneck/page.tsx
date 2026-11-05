import Link from "next/link";
import { BottleneckView } from "@/components/prototype/teacher";
import { PageHead } from "@/components/prototype/frame";

export default function BottleneckPage() {
  return (
    <>
      <p className="small" style={{ marginBottom: 8 }}><Link href="/prototype/teacher">Back to class overview</Link></p>
      <PageHead title="Where learners get stuck" sub="The topic most learners need to work on first, how the topics connect, and which links a teacher has reviewed." />
      <BottleneckView />
    </>
  );
}
