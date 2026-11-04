"use client";
import { PersonPage } from "@/components/person-page";
export default function StudentPage({ params }: { params: { id: string } }) {
  return <PersonPage kind="student" id={params.id} />;
}
