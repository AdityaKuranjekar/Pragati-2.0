"use client";

import { Camera, FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { Card, CardTitle, Note, Origin, PageHead } from "@/components/ui";
import { useApp, useData } from "@/lib/app-context";
import { cn } from "@/lib/utils";
import { IngestPanel } from "./ingest-panel";
import { OmrPanel } from "./omr-panel";

export default function CapturePage() {
  const { L } = useApp();
  const dc = useData("datacard");
  const [tab, setTab] = useState<"file" | "omr">("file");
  const clean = dc.data?.cleaning;

  return (
    <div className="space-y-6">
      <PageHead sub={L("Upload a spreadsheet or a photo of an OMR sheet. You check the column match and any problem rows before anything is saved.", "स्प्रेडशीट या OMR शीट की फ़ोटो अपलोड करें। कुछ भी सहेजने से पहले आप कॉलम मिलान और समस्या वाली पंक्तियाँ जाँचते हैं।")} />
      <div role="tablist" aria-label={L("Source", "स्रोत")} className="flex gap-2">
        {([["file", FileSpreadsheet, "Spreadsheet", "स्प्रेडशीट"], ["omr", Camera, "OMR photo", "OMR फ़ोटो"]] as const).map(([id, Icon, en, hi]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn("inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-colors", tab === id ? "border-brand bg-brand-soft text-brand-dark" : "border-line bg-white text-ink-soft hover:bg-bg")}
          >
            <Icon size={16} /> {L(en, hi)}
          </button>
        ))}
      </div>
      {tab === "file" ? <IngestPanel /> : <OmrPanel />}

      {clean && (clean.examples ?? []).length > 0 && (
        <Card>
          <CardTitle right={<Origin origin="synthetic" />}>{L("Example of name cleaning", "नाम सफ़ाई का उदाहरण")}</CardTitle>
          <div className="grid gap-2 sm:grid-cols-2">
            {clean.examples.map((e, i) => (
              <div key={i} className="flex items-center justify-between rounded-xl border border-line px-3 py-2 text-sm">
                <code className="text-ink-soft line-through">{e.raw}</code>
                <span>→</span>
                <code className="font-medium text-[#087f5b]">{e.clean}</code>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-ink-soft">{L("Illustrative examples only; a measured cleaning rate was not computed in this build.", "केवल उदाहरण; इस संस्करण में सफ़ाई की मापी गई दर नहीं निकाली गई।")}</p>
        </Card>
      )}
    </div>
  );
}
