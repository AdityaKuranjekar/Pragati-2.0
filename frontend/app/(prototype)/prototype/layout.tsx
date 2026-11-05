import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Footer, TopBar } from "@/components/prototype/frame";
import "./prototype.css";

export const metadata: Metadata = { title: "Pragati 2.0 prototype", description: "Adaptive learning path prototype, demo data" };

export default function PrototypeLayout({ children }: { children: ReactNode }) {
  return (
    <div className="proto">
      <a href="#main" className="sr-only">Skip to content</a>
      <TopBar />
      <main id="main" className="p-main">{children}</main>
      <footer className="p-foot"><Footer /></footer>
    </div>
  );
}
