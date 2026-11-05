# Research prompts (Pragati 2.0)

**Status:** every external fact in the Pragati 2.0 plan is **unverified** until a primary source is checked and the result is recorded in the "Findings" column of the register below. Per `CLAUDE.md` §4: never guess an external fact. Each prompt below is self-contained, so it can be pasted into a cloud or local session without this conversation.

**Rules for every research session**
1. Use primary sources first (official gazette, NTA/CET board sites, dataset pages, licence files in the repo). Secondary commentary is a lead, not evidence.
2. For every claim record: source URL, access date, quoted wording (short), and a confidence tag (`verified`, `secondary-only`, `not found`).
3. Write results to `docs/pragati-2.0/research/findings/<ID>.md`. Do not paste raw copyrighted text; paraphrase and link.
4. Do not download datasets or question papers in a research session. Read the licence page only.
5. End with a list of what is still unverified and what would settle it.

---

## Register

| ID | Topic | Blocks | Priority | Status |
|---|---|---|---|---|
| R1 | DPDP Act 2023 s.9 and DPDP Rules 2025 for coaching-institute learning analytics on minors | Phase 2 features, Phase 3 teacher views, pilot | P0 (blocker) | Partly checked: secondary sources only |
| R2 | Licence and terms for every dataset and content source | Phase 1, Phase 4, any redistribution | P0 | Partly checked: ASSISTments terms not found |
| R3 | Exam scope: JEE Main, JEE Advanced, state CETs, Olympiads (syllabi and patterns) | Phase 0 scope, Phase 1 curriculum, schema | P0 | Not started |
| R4 | DataNova Global Data-thon 2026 rules, judging criteria and deadlines | Phase 5, all priorities | P0 | Not started (no source in repo) |
| R5 | Prior art: knowledge tracing, prerequisite graphs, collaborative filtering in education | Phase 2 method choice, related work | P1 | Not started |
| R6 | Market facts: exam registrations, coaching-institute landscape, pricing comparables | Pitch, Phase 6 | P1 | Not started |
| R7 | Hosting free-tier limits (Vercel, Render, Neon, Supabase, Firebase) | Phase 5 demo reliability | P1 | Not started |
| R8 | Adaptive-learning evaluation designs and effect-size priors | Phase 4 sample sizes | P1 | Not started |
| R9 | Hindi and NCERT terminology review process | Phase 1, Phase 3 bilingual UI | P2 | Not started |
| R10 | Olympiad and international-competition scope and its legal content position | Scope decision | P2 | Not started |

---

## R1: DPDP Act and minors (blocker)

**Question.** Does Section 9(3) of the Digital Personal Data Protection Act, 2023 prohibit (a) per-question correctness logs, (b) response-time and hint-use features, and (c) a "needs support" list generated from them, when the data subject is a Class 11 or 12 student aged under 18 at a coaching institute? Which exemption in the Fourth Schedule of the DPDP Rules, 2025 (if any) applies to an educational institution, and does it cover a private coaching centre? What are the exact conditions, and what does "behavioural monitoring" mean in the Act or the Rules?

**Why it matters.** The current plan (Phase 2 §2 and §4) uses response time and hint dependency. `contracts/routing_policy.yaml` already gates ML risk for minors (rule rationale cites DPDP s.9(3)). The pilot cannot start until this is answered.

**Primary sources to check.**
- The Digital Personal Data Protection Act, 2023 (Gazette / MeitY), s.9 and s.2 definitions ("child", "data fiduciary", "significant").
- The Digital Personal Data Protection Rules, 2025: Rule 10 (verifiable consent), Rule 12 and the Fourth Schedule (exemptions).
- Any MeitY FAQ or notification on commencement date.

**Secondary leads already found (verify, do not cite as law):** commentary says s.9(3) bars tracking or behavioural monitoring of children; commentary says the Fourth Schedule allows educational institutions to track children under conditions; one source gives 13 May 2027 as the commencement date. None was checked against the Gazette.

**Output.** A one-page memo with: quoted s.9(1) and s.9(3); the Fourth Schedule clause (quoted); a yes/no/unclear answer for (a), (b), (c) and for a coaching institute; the exact conditions; commencement date; the questions only a lawyer can answer. Mark the memo "not legal advice; for counsel review".

---

## R2: Dataset and content licences

**Question.** For each source below, what are the current licence and terms (use, research, commercial, redistribution, attribution, retention)?

| Source | Pragati use | Known so far |
|---|---|---|
| ASSISTments 2009-2010 Skill Builder | KT benchmark (server-side only) | No explicit licence found; IEEE DataPort copies have blank licence fields. Repo note says "free for research, no explicit licence". |
| OULAD (Open University) | Retention experiment (not mastery) | Repo cites CC BY 4.0. Verify on the official page and keep the citation. |
| JEEBench (Arora et al., EMNLP 2023) | Tagging evaluation text | Repo cites MIT. Verify the licence file in the repository and any question-level rights notice. |
| EdNet (riiid) | Optional, later | Unknown |
| PSLC DataShop collections | Optional | Per-collection terms |
| OpenStax | Resource mapping | Licence varies per book (CC BY is common). Verify per title. |
| NCERT books and Exemplar | Curriculum reference and items | Copyright notice on NCERT site. Establish what may be reused as a reference, paraphrased, or quoted. |
| NTA JEE Main and Advanced papers and solutions | Items | Official notice terms; establish reuse rights and whether the answer keys are public. |
| State CET past papers | Items | Per-board terms |

**Output.** One table per source with: licence name and version, URL and access date, permitted purposes, redistribution (yes/no/unclear), attribution text, and a "safe to use in a public demo?" flag. Update `contracts/datasets.yaml` only after a human reviews the findings.

---

## R3: Exam scope (JEE Main, JEE Advanced, state CETs, Olympiads)

**Question.** For the 2026 cycle:
1. JEE Main: official syllabus, pattern (sections, marks, negative marking), and whether the NTA notice used in `contracts/exam_patterns.yaml` (`Notice_20260120102259.pdf`) says what the repo says.
2. JEE Advanced: syllabus, paper pattern and any differences from Main.
3. State CETs: which states have a CET that is PCM-based for Class 11 and 12 entrants? For each shortlisted state (suggest 2 to 3 with the largest test-taker counts), give exam name, conducting body, syllabus document, pattern and the official URL.
4. Olympiads: which Indian olympiads and international olympiads (for example IOQM, RMO, INMO, and the international physics, chemistry and maths olympiads) have published syllabi, and which are open to Class 11 and 12 students in India?

**Why it matters.** `contracts/topics.yaml` and the DB CHECK `topics.exam IN ('jee_main','neet_ug')` do not cover JEE Advanced or CETs. A new exam value is a schema migration, which Phase 0 gates.

**Output.** A table per exam: syllabus URL, pattern, year, subjects, class level, and "in pilot scope?" recommendation. Recommend the smallest set that gives a credible story. Note that olympiad content is rare, cohorts are small, and content rights are unclear.

---

## R4: DataNova Global Data-thon 2026 (rules and judging)

**Question.** What are the official rules, eligibility, timeline, submission format, judging criteria and weights, and any requirements on code licence, data use, AI-tool disclosure, and presentation length for the "Adaptive Learning Path Recommendation" problem?

**Why it matters.** Phase 5 structure, the evaluation emphasis in Phase 4 and the pitch all depend on the judging rubric. The problem statement in the README comes from a secondary copy; the official page is not in the repo.

**Primary sources.** The DataNova Global Data-thon official page or the organiser's announcement. Record the exact deadline in IST and the submission portal.

**Output.** A rubric table (criterion, weight, what the judge looks for) and a deadline table. Flag any rule that conflicts with the repo's plan (for example, submitting a hosted demo, requiring a public dataset, or banning generative AI in a component).

---

## R5: Prior art for the method choices

**Question.** For each method below, give the primary paper, the reported result on a public benchmark, and the conditions under which it fails:
- Bayesian Knowledge Tracing (Corbett and Anderson 1994) and its known identifiability problems.
- Deep Knowledge Tracing (Piech et al. 2015) and critiques of its evaluation (for example on data leakage or on whether it beats BKT with tuned baselines).
- Rasch and hierarchical IRT for educational measurement; how the Rasch 1PL differs from 2PL in practice.
- Knowledge space theory and prerequisite-graph learning from data (Doignon and Falmagne; any recent work that learns prerequisites from response data).
- Collaborative filtering for learners and items (matrix factorisation, item-item similarity), with its cold-start problem.
- Graph algorithms for education: personalised PageRank or similar for finding bottleneck concepts; shortest-path or topological ordering for learning paths.
- Recent comparisons of KT models on ASSISTments with leakage-safe splits (for example pyKT).

**Output.** A related-work table. Note which results are on ASSISTments and which are not. Do not copy published numbers into the product claims unless they were reproduced under the same protocol.

---

## R6: Market facts (verify before use)

**Question.** From official or primary sources (not press releases): number of JEE Main and JEE Advanced registrants for the last two cycles; number of CET registrants for the states chosen in R3; number of registered coaching institutes or coaching-market figures, with the methodology behind them; typical coaching-fee ranges published by institutes (with source).

**Output.** A table with value, year, source, and a confidence tag. Mark any figure without a primary source as "do not use in pitch". Include the pitch claims that need one of these numbers.

---

## R7: Free-tier hosting limits

**Question.** For each service in the Phase 0 hosting plan, what are the current free-tier limits and terms that matter for a demo: Vercel (bandwidth, function duration, commercial-use rules), Render (web service sleep behaviour, cold-start time, instance hours), Neon and Supabase (database size, compute hours, pausing rules, connection limits), Firebase and Supabase Auth (monthly active user limits).

**Output.** A table with limit, value, source, date. Include a "what the demo needs" column (for example a 2-minute cold start is acceptable only with a visible loading state and a recorded backup).

---

## R8: Evaluation design and effect-size priors

**Question.** What effect sizes have been reported for adaptive practice or intelligent tutoring against fixed sequences in secondary-school or pre-university maths and physics (for example VanLehn 2011, meta-analyses of ITS and adaptive learning)? Give the typical effect size, the design, the sample size, and the cluster structure (class vs student). Also: typical intra-class correlation for student outcomes in Indian coaching batches, if any source reports it.

**Why it matters.** The pilot sample sizes in `EVAL_PLAN.md` assume d = 0.3 and ICC = 0.05. Both are placeholders until this is checked.

**Output.** A table of sources with effect size, design, and population. State which assumption in `EVAL_PLAN.md` each source supports or contradicts.

---

## R9: Hindi terminology and review

**Question.** What process does NCERT or the state board use for Hindi physics, chemistry and maths terminology? Which reference glossary is authoritative and freely accessible? How do existing review sheets in `contracts/topics_hi_review.csv` compare?

**Output.** Recommended glossary source, a reviewer checklist, and a proposed review protocol with a native-speaker sign-off step.

---

## R10: Olympiad and international scope

**Question.** Which international olympiads have an official syllabus, an official sample-paper policy, and a student eligibility rule that includes Indian Class 11 and 12 students? What rights status applies to their past problems? Is there any reason a small olympiad track is feasible in the pilot, or should it be deferred?

**Output.** Recommendation (include, defer or exclude) with reasons and the sources checked.

---

## Findings register

Filed 2026-11-05 in `findings/REPORT_2026-11-05.md`, which carries the verification status of every claim.

| ID | Status | Findings file | Still unverified |
|---|---|---|---|
| R1 | Fourth Schedule educational-institution exemption supported by secondary sources; processor and cross-tenant question open | `findings/REPORT_2026-11-05.md` | Gazette text, Rule 10/12 numbering, commencement date, whether a coaching centre qualifies, processor status |
| R2 | OpenStax NC-SA and EdNet NC confirmed; ASSISTments, OULAD, JEEBench, NCERT, NTA not confirmed | same | ASSISTments terms; OULAD and JEEBench licence files; NCERT and NTA reuse |
| R3 | Not verified | same | JEE Main/Advanced pattern details, EAPCET and WBJEE marking |
| R4 | **Not found.** Report's dates and rubric unsourced | same | Everything; obtain official page from owner |
| R5 | Literature matches memory; numeric ranges not verified | same | Benchmark figures |
| R6 | Deductions only; not used | same | Primary statistics |
| R7 | Deductions only | same | Provider pricing pages |
| R8 | d = 0.76 from memory; d = 0.3 and ICC 0.05 are assumptions | same | Source for ICC; effect-size priors |
| R9 | Plausible; not checked | same | CSTT use |
| R10 | Consistent with plan | same | Olympiad rights (not needed for the pilot) |
