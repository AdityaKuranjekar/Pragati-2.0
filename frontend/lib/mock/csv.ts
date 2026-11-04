// Small CSV reader and column matcher for the mock ingest endpoints (server side only).
export function parseCsv(text: string): string[][] {
  const t = text.replace(/^﻿/, "");
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let q = false;
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (q) {
      if (c === '"' && t[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') q = false;
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === "," || c === "\t") {
      row.push(cell);
      cell = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && t[i + 1] === "\n") i++;
      row.push(cell);
      cell = "";
      if (row.some((x) => x.trim() !== "")) rows.push(row);
      row = [];
    } else cell += c;
  }
  row.push(cell);
  if (row.some((x) => x.trim() !== "")) rows.push(row);
  return rows;
}

export type Kind = "students" | "attendance" | "fees" | "results" | "answer-key";
export const KINDS: Kind[] = ["students", "attendance", "fees", "results", "answer-key"];

export type Target = { id: string; required: boolean; label_en: string; label_hi: string; synonyms: string[] };
const T = (id: string, required: boolean, label_en: string, label_hi: string, synonyms: string[]): Target => ({ id, required, label_en, label_hi, synonyms });

const ROLL = T("roll_no", true, "Roll number", "रोल नंबर", ["roll_no", "roll no", "roll", "rollno", "roll number", "r no", "enrollment", "id", "रोल नंबर", "रोल"]);
// Targets follow contracts/csv_templates/*.csv.
export const TARGETS: Record<Kind, Target[]> = {
  students: [ROLL, T("name", true, "Student name", "विद्यार्थी का नाम", ["name", "student name", "student", "full name", "नाम", "विद्यार्थी"]), T("dob", false, "Date of birth", "जन्म तिथि", ["dob", "date of birth", "birth date", "जन्म तिथि"]), T("class_level", false, "Class", "कक्षा", ["class level", "class", "कक्षा"]), T("exam", false, "Exam", "परीक्षा", ["exam", "target exam", "परीक्षा"]), T("batch_name", false, "Batch", "बैच", ["batch", "batch name", "section", "बैच"])],
  attendance: [ROLL, T("attendance_date", false, "Date", "तिथि", ["date", "attendance date", "day", "तिथि"]), T("present_flag", false, "Present (yes/no)", "उपस्थित (हाँ/नहीं)", ["present", "present flag", "status", "p/a", "उपस्थित"]), T("attendance_pct", false, "Attendance %", "उपस्थिति %", ["attendance", "attendance %", "attendance pct", "att%", "att %", "present %", "present pct", "percentage", "% present", "उपस्थिति"])],
  fees: [ROLL, T("amount_paise", true, "Amount due (paise)", "देय राशि (पैसे)", ["amount paise", "amount", "fee", "fees", "due", "amount due", "देय"]), T("instalment_no", false, "Instalment", "किस्त", ["instalment no", "installment", "instalment", "किस्त"]), T("due_date", false, "Due date", "देय तिथि", ["due date", "installment date", "देय तिथि"]), T("paid_amount_paise", false, "Paid (paise)", "भुगतान (पैसे)", ["paid amount paise", "paid", "received", "भुगतान"]), T("paid_date", false, "Paid date", "भुगतान तिथि", ["paid date", "payment date", "भुगतान तिथि"])],
  results: [ROLL, T("test_name", true, "Test", "टेस्ट", ["test name", "test", "test id", "exam name", "टेस्ट"]), T("raw_score", true, "Marks", "अंक", ["raw score", "marks", "score", "total", "marks obtained", "अंक"]), T("test_date", false, "Test date", "टेस्ट तिथि", ["test date", "date", "टेस्ट तिथि"]), T("absent_flag", false, "Absent", "अनुपस्थित", ["absent flag", "absent", "ab", "अनुपस्थित"])],
  "answer-key": [T("question_no", true, "Question number", "प्रश्न संख्या", ["question no", "q no", "qno", "question", "q", "q.no", "प्रश्न"]), T("accepted_answers", true, "Correct answer", "सही उत्तर", ["accepted answers", "answer", "key", "correct", "correct option", "ans", "उत्तर", "सही उत्तर"]), T("topic_id", false, "Topic", "विषय", ["topic id", "topic", "chapter", "विषय"]), T("subject", false, "Subject", "विषय (सब्जेक्ट)", ["subject", "सब्जेक्ट"])],
};
/** At least one of these must be mapped. */
export const ONE_OF: Partial<Record<Kind, string[]>> = { attendance: ["present_flag", "attendance_pct"] };

const norm = (s: string) => s.toLowerCase().replace(/[_\-.]+/g, " ").replace(/\s+/g, " ").trim();

function similarity(a: string, b: string): number {
  if (a === b) return 1;
  if (a.includes(b) || b.includes(a)) return Math.min(a.length, b.length) / Math.max(a.length, b.length) * 0.4 + 0.5;
  // character bigram overlap
  const bg = (s: string) => new Set(Array.from({ length: Math.max(0, s.length - 1) }, (_, i) => s.slice(i, i + 2)));
  const A = bg(a);
  const B = bg(b);
  if (!A.size || !B.size) return 0;
  let n = 0;
  A.forEach((x) => B.has(x) && n++);
  return (2 * n) / (A.size + B.size);
}

export type ColumnGuess = { source: string; target: string | null; confidence: number; alternatives: { target: string; confidence: number }[] };

/** Greedy best match per source column; each target is used at most once. */
export function guessMapping(kind: Kind, headers: string[]): ColumnGuess[] {
  const targets = TARGETS[kind];
  const scores = headers.map((h) =>
    targets
      .map((t) => ({ target: t.id, confidence: Math.max(...t.synonyms.map((s) => similarity(norm(h), norm(s)))) }))
      .sort((a, b) => b.confidence - a.confidence)
  );
  const used = new Set<string>();
  const out: ColumnGuess[] = headers.map((h, i) => ({ source: h, target: null, confidence: 0, alternatives: scores[i].filter((s) => s.confidence >= 0.3).slice(0, 3).map((s) => ({ ...s, confidence: +s.confidence.toFixed(2) })) }));
  const order = scores.map((s, i) => ({ i, c: s[0]?.confidence ?? 0 })).sort((a, b) => b.c - a.c);
  for (const { i } of order) {
    const best = scores[i].find((s) => !used.has(s.target) && s.confidence >= 0.55);
    if (best) {
      used.add(best.target);
      out[i].target = best.target;
      out[i].confidence = +best.confidence.toFixed(2);
    }
  }
  return out;
}
