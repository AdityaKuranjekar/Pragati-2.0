import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ResetDemo, StatusLine, TopBar } from "@/components/prototype/frame";
import "./prototype.css";

export const metadata: Metadata = { title: "Pragati 2.0 prototype", description: "Adaptive learning path prototype, demo data" };

export default function PrototypeLayout({ children }: { children: ReactNode }) {
  return (
    <div className="proto">
      <a href="#main" className="sr-only">Skip to content</a>
      <TopBar />
      <main id="main" className="p-main">{children}</main>
      <footer className="p-foot">
        <StatusLine />
        <p>Interface prototype. Figures come from demo fixtures, a seeded simulator and results recorded in the repository. The Pragati engine is not connected; estimates use a simple share-correct rule.</p>
        <ResetDemo />
      </footer>
    </div>
  );
}
