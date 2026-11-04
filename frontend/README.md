# Pragati web (Tab 2)

Next.js 14 (App Router) + TypeScript + Tailwind + ECharts. Reads the ML artifacts through a thin mock API.

## Run
```bash
npm install
npm run dev        # http://localhost:3000
npm run build && npm run lint && npm run typecheck
```
Sign in at `/login` (demo accounts, no password). Tests: `npm run build && npm run e2e` (Playwright against the production build and the mock; first time `npx playwright install chromium`).
The mock API reads `ml/artifacts/<institute>/*.json`, (regenerate first, see the root README; the sample files were removed).
If the artifacts are elsewhere (for example in another worktree), set `ARTIFACTS_DIR` in `.env.local`.

## Folder map
- `app/` pages: `login`, `capture` (spreadsheet and OMR), `teacher`, `student/[id]`, `parent/[id]`, `owner`, `privacy` (consent and privacy tier), `data-card`, `how-it-works`; `api/mock/[...path]` is the mock server entry.
- `lib/mock/` the in-memory mock server and CSV column matcher; `e2e/` Playwright specs.
- `lib/types.ts` one zod schema per artifact file; `lib/api.ts` the only fetch client; `lib/app-context.tsx` language, institute, `useData`.
- `components/` shell (header, role switcher), `ui.tsx` primitives and origin chips, `echart.tsx` themed chart wrapper.

## Swap to the real API
Set `NEXT_PUBLIC_API_BASE` (default `/api/mock`; real: `http://localhost:8000/api/v1`) and rebuild. If the artifact-read path shape differs, change `urlFor` in `lib/api.ts`. All HTTP goes through `lib/http.ts` (token, 401, 403). What each call sends and expects: `API_CONTRACT.md`. What is simulated: `NOTES.md`.

## Data to screen
| Screen | Files |
|---|---|
| Teacher | mastery, risk, student (names) |
| Student | student, percentile |
| Parent | parent, reports, student |
| Owner | owner, risk, mastery, moat |
| Data card | datacard, figures/*.png |
| How it works | scaling, models |
| Capture | datacard, mastery (simulated) |

Student/parent ids `_` resolve to the first student by roll number. Students are never sorted by performance.
