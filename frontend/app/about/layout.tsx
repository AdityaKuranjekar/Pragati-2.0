"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { EvidenceContext } from "@/components/ui";
import { useApp } from "@/lib/app-context";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/about", en: "How it works", hi: "यह कैसे काम करता है" },
  { href: "/about/data-card", en: "Data card", hi: "डेटा कार्ड" },
  { href: "/about/evidence", en: "Evidence", hi: "प्रमाण" },
];

/** Technical evidence lives here only: origin chips, model metrics, provenance. */
export default function AboutLayout({ children }: { children: ReactNode }) {
  const { L } = useApp();
  const path = usePathname() ?? "";
  return (
    <EvidenceContext.Provider value={true}>
      <div className="space-y-5">
        <nav aria-label={L("Evidence sections", "प्रमाण अनुभाग")} className="flex gap-2 overflow-x-auto">
          {TABS.map((t) => (
            <Link key={t.href} href={t.href} aria-current={path === t.href ? "page" : undefined} className={cn("min-h-[44px] whitespace-nowrap rounded-xl border px-4 py-2.5 text-[15px] font-medium", path === t.href ? "border-brand bg-brand-soft text-brand-dark" : "border-line bg-white text-ink-soft hover:bg-bg")}>
              {L(t.en, t.hi)}
            </Link>
          ))}
        </nav>
        {children}
      </div>
    </EvidenceContext.Provider>
  );
}
