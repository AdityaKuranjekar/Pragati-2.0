# Prototype UI design brief

**Status:** draft, 2026-11-05. For the `/prototype` route in `frontend/`. The institute console is not changed.

## 1. Direction in one line

A calm, institutional learning tool that a teacher would trust with a class list: quiet surfaces, one accent colour, numbers that explain themselves.

## 2. Inspiration, and what we take from each

| Reference | Take | Do not take |
|---|---|---|
| ClassDojo (`https://www.classdojo.com/`) | Clear hierarchy, generous spacing, friendly tone in copy, simple navigation between a class and its people | Playful illustrations, mascots, bright multi-colour palettes, rewards and badges. Too informal for a learning-analytics product |
| Khan Academy learning dashboard and Course Mastery Progress Report | Card-based next-step layout; class-level mastery bars; option to hide student names when projecting | Gamified points and streak metaphors |
| Research guidance on education dashboards (summary first, drill down on demand; simplified legends and tooltips; actionability and transparency; group-level view as default; co-design with teachers) | The information architecture in §4 | Visual style claims without a source |

**Honest note:** I could not render ClassDojo's live pages from here, so the ClassDojo row is based on its public description, not a screen-by-screen review. Before the work session starts, the owner should open ClassDojo and two other references, and send screenshots of the three things they like most (see §8).

## 3. Visual system

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F6F7F9` | `#0F1419` | Page background |
| `--surface` | `#FFFFFF` | `#1A2129` | Cards |
| `--text` | `#1B2430` | `#E6EAF0` | Body text |
| `--text-muted` | `#5B6675` | `#9AA5B4` | Labels, captions |
| `--border` | `#E1E5EB` | `#2A3440` | Hairlines (use instead of shadows) |
| `--accent` | `#0F6E6E` | `#4FB3B3` | Primary action, selected state |
| `--warn` | `#9A5B00` | `#E0A94D` | "Insufficient evidence", "unreviewed" |

- **Mastery scale:** a single-hue sequential scale (light to dark teal or blue) with a numeric label on every cell. Never encode mastery by colour alone. Test with a colour-blindness simulator.
- **Radius:** 8px on cards and inputs. Not pill shapes.
- **Shadows:** none, or one very light shadow on popovers only.
- **Type:** one sans-serif family (for example Inter from Google Fonts, the only allowed stylesheet source). Body 15px, labels 13px, numbers tabular.
- **Density:** teacher views can be dense; learner views are one primary action at a time.
- **Tokens** are defined on `:root` and redefined for dark mode, as the design rules in `CLAUDE.md` require.

## 4. Information architecture

**Teacher (default view for the demo)**
1. **Cohort summary:** learners, evidence coverage, bottleneck concept with its number of blocked objectives.
2. **Concept heatmap:** concepts (rows) by learners (columns), with cell labels, an evidence count and an "insufficient evidence" marker. Group view first; per-student on demand.
3. **Bottleneck panel:** the prerequisite edge involved, its review state ("proposed, unreviewed" in amber), and the reason.
4. **Override:** accept, modify or dismiss a suggestion, with a required reason field.

**Learner (demo fixtures)**
1. **Next step card:** one action, one reason in a sentence, the evidence used (counts and concept names), and the policy version.
2. **Concept cards:** mastery band, uncertainty shown as a range, evidence count. Labelled "early estimate" when evidence is low.
3. **Practice:** one question at a time; answer, feedback, and the next step updates after the backend confirms.

**Evaluation page**
- Each result as a row: metric, task, origin tag, baseline, result, CI, and pass/miss against the pre-registered bar. Misses are shown in the same style as passes.

## 5. Content rules (serious tone)

- Plain, specific labels: "Prerequisite not yet mastered", not "Oops!" or "Great job!".
- No praise, badges, streaks or points.
- Every number has an origin tag: `[DEMO FIXTURE]`, `[SIM]`, `[PUB]`, `[EXP]`.
- No ranking of students in any view.

## 6. Layout and accessibility rules

- 16px side gutter; no horizontal scroll at phone width.
- Keyboard navigable; visible focus ring; contrast at least 4.5:1 for body text.
- Charts have a text alternative (the table under the chart is the accessible version).

## 7. Screens to build first (order matters)

1. Teacher cohort summary with the heatmap (the strongest first impression).
2. Learner next-step card with reason.
3. Bottleneck panel with unreviewed-edge marking.
4. Evaluation page with misses visible.

## 8. Inspiration you can send

Please send 2 to 4 links plus one line each on what to take. Useful categories: a calm learning dashboard; a clean data table with filters; a serious analytics product for teachers or clinicians. Screenshots are better than links if the page needs a login.
