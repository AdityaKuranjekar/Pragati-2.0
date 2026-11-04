"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useApp } from "@/lib/app-context";
import { useRoster } from "@/lib/views";
import { EmptyState } from "./flair";
import { ParentView } from "./parent-view";
import { StudentView } from "./student-view";
import { StudentPicker } from "./pickers";
import { PageHead, PageSkeleton, Unavailable } from "./ui";

/** Student or parent page: a searchable picker, then that one student's own view (no peers, no batch data). */
export function PersonPage({ kind, id }: { kind: "student" | "parent"; id?: string }) {
  const { L, sel, setStudent } = useApp();
  const router = useRouter();
  const roster = useRoster();
  const people = roster.people;
  const wanted = id && id !== "_" ? id : sel.studentId;
  const current = people.find((p) => p.id === wanted)?.id ?? (id && id !== "_" ? id : people[0]?.id) ?? null;

  // remember what is on screen so the other pages open on the same student
  useEffect(() => {
    if (current && current !== sel.studentId && people.some((p) => p.id === current)) setStudent(current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, people.length]);

  const pick = (pid: string) => {
    setStudent(pid);
    router.push(`/${kind}/${pid}`);
  };

  const sub =
    kind === "student"
      ? L("What this student sees: their own progress and a small plan. No ranks, no comparison.", "यह विद्यार्थी क्या देखता है: अपनी प्रगति और छोटी योजना। कोई रैंक या तुलना नहीं।")
      : L("What this family sees: the WhatsApp message, simple progress, and what to do at home.", "यह परिवार क्या देखता है: WhatsApp संदेश, सरल प्रगति और घर पर क्या करें।");
  return (
    <div className="space-y-5">
      <PageHead sub={sub} right={<StudentPicker value={current} onPick={pick} label={kind === "student" ? L("Find a student", "विद्यार्थी खोजें") : L("Find a child", "बच्चा खोजें")} />} />
      {roster.loading ? (
        <PageSkeleton />
      ) : roster.error && people.length === 0 ? (
        <Unavailable what={L("students", "विद्यार्थी")} detail={roster.error} status={roster.status} onRetry={roster.reload} />
      ) : !current ? (
        <EmptyState title={L("No students yet", "अभी कोई विद्यार्थी नहीं")}>{L("Add a student list under Add data.", "डेटा जोड़ें में विद्यार्थी सूची जोड़ें।")}</EmptyState>
      ) : kind === "student" ? (
        <StudentView key={current} id={current} />
      ) : (
        <ParentView key={current} id={current} />
      )}
    </div>
  );
}
