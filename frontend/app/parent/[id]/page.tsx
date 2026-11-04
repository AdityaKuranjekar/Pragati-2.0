"use client";
import { PersonPage } from "@/components/person-page";
export default function ParentPage({ params }: { params: { id: string } }) {
  return <PersonPage kind="parent" id={params.id} />;
}
