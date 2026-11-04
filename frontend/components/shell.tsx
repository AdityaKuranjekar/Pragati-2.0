"use client";

import { BookOpen, Building2, GraduationCap, Home, LayoutGrid, Menu, ShieldCheck, Smartphone, Upload, Users, X, HeartHandshake } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useApp } from "@/lib/app-context";
import { INSTITUTES } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Logo } from "./flair";
import { Select, Skeleton } from "./ui";

type Item = { href: string; en: string; hi: string; icon: typeof Home; match?: string; exact?: boolean };
const TINT: Record<string, string> = { "/": "#edf2ff", "/add-data": "#fff9db", "/weak-topics": "#eef2ff", "/support": "#e6fcf5", "/students": "#e7f5ff", "/student": "#e7f5ff", "/parents": "#fff4e0", "/parent": "#fff4e0", "/results": "#f3f0ff", "/privacy": "#f4f1ec", "/about": "#f4f1ec" };
const GROUPS: { en: string; hi: string; items: Item[] }[] = [
  { en: "", hi: "", items: [{ href: "/", en: "Home", hi: "होम", icon: Home, exact: true }] },
  {
    en: "This week",
    hi: "इस सप्ताह",
    items: [
      { href: "/add-data", en: "Add data", hi: "डेटा जोड़ें", icon: Upload },
      { href: "/weak-topics", en: "Weak topics", hi: "कमज़ोर विषय", icon: LayoutGrid },
      { href: "/support", en: "Support list", hi: "सहयोग सूची", icon: HeartHandshake },
      { href: "/students", en: "Students", hi: "विद्यार्थी", icon: GraduationCap, match: "/student" },
      { href: "/parents", en: "Parents", hi: "अभिभावक", icon: Smartphone, match: "/parent" },
      { href: "/results", en: "Results", hi: "नतीजे", icon: Building2 },
    ],
  },
  {
    en: "Settings",
    hi: "सेटिंग",
    items: [{ href: "/privacy", en: "Privacy and consent", hi: "गोपनीयता और सहमति", icon: ShieldCheck }],
  },
  { en: "For judges", hi: "जजों के लिए", items: [{ href: "/about", en: "How it works and evidence", hi: "यह कैसे काम करता है और प्रमाण", icon: BookOpen, match: "/about" }] },
];
const ALL = GROUPS.flatMap((g) => g.items);

function Nav({ path, onGo }: { path: string; onGo?: () => void }) {
  const { L } = useApp();
  const active = (x: Item) => (x.exact ? path === x.href : path === x.href || path.startsWith(`${x.match ?? x.href}/`) || path.startsWith(x.match ?? x.href));
  return (
    <nav aria-label={L("Main", "मुख्य")} className="flex-1 space-y-4 overflow-y-auto px-3 pb-4">
      {GROUPS.map((g, gi) => (
        <div key={gi}>
          {g.en && <p className="mb-1 px-3 text-xs font-semibold uppercase tracking-wide text-ink-mute">{L(g.en, g.hi)}</p>}
          <ul className="space-y-1">
            {g.items.map((n) => (
              <li key={n.href}>
                <Link
                  href={n.href}
                  onClick={onGo}
                  aria-current={active(n) ? "page" : undefined}
                  className={cn(
                    "flex min-h-[44px] items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] transition-colors",
                    active(n) ? "bg-brand-soft font-semibold text-brand-dark" : "text-ink-soft hover:bg-bg"
                  )}
                >
                  <n.icon size={18} /> {L(n.en, n.hi)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { lang, setLang, institute, setInstitute, ready, L } = useApp();
  const path = usePathname() ?? "/";
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);
  const here = ALL.find((n) => (n.exact ? path === n.href : path.startsWith(n.match ?? n.href))) ?? ALL[0];
  const tint = TINT[path] ?? TINT["/" + (path.split("/")[1] ?? "")] ?? "#edf2ff";
  const inst = INSTITUTES.find((i) => i.id === institute)?.label ?? institute;

  const brand = (
    <Link href="/" className="flex items-center gap-2.5 px-5 py-5">
      <Logo size={38} />
      <span>
        <span className="block font-semibold leading-tight text-ink">Pragati</span>
        <span className="block text-xs leading-tight text-ink-mute">{inst}</span>
      </span>
    </Link>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-white focus:p-2">
        {L("Skip to content", "सामग्री पर जाएँ")}
      </a>

      {/* The one navigation: fixed sidebar on large screens, a drawer behind the menu button on phones */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-line bg-white lg:flex" data-testid="sidebar">
        {brand}
        <Nav path={path} />
        <p className="px-5 py-4 text-xs leading-snug text-ink-mute">{L("Demo data", "डेमो डेटा")}</p>
      </aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label={L("Menu", "मेन्यू")}>
          <button className="absolute inset-0 bg-ink/40" aria-label={L("Close menu", "मेन्यू बंद करें")} onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col bg-white shadow-soft">
            <div className="flex items-center justify-between pr-3">
              {brand}
              <button onClick={() => setOpen(false)} aria-label={L("Close menu", "मेन्यू बंद करें")} className="grid h-11 w-11 place-items-center rounded-xl text-ink-soft hover:bg-bg">
                <X size={20} />
              </button>
            </div>
            <Nav path={path} onGo={() => setOpen(false)} />
            <p className="px-5 py-4 text-xs text-ink-mute">{L("Demo data", "डेमो डेटा")}</p>
          </div>
        </div>
      )}

      <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-2 gap-y-2 px-4 py-2.5 sm:flex-nowrap sm:gap-3">
          <button onClick={() => setOpen(true)} aria-label={L("Open menu", "मेन्यू खोलें")} className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-line text-ink-soft hover:bg-bg lg:hidden" data-testid="menu-button">
            <Menu size={20} />
          </button>
          <h1 className="min-w-0 flex-1 basis-[50%] truncate text-lg font-semibold tracking-tight text-ink sm:basis-auto sm:text-xl" data-testid="page-title">
            {L(here.en, here.hi)}
          </h1>
          <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:justify-start sm:gap-3">
          <Select label={L("Institute", "संस्थान")} value={institute} onChange={setInstitute} options={INSTITUTES.map((i) => ({ value: i.id, label: i.label }))} />
          <div role="group" aria-label={L("Language", "भाषा")} className="flex shrink-0 rounded-xl border border-line p-0.5 text-sm">
            {(["en", "hi"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                aria-pressed={lang === l}
                className={cn("min-h-[40px] rounded-lg px-3 font-medium", lang === l ? "bg-brand text-white" : "text-ink-soft")}
              >
                {l === "en" ? "EN" : "हि"}
              </button>
            ))}
          </div>
          </div>
        </div>
      </header>
      <div style={{ background: `linear-gradient(180deg, ${tint} 0, rgba(250,248,245,0) 280px)` }}>
      <main id="main" className="mx-auto max-w-6xl px-4 py-6" aria-busy={!ready}>
        {ready ? (
          <div key={path} className="animate-page">{children}</div>
        ) : (
          <div className="space-y-4" role="status" aria-label={L("Loading", "लोड हो रहा है")}>
            <Skeleton className="h-10 w-1/3" />
            <Skeleton className="h-40" />
            <Skeleton className="h-64" />
          </div>
        )}
      </main>
      </div>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-ink-mute">
        <Users size={12} className="mr-1 inline" />
        {L("Demo data: all students shown here are synthetic.", "डेमो डेटा: यहाँ दिखाए गए सभी विद्यार्थी कृत्रिम हैं।")}
      </footer>
    </div>
  );
}
