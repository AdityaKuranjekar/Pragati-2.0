# S0 log: hosted hello page and health endpoint

Status: code done and pushed; hosting steps blocked (see below). Updated 2026-11-05.

| Step | Result |
|---|---|
| Branch | `claude/serene-sagan-8za1vh` (remote already held the planning docs; rebased onto it) |
| `/prototype` page | `frontend/app/(prototype)/prototype/page.tsx`; `next build` and `tsc` pass locally |
| Health endpoint | `frontend/api/health.py` (Vercel Python function; lives under `frontend/` because the project root directory is `frontend`). Returns `{"status":"ok","version":"<VERCEL_GIT_COMMIT_SHA>"}`; no database calls |
| Vercel project `pragati-2-prototype` | NOT created. Vercel API returned 403 for team `team_eU77vEKDPuiAmwd1zrn5Qtt1` until the owner approves team access (one-time link) |
| Preview URL | pending |
| Production URL | pending |
| External health check | pending |

Notes
- The page is inside the existing root layout, so it renders within the institute console shell. Changing that would need edits outside the new route group.
- The institute console remains at `/` on the same deployment (plan section 6 warns about this).
