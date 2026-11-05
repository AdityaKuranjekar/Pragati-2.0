# Prototype UI proposal

**Status:** proposal, 2026-11-05. Nothing in this file is implemented. Source of truth for direction, tokens, screens and tone: [`DESIGN_BRIEF.md`](DESIGN_BRIEF.md). Scope: the `/prototype` route in `frontend/`. The institute console does not change.

Sections follow the task: 1 inventory, 2 route structure, 3 screens, 4 tokens and contrast, 5 numbers and origin tags, 6 questions for the owner.

---

## 1. Inventory of `frontend/`

Next.js 14 App Router, Tailwind 3, `@fontsource-variable/inter` (self-hosted, so no new stylesheet source is needed). All existing pages are the Pragati 1.0 institute console, EN and HI, on mock data.

### 1.1 Entry points

| File | What it does | Decision |
|---|---|---|
| `app/layout.tsx` | Root layout: Inter and Noto Sans Devanagari, `globals.css`, wraps every route in `AppProvider` and `Shell` | **Leave alone**, with one open point (section 1.3 and question 1) |
| `app/globals.css` | Tailwind layers, one focus ring colour (`#3b5bdb`), `--tint`, `.card-lift` | **Leave alone.** Prototype tokens go in a separate file (section 4) |
| `tailwind.config.ts` | Console palette (`bg`, `ink`, `brand`, `teal`, `amber`, `calm`, `tint`), 14px and 20px radii, soft shadows | **Leave alone.** Do not add prototype colours here |
| `app/api/mock/[...path]` | Mock server for the console | **Leave alone** |
| `e2e/` | Playwright specs for the console | **Leave alone.** Add `e2e/prototype.spec.ts` later |

### 1.2 `components/`

| File | Contents | Decision | Reason |
|---|---|---|---|
| `shell.tsx` | Console sidebar, header, institute picker, EN/HI switch, loading gate on `ready` | **Leave alone** (see 1.3) | Console navigation; wrong product for the prototype |
| `ui.tsx` | `Card`, `Button`, `Badge`, `Origin`, `Skeleton`, `Unavailable`, `Empty`, `Note`, `PageHead`, `Select`, `Stat` | **Do not restyle; write prototype equivalents** | They hard-code 14px radius, soft shadows, a multi-colour tone set and a console-only `Origin` chip (shown only when `EvidenceContext` is on). Restyling would change the console |
| `echart.tsx` | ECharts wrapper, five-colour palette | **Reuse only if a chart needs it** (evaluation interval plot). Pass prototype colours explicitly; do not use its `PALETTE` | The heatmap is an HTML table, not a canvas chart (accessible, keyboard focusable, numeric labels) |
| `flair.tsx` | `CountUp`, `Ring`, `IconTile`, `EmptyState`, `Logo` | **Leave alone, do not use** | Animated counters, rings and tinted tiles read as gamified; brief section 5 excludes that |
| `pickers.tsx`, `student-view.tsx`, `parent-view.tsx`, `person-page.tsx`, `report-generator.tsx`, `upload-banner.tsx` | Console screens and widgets | **Leave alone** | Different product surface |

### 1.3 `lib/`

| File | Contents | Decision | Reason |
|---|---|---|---|
| `http.ts` | `apiFetch`, `ApiError`, console demo-session token | **Reuse `ApiError` only.** Wrap `fetch` in a new `lib/prototype/client.ts` | `apiFetch` defaults to `/api/mock`, attaches the console demo token, and re-logs in on 401. The prototype API has its own base path and no token yet |
| `query.ts` | `useQuery(key, fetcher)` cache hook | **Reuse** | Only imports `ApiError`; no dependency on console state |
| `utils.ts` | `cn`, `pct`, `byName` | **Reuse `cn` and `pct`.** Do not use `byName` on learner lists (ranking rule is about order; see section 3.1) | Generic helpers |
| `bands.ts` | Four mastery bands with fixed theta cut-offs and console colours | **Leave alone, do not reuse** | Cut-offs and colours belong to the 1.0 Rasch model. The 2.0 scale is defined in section 4 |
| `app-context.tsx`, `names.ts`, `types.ts`, `views.ts`, `api.ts`, `teacher-api.ts`, `privacy-api.ts`, `reports-api.ts`, `ingest.ts`, `server-data.ts`, `hooks.ts`, `mock/` | Console state, types, API clients, mock data | **Leave alone** | Console only |

### 1.4 The one real conflict: the root layout wraps `/prototype`

`app/layout.tsx` puts every route inside `Shell`. The hosted S0 build already shows the effect: `/prototype` renders inside the console sidebar (title "Home", institute picker, EN/HI switch), and its content stays hidden behind a loading skeleton until the console's own data load finishes. The prototype cannot look like the brief inside that frame. Three ways out:

| Option | Change to existing files | Risk |
|---|---|---|
| A. Passthrough in `Shell`: if the path starts with `/prototype`, render `children` and return | 3 to 4 lines in `components/shell.tsx` | Smallest diff; touches a console file; console behaviour unchanged for every other path |
| B. Move all console pages into an `app/(console)/` route group, and make the root layout bare | Moves about a dozen folders; console URLs unchanged | Large diff; e2e and import paths need checking |
| C. Leave the frame as it is | None | Prototype keeps the console sidebar and loading gate. Not acceptable for the first impression the brief asks for |

**Recommendation: A.** It needs your decision because you asked that the console not change; the proposed edit does not change its behaviour. `AppProvider` would still run its institute fetches on prototype pages (wasted requests, no visible effect). See question 1.

---

## 2. Route group structure (file paths only)

```text
frontend/app/(prototype)/prototype/
  layout.tsx                 prototype frame: top bar, skeleton, tokens import
  page.tsx                   entry; sends to /prototype/teacher
  loading.tsx
  error.tsx
  prototype.css              tokens on :root, dark overrides, component classes
  teacher/
    page.tsx                 screen 1: cohort summary and concept heatmap
    bottleneck/
      page.tsx               screen 3: bottleneck panel (also linked from screen 1)
  learner/
    [id]/
      page.tsx               screen 2: next-step card, concept cards, practice
  evaluation/
    page.tsx                 screen 4: results with misses visible

frontend/components/prototype/
  frame/       TopBar.tsx, NavTabs.tsx, PageTitle.tsx
  common/      Card.tsx, Button.tsx, OriginTag.tsx, StatusLine.tsx, LoadingState.tsx,
               ErrorState.tsx, EmptyNote.tsx, DefinitionList.tsx
  teacher/     CohortSummary.tsx, ConceptHeatmap.tsx, HeatmapCell.tsx, HeatmapLegend.tsx,
               LearnerDrawer.tsx, BottleneckPanel.tsx, EdgeRow.tsx, OverrideForm.tsx
  learner/     LearnerSwitch.tsx, NextStepCard.tsx, ReasonBlock.tsx, EvidenceList.tsx,
               ConceptCard.tsx, MasteryRange.tsx, PracticeItem.tsx
  evaluation/  ResultsTable.tsx, ResultRow.tsx, IntervalCell.tsx

frontend/lib/prototype/
  client.ts                  fetch wrapper, base path, ApiError mapping
  types.ts                   response types (section 3 field names)
  schemas.ts                 zod parsers (zod is already a dependency)
  mastery-scale.ts           value to step (m1..m5) and label, one function
  origin.ts                  origin tag type and display text
  format.ts                  number formatting, tabular figures helpers

frontend/e2e/prototype.spec.ts          Playwright against the hosted URL (later)
frontend/api/health.py                  exists (S0)
```

Notes:

- `NavTabs` links Teacher, Learner, Evaluation. No sidebar.
- `LearnerSwitch` offers the two fixture learners by neutral label ("Learner A", "Learner B"), not by name or score.
- `components/prototype/common` replaces the `ui.tsx` pieces; nothing is imported from `components/ui.tsx` or `components/flair.tsx`.

---

## 3. The four screens

Order follows brief section 7. Every screen carries a fixed line under the page title: `Prototype, demo data`. Wireframes are text; `[TAG]` marks an origin tag (section 5). Field names are the response fields the screen reads; endpoint paths are decided in stage S3 and are not proposed here.

### 3.1 Screen 1: Teacher cohort summary with concept heatmap

```text
Pragati 2.0 prototype            Teacher | Learner | Evaluation
Prototype, demo data
-------------------------------------------------------------
Cohort summary                                   [DEMO FIXTURE]
 Learners        Evidence coverage     Bottleneck concept
 2               6 of 9 cells have     Roots of a quadratic
                 enough evidence       blocks 2 objectives
                                       See bottleneck >
-------------------------------------------------------------
Concept by learner                      Show: Group | Learner
                       Learner A        Learner B
 Complex numbers:      [ 0.72 | n=14 ]  [ 0.31 | n=9  ]
  Argand diagram
 Roots of a quadratic  [ 0.48 | n=11 ]  [ -- | n=2 *  ]
 Forming equations    [ 0.40 | n=7  ]  [ -- | n=0 *  ]
 * Insufficient evidence (fewer than 5 attempts)

 Legend: 0.0 [m1][m2][m3][m4][m5] 1.0   [ -- ] no estimate
 Table view of the same data is the table above. Rows sorted by
 syllabus order. Columns are not sorted by score.
```

Components: `CohortSummary`, `ConceptHeatmap`, `HeatmapCell`, `HeatmapLegend`, `LearnerDrawer` (opens on cell activation; shows the learner's concept range and evidence count), `OriginTag`, `Card`.

Behaviour that follows the brief:

- Group view is the default. "Learner" view reveals column headers and the drawer.
- Each cell shows the number and the evidence count; the colour is a secondary cue (brief section 3).
- Cells with fewer evidence items than the threshold show `--` and the amber "insufficient evidence" marker (text plus an icon, not colour alone).
- No ranking: rows follow syllabus order; columns follow a fixed fixture order; there is no sort control and no "top" or "bottom" label.

Data needed:

| Object | Fields |
|---|---|
| `cohort` | `cohort_id`, `learner_count`, `evidence_threshold`, `cells_total`, `cells_with_evidence`, `origin` |
| `bottleneck_summary` | `concept_id`, `concept_label`, `blocked_objective_count`, `edge_review_state` |
| `concepts[]` | `concept_id`, `label`, `class_level`, `syllabus_order` |
| `learners[]` | `learner_id`, `display_label`, `origin` |
| `cells[]` | `concept_id`, `learner_id`, `mastery_estimate`, `interval_low`, `interval_high`, `evidence_count`, `last_evidence_at`, `insufficient_evidence`, `origin` |
| `engine` | `policy_version`, `model_version` |

### 3.2 Screen 2: Learner next-step card with reason

```text
Pragati 2.0 prototype            Teacher | Learner | Evaluation
Prototype, demo data                         Viewing: Learner A v
-------------------------------------------------------------
Next step                                        [DEMO FIXTURE]
 Practise: Roots of a quadratic, nature of roots
 Reason
   The prerequisite "Complex numbers: Argand diagram" has an
   estimate of 0.31 (range 0.18 to 0.46) from 9 attempts.
   "Roots of a quadratic" depends on it, so it comes first.
 Evidence used
   9 attempts on Argand diagram · 11 on Roots of a quadratic
 Policy version: v0.1                       [Start practice]
-------------------------------------------------------------
Concept cards
 Argand diagram     0.31   range 0.18-0.46   n=9
                    Early estimate (fewer than 15 attempts)
 Roots of a quadratic 0.48 range 0.35-0.62   n=11
-------------------------------------------------------------
Practice (after Start practice)
 Question 3 of 10 ....................... one question at a time
 [question text]   ( ) A  ( ) B  ( ) C  ( ) D       [Submit answer]
 Result: Incorrect. Recorded as 1 attempt.
 Updating next step...   ->   Next step unchanged / changed
                              because: [reason sentence]
```

Components: `LearnerSwitch`, `NextStepCard`, `ReasonBlock`, `EvidenceList`, `ConceptCard`, `MasteryRange`, `PracticeItem`, `StatusLine`, `OriginTag`.

Behaviour that follows the brief:

- One primary action per view; the next step card is the only filled button.
- The next step updates only after the backend confirms the attempt; until then the card shows "Updating" and the previous step.
- "Early estimate" label appears when `evidence_count` is below the threshold.
- Copy states facts. No feedback phrases of praise or encouragement; incorrect and correct results use the same wording pattern.

Data needed:

| Object | Fields |
|---|---|
| `learner` | `learner_id`, `display_label`, `origin` |
| `next_step` | `step_id`, `action_type`, `concept_id`, `concept_label`, `item_set_id`, `reason_text`, `reason_inputs[]`, `evidence_used[]`, `policy_version`, `computed_at`, `unchanged_since_previous`, `origin` |
| `reason_inputs[]` | `concept_id`, `mastery_estimate`, `interval_low`, `interval_high`, `evidence_count`, `rule_id` |
| `evidence_used[]` | `concept_id`, `concept_label`, `attempt_count` |
| `concept_states[]` | `concept_id`, `label`, `mastery_estimate`, `interval_low`, `interval_high`, `evidence_count`, `early_estimate`, `origin` |
| `item` | `item_id`, `concept_id`, `stem`, `options[]`, `position`, `total`, `origin` |
| `attempt_request` | `learner_id`, `item_id`, `answer`, `client_attempt_id` (idempotency key) |
| `attempt_result` | `attempt_id`, `correct`, `recorded`, `next_step` (same shape as above), `changed_because` |

### 3.3 Screen 3: Bottleneck panel with unreviewed-edge marking

```text
Pragati 2.0 prototype            Teacher | Learner | Evaluation
Prototype, demo data
-------------------------------------------------------------
Bottleneck: Roots of a quadratic                 [DEMO FIXTURE]
 Blocks 2 objectives for 2 of 2 learners
-------------------------------------------------------------
Prerequisite path
 Complex numbers: Argand diagram
    |  edge: prerequisite       [! Proposed, unreviewed]
    v
 Roots of a quadratic
    |  edge: prerequisite       [! Proposed, unreviewed]
    v
 Forming equations
 Edges marked proposed are suggestions, not confirmed facts.
-------------------------------------------------------------
Why this is flagged
 Learner A: 0.31 on the prerequisite (n=9)
 Learner B: no estimate on the prerequisite (n=2)
-------------------------------------------------------------
Suggested action                          Your decision
 Review the edge "Argand diagram -> Roots of a quadratic"
 ( ) Accept   ( ) Modify   ( ) Dismiss
 Reason (required): [______________________________]
                                          [Save decision]
 Saved decisions: none
```

Components: `BottleneckPanel`, `EdgeRow`, `OverrideForm`, `EvidenceList`, `OriginTag`, `StatusLine`.

Behaviour that follows the brief:

- The edge review state is text and an amber marker; accepted edges show "Reviewed" in the same weight, not a celebratory state.
- `Save decision` is disabled until the reason field has text (brief section 4, item 4).
- A saved decision shows who, what and when; it does not change the engine's graph in the prototype unless the S3 API supports it (question to the build stage, not the owner).

Data needed:

| Object | Fields |
|---|---|
| `bottleneck` | `concept_id`, `concept_label`, `blocked_objective_count`, `learners_affected`, `learners_total`, `score`, `score_method`, `origin` |
| `edges[]` | `edge_id`, `from_concept_id`, `from_label`, `to_concept_id`, `to_label`, `review_state` (`proposed`, `accepted`, `modified`, `dismissed`), `source`, `reviewed_by`, `reviewed_at` |
| `learner_evidence[]` | `learner_id`, `display_label`, `concept_id`, `mastery_estimate`, `evidence_count`, `insufficient_evidence` |
| `suggestion` | `suggestion_id`, `edge_id`, `action_type`, `reason_text` |
| `override_request` | `suggestion_id`, `decision`, `reason`, `client_request_id` |
| `override_record` | `override_id`, `decision`, `reason`, `decided_by`, `decided_at` |

### 3.4 Screen 4: Evaluation page with misses visible

```text
Pragati 2.0 prototype            Teacher | Learner | Evaluation
Prototype, demo data
-------------------------------------------------------------
Evaluation results
 Every row uses the same layout. A result that misses its bar is
 shown the same way as one that meets it.
-------------------------------------------------------------
Metric | Task | Origin | Baseline | Result | 95% CI | Bar | Outcome
 ...rows, one per pre-registered result...
 Example row shape:
 AUC  | next-response prediction | [PUB] | 0.xx | 0.xx | 0.xx-0.xx | >= 0.xx | Met / Missed
 Not run yet: [EXP] root-cause diagnosis (no labels yet)
-------------------------------------------------------------
Notes
 Results come from the pre-registered runs; run id, dataset
 version, split, seed and model version are listed per row.
```

Components: `ResultsTable`, `ResultRow`, `IntervalCell`, `OriginTag`, `EmptyNote` (for "Not run yet" rows).

Behaviour that follows the brief:

- Misses use the same row style as passes; the only difference is the word in the Outcome column.
- Rows with no result show "Not run yet" and a reason, never a blank or an estimate.
- Each row has an origin tag; no row mixes tags.

Data needed:

| Object | Fields |
|---|---|
| `results[]` | `result_id`, `eval_set` (for example `E1`), `metric`, `task`, `origin`, `baseline_name`, `baseline_value`, `result_value`, `ci_low`, `ci_high`, `bar_operator`, `bar_value`, `outcome` (`met`, `missed`, `not_run`), `not_run_reason` |
| `provenance` (per result) | `dataset_name`, `dataset_version`, `split_id`, `seed`, `model_version`, `script_path`, `run_at`, `preregistration_id` |

---

## 4. Tokens as CSS custom properties, and the mastery scale

### 4.1 Mechanics

- Tokens live in `app/(prototype)/prototype/prototype.css`, imported only by `prototype/layout.tsx`. No `var(--` is used anywhere else in `frontend/` today, so the unprefixed names from the brief do not collide with the console (checked by search).
- Dark mode follows the design rules in `CLAUDE.md`: defaults on `:root`, overrides under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`.
- The prototype frame sets `body`-level colour and background from tokens on its own wrapper, because the root layout's `bg-bg` utility is a fixed console colour.
- Tailwind is used for layout utilities only. Colours come from the variables through classes in `prototype.css`; `tailwind.config.ts` is not edited.

```css
:root {
  --bg: #F6F7F9;
  --surface: #FFFFFF;
  --text: #1B2430;
  --text-muted: #5B6675;
  --border: #E1E5EB;
  --accent: #0F6E6E;
  --warn: #9A5B00;
  --on-accent: #FFFFFF;

  --mastery-1: #E4F2F2;  --on-mastery-1: #1B2430;
  --mastery-2: #B5DCDC;  --on-mastery-2: #1B2430;
  --mastery-3: #72BBBB;  --on-mastery-3: #1B2430;
  --mastery-4: #2A8080;  --on-mastery-4: #FFFFFF;
  --mastery-5: #0E5656;  --on-mastery-5: #FFFFFF;
  --mastery-none: #EDEFF3;

  --radius: 8px;
  --focus-ring: 2px solid var(--accent);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* dark values below */ }
}
:root[data-theme="dark"] {
  --bg: #0F1419;
  --surface: #1A2129;
  --text: #E6EAF0;
  --text-muted: #9AA5B4;
  --border: #2A3440;
  --accent: #4FB3B3;
  --warn: #E0A94D;
  --on-accent: #0F1419;

  --mastery-1: #22333A;  --on-mastery-1: #E6EAF0;
  --mastery-2: #2F5B62;  --on-mastery-2: #E6EAF0;
  --mastery-3: #3F8A8F;  --on-mastery-3: #0F1419;
  --mastery-4: #66B8B8;  --on-mastery-4: #0F1419;
  --mastery-5: #A6E0DE;  --on-mastery-5: #0F1419;
  --mastery-none: #222B35;
}
```

Token map:

| Brief token (section 3) | Custom property | Light | Dark |
|---|---|---|---|
| Page background | `--bg` | `#F6F7F9` | `#0F1419` |
| Cards | `--surface` | `#FFFFFF` | `#1A2129` |
| Body text | `--text` | `#1B2430` | `#E6EAF0` |
| Labels, captions | `--text-muted` | `#5B6675` | `#9AA5B4` |
| Hairlines | `--border` | `#E1E5EB` | `#2A3440` |
| Primary action, selected | `--accent` | `#0F6E6E` | `#4FB3B3` |
| Insufficient evidence, unreviewed | `--warn` | `#9A5B00` | `#E0A94D` |
| Mastery scale (added by this proposal) | `--mastery-1` to `--mastery-5`, `--mastery-none`, plus `--on-mastery-N` | see 4.3 | see 4.3 |
| Radius 8px | `--radius` | `8px` | `8px` |
| No shadows | none; hairline `--border` only | | |
| Type | Inter Variable (already installed), body 15px, labels 13px, `font-variant-numeric: tabular-nums` on numbers | | |

### 4.2 Brief tokens: contrast

Ratios are WCAG 2.x relative-luminance contrast, computed with a script (`contrast.py`, kept in the session scratchpad, not in the repo; to be moved to `ml/` or `scripts/` if you want it reproducible).

| Pair | Light | Dark | Requirement | Result |
|---|---|---|---|---|
| `--text` on `--bg` | 14.60 | 15.33 | 4.5 | Meets |
| `--text` on `--surface` | 15.65 | 13.45 | 4.5 | Meets |
| `--text-muted` on `--surface` | 5.83 | 6.51 | 4.5 | Meets |
| `--text-muted` on `--bg` | 5.44 | 7.42 | 4.5 | Meets |
| `--accent` on `--surface` (links, selected text) | 6.04 | 6.52 | 4.5 | Meets |
| `--on-accent` on `--accent` (primary button) | 6.04 | 7.43 | 4.5 | Meets |
| `--warn` on `--surface` | 5.43 | 7.69 | 4.5 | Meets |
| `--warn` on `--mastery-none` | 4.71 | 6.79 | 4.5 | Meets |
| `--border` on `--surface` | 1.26 | 1.29 | none (decorative hairline) | Not a meaningful boundary on its own; cells carry numeric labels, so no information depends on it |

### 4.3 Mastery scale: values, labels, and colour-blind check

Five light-to-dark steps of one teal hue in light mode. In dark mode the order runs dark-to-light so that a higher value is always the more prominent step against the page. The step is chosen by the mastery estimate (0 to 1): m1 below 0.2, m2 0.2 to under 0.4, m3 0.4 to under 0.6, m4 0.6 to under 0.8, m5 0.8 and above. `--mastery-none` is a neutral cell with a dashed border and the text `--`. The cut-offs are placeholders for the engine's real output range and are an open item for the build stage.

Every cell prints its number (`0.48`) and the evidence count (`n=11`). Colour is a second cue only.

**Text on cell (4.5 required):**

| Step | Cell colour | Text colour | Light ratio |
|---|---|---|---|
| m1 | `#E4F2F2` | `#1B2430` | 13.63 |
| m2 | `#B5DCDC` | `#1B2430` | 10.61 |
| m3 | `#72BBBB` | `#1B2430` | 7.11 |
| m4 | `#2A8080` | `#FFFFFF` | 4.67 |
| m5 | `#0E5656` | `#FFFFFF` | 8.45 |
| none | `#EDEFF3` | `#1B2430` | 13.60 |

| Step | Cell colour | Text colour | Dark ratio |
|---|---|---|---|
| m1 | `#22333A` | `#E6EAF0` | 10.85 |
| m2 | `#2F5B62` | `#E6EAF0` | 6.23 |
| m3 | `#3F8A8F` | `#0F1419` | 4.62 |
| m4 | `#66B8B8` | `#0F1419` | 8.03 |
| m5 | `#A6E0DE` | `#0F1419` | 12.64 |
| none | `#222B35` | `#E6EAF0` | 11.87 |

Two values changed during checking: the first light m4 (`#2E8A8A`) gave 4.10 with white text, and the first dark m3 gave 4.01 with white text. Both were adjusted to the values above.

**Step-to-step contrast, normal vision and simulated colour-vision deficiency** (adjacent steps in the scale; simulation is the Machado et al. matrix at full severity applied in linear RGB):

| Pair (light) | Normal | Deuteranopia | Protanopia | Tritanopia |
|---|---|---|---|---|
| m1 vs m2 | 1.28 | 1.30 | 1.26 | 1.28 |
| m2 vs m3 | 1.49 | 1.53 | 1.45 | 1.49 |
| m3 vs m4 | 2.12 | 2.15 | 2.09 | 2.07 |
| m4 vs m5 | 1.81 | 1.79 | 1.83 | 1.80 |

| Pair (dark) | Normal | Deuteranopia | Protanopia | Tritanopia |
|---|---|---|---|---|
| m1 vs m2 | 1.74 | 1.70 | 1.80 | 1.74 |
| m2 vs m3 | 1.88 | 1.85 | 1.92 | 1.89 |
| m3 vs m4 | 1.74 | 1.74 | 1.73 | 1.73 |
| m4 vs m5 | 1.57 | 1.60 | 1.54 | 1.57 |

What this shows and what it does not:

- The scale is a single hue ordered by lightness, so the luminance order of the five steps is preserved under all three simulated deficiencies (checked: monotonic in each case) and the contrast between steps barely moves between normal vision and deficiency.
- Adjacent steps are close in lightness (1.26 to 2.15). Neighbouring steps are hard to tell apart by colour alone, which is why the number is printed in every cell. Steps two apart are easier to separate. This is a limit of a 5-step single-hue scale, not something to fix by adding hues.
- `m1` light (`#E4F2F2`) against the white card is 1.15, so the cell needs a 1px `--border` outline.
- This is a computed check, not a test with colour-blind users and not a run in a browser simulator. The brief also asks for a simulator pass; that is still to do on the built page.
- Amber `--warn` against teal steps is a hue difference only for normal vision. Under deuteranopia and protanopia amber and green-teal can be close. The "insufficient evidence" and "proposed, unreviewed" states therefore always carry text and an icon.

---

## 5. Every place a number appears, and its origin tag

Tags per `CLAUDE.md` and the brief: `[DEMO FIXTURE]`, `[SIM]`, `[PUB]`, `[EXP]`. The evaluation plan also defines `[PILOT]`; it does not appear in the prototype because no pilot has run. Assumption for numbers that change after a viewer submits an attempt: they keep `[DEMO FIXTURE]` and the card says "includes attempts made in this session".

| Screen | Number | Tag |
|---|---|---|
| All | Page-level line "Prototype, demo data" (not a number; shown beside every tagged block) | none |
| 1 Cohort summary | Learner count | `[DEMO FIXTURE]` |
| 1 Cohort summary | Evidence coverage (cells with enough evidence of total) | `[DEMO FIXTURE]` |
| 1 Cohort summary | Bottleneck concept's blocked-objective count | `[DEMO FIXTURE]` |
| 1 Heatmap | Mastery estimate per cell | `[DEMO FIXTURE]` |
| 1 Heatmap | Evidence count `n` per cell | `[DEMO FIXTURE]` |
| 1 Heatmap | Interval bounds in the learner drawer | `[DEMO FIXTURE]` |
| 1 Heatmap | Legend scale endpoints 0.0 and 1.0 | none (scale definition) |
| 1 Heatmap | Evidence threshold ("fewer than 5 attempts") | none (engine setting; show its value and policy version) |
| 2 Next step | Estimate and range quoted in the reason sentence | `[DEMO FIXTURE]` |
| 2 Next step | Attempt counts in "Evidence used" | `[DEMO FIXTURE]` |
| 2 Next step | Policy version | none (version string) |
| 2 Concept cards | Mastery estimate, range, evidence count, early-estimate threshold | `[DEMO FIXTURE]` (threshold: none) |
| 2 Practice | Question position and total ("3 of 10") | none (position in a list) |
| 2 Practice | Count of attempts recorded after submit | `[DEMO FIXTURE]` (includes this session) |
| 3 Bottleneck | Blocked-objective count, learners affected of total | `[DEMO FIXTURE]` |
| 3 Bottleneck | Bottleneck score, if shown | `[DEMO FIXTURE]` with the score method named |
| 3 Bottleneck | Per-learner estimate and `n` under "Why this is flagged" | `[DEMO FIXTURE]` |
| 3 Bottleneck | Saved decision count, timestamps | none (user action record) |
| 4 Evaluation | AUC, accuracy or other metric, baseline value, CI bounds, bar value | per row: `[PUB]`, `[SIM]` or `[EXP]` (E1, E3 and E4 in `EVAL_PLAN.md`) |
| 4 Evaluation | Dataset version, seed, run date | none (provenance fields) |
| 4 Evaluation | Count of "not run" results | none |

Placement rule: the tag sits in the block heading for blocks with one origin, and in a column for tables. A block never mixes tags. Tag text is the literal bracketed string so that a grep over responses and rendered text can check it.

---

## 6. Questions for the owner

1. **Is a small edit to `components/shell.tsx` acceptable?** Today the console frame wraps `/prototype` and hides the page until console data loads (section 1.4). The smallest fix is a path check at the top of `Shell` that returns `children` for paths starting with `/prototype`. Console pages behave as before. The alternative is moving the whole console into a route group, which is a much larger change. If neither is acceptable, the prototype keeps the console sidebar.
2. **May the evaluation page name ASSISTments?** `PROTOTYPE_PLAN.md` section 5 says no ASSISTments or pending-source text appears anywhere in the UI or API responses. `EVAL_PLAN.md` E1 is the ASSISTments run, and its origin tag `[PUB]` needs a dataset name to be honest. Options: name the dataset and its licence on the evaluation page, show only `[PUB]` with a "public dataset" label and no name, or omit E1 until the dataset terms are checked.
3. **How many learners should the heatmap show?** The plan has two fixture learners, so the heatmap would be two columns, which is thin for "the strongest first impression". A larger cohort (for example 24 learners) would have to be generated by the simulator and tagged `[SIM]`, with the two fixtures marked `[DEMO FIXTURE]`, and the screen would then mix two tags (one per column group). Do you want two learners, or a simulated cohort with both tags shown?
