"use client";

import { Search } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useApp } from "@/lib/app-context";
import { useBatchChoice, useRoster, type Person } from "@/lib/views";
import { cn } from "@/lib/utils";
import { Select } from "./ui";

/** Batch chooser; the choice is remembered per institute. */
export function BatchPicker({ onChange }: { onChange?: (id: string) => void }) {
  const { L } = useApp();
  const { batches, batch, setBatch } = useBatchChoice();
  if (batches.length === 0) return null;
  return (
    <Select
      label={L("Batch", "बैच")}
      value={batch?.id ?? ""}
      onChange={(v) => {
        setBatch(v);
        onChange?.(v);
      }}
      options={batches.map((b) => ({ value: b.id, label: b.name }))}
    />
  );
}

/**
 * Searchable student chooser: type a name or roll number. Always alphabetical, never by performance.
 * `value` is the current student id; `onPick` gets the new one.
 */
export function StudentPicker({ value, onPick, label }: { value: string | null; onPick: (id: string) => void; label?: string }) {
  const { L } = useApp();
  const { people, byId, loading } = useRoster();
  const { batches } = useBatchChoice();
  const [q, setQ] = useState("");
  const [batchId, setBatchId] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const listId = useId();
  const current = value ? byId.get(value) : undefined;

  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return people.filter((p) => (!batchId || p.batchId === batchId) && (!s || p.name.toLowerCase().includes(s) || p.roll.toLowerCase().includes(s))).slice(0, 60);
  }, [people, q, batchId]);

  useEffect(() => setActive(0), [q, batchId]);
  useEffect(() => {
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const pick = (p: Person) => {
    onPick(p.id);
    setQ("");
    setOpen(false);
  };

  return (
    <div ref={box} className="relative flex flex-wrap items-end gap-2" data-testid="student-picker">
      {batches.length > 1 && (
        <Select label={L("Batch", "बैच")} value={batchId} onChange={setBatchId} options={[{ value: "", label: L("All batches", "सभी बैच") }, ...batches.map((b) => ({ value: b.id, label: b.name }))]} />
      )}
      <div className="relative w-full min-w-[220px] flex-1 sm:w-80 sm:flex-none">
        <label htmlFor={`${listId}-in`} className="sr-only">
          {label ?? L("Find a student by name or roll number", "नाम या रोल नंबर से विद्यार्थी खोजें")}
        </label>
        <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-mute" />
        <input
          id={`${listId}-in`}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
          data-testid="student-search"
          value={open ? q : current ? `${current.name} · ${current.roll}` : q}
          placeholder={loading ? L("Loading students…", "विद्यार्थी लोड हो रहे हैं…") : L("Search name or roll number", "नाम या रोल नंबर खोजें")}
          onFocus={(e) => {
            setOpen(true);
            e.currentTarget.select();
          }}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setOpen(true);
              setActive((a) => Math.min(a + 1, shown.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && open && shown[active]) {
              e.preventDefault();
              pick(shown[active]);
            } else if (e.key === "Escape") setOpen(false);
          }}
          className="min-h-[44px] w-full rounded-xl border border-line bg-white py-2 pl-9 pr-3 text-[15px] text-ink"
        />
        {open && (
          <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-line bg-white py-1 shadow-soft">
            {shown.length === 0 ? (
              <li className="px-3 py-3 text-sm text-ink-soft">{loading ? L("Loading…", "लोड हो रहा है…") : L("No student matches.", "कोई विद्यार्थी नहीं मिला।")}</li>
            ) : (
              shown.map((p, i) => (
                <li
                  key={p.id}
                  role="option"
                  aria-selected={p.id === value}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    pick(p);
                  }}
                  onMouseEnter={() => setActive(i)}
                  className={cn("flex min-h-[44px] cursor-pointer items-center justify-between gap-2 px-3 py-2 text-[15px]", i === active && "bg-brand-soft", p.id === value && "font-semibold")}
                >
                  <span className="truncate">{p.name}</span>
                  <span className="shrink-0 text-xs text-ink-mute">{p.roll}</span>
                </li>
              ))
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
