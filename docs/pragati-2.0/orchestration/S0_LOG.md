# S0 log: hosted hello page and health endpoint

Status: deployed; anonymous access and in-browser page check still open. Updated 2026-11-05.

| Step | Result |
|---|---|
| Branch | `claude/serene-sagan-8za1vh` (remote already held the planning docs; rebased onto it) |
| `/prototype` page | `frontend/app/(prototype)/prototype/page.tsx`; `next build` and `tsc` pass locally |
| Health endpoint | `frontend/api/health.py` (Vercel Python function; lives under `frontend/` because the project root directory is `frontend`). Returns `{"status":"ok","version":"<VERCEL_GIT_COMMIT_SHA>"}`; no database calls |
| Vercel project `pragati-2-prototype` | Created (`prj_yg7Pe3aUnM2tRXUojlrk47EpdlHT`, team `team_eU77vEKDPuiAmwd1zrn5Qtt1`, root `frontend`, Next.js, linked to this repo). Required the owner to approve team access first (two links; the first expired). The 11 existing projects were not touched |
| Production URL | https://pragati-2-prototype.vercel.app (redeployed as `dpl_6Djm3WLQTbsmdPwcvLayftAtfu5H`, commit dbe32ee, READY; first deploy was `dpl_B4qqRELipsSdjMBAP8NNZtjGgGrz`, commit 11c2172) |
| Preview URL (READY) | https://pragati-2-prototype-opx9591r9-adityakuranjekars-projects.vercel.app (deployment `dpl_9WJjFGwQ8aZYs5X6wt8RGZkdnzqg`, same commit; still BUILDING when last checked, not fetched: Vercel Auth blocked the fetch tool). Note: the first deploy of the project was assigned production automatically, so production was created before the preview |
| Health check (production) | `GET /api/health` returned HTTP 200 `{"status": "ok", "version": "dbe32ee06c6d3740b38407c5dd9143e17b4a529f"}` (after the redeploy) |
| `/prototype` (production) | HTTP 200; page is part of the build. Server HTML contains the console shell and loading skeleton; the page body is client-rendered, so its text was not confirmed in a browser |
| Check method | The sandbox egress proxy returns 403 for `*.vercel.app`, so curl from the sandbox failed. Checks were made with the Vercel MCP fetch tool, which runs outside the sandbox but with the owner's Vercel session |
| Deployment protection | Vercel Auth turned off on this project at the owner's request, so the URLs are public |

Notes
- The page is inside the existing root layout, so it renders within the institute console shell. Changing that would need edits outside the new route group.
- The institute console remains at `/` on the same deployment (plan section 6 warns about this).

## Update: prototype UI deployed

- Production redeployed as `dpl_2Rka81M5zzA5BmK5VVLnH9QzL7oD` (commit e98dfc1), READY.
- `/api/health` returned HTTP 200 `{"status": "ok", "version": "e98dfc13c2ff6ccd15ff6eb686a915acacce80c1"}`.
- `/prototype/evaluation` returned HTTP 200 with the prototype frame (no console sidebar) and page content in the server HTML; no dataset names appear in it. Fetched with the Vercel MCP fetch tool, not an anonymous browser.
- Still not checked on the hosted URL: Playwright flow, anonymous private-window access.

## Update: final deploy (2026-11-05)

- Production: https://pragati-2-prototype.vercel.app, deployment `dpl_cFvkdmivnRdfwgmUDQrV2YSADeV2`, commit c2ff71e (console look, light only, plain-language labels), READY.
- `/api/health` returned HTTP 200 `{"status": "ok", "version": "c2ff71e5b8ccf015ada9c4e460482d773dfe5e1a"}`, matching the deployed commit.
- Preview: the earlier preview deployment (`dpl_9WJjFGwQ8aZYs5X6wt8RGZkdnzqg`, commit 11c2172) is still the only preview and shows the first hello page, not the current UI.
- Method: checks used the Vercel MCP fetch tool (the sandbox proxy blocks `*.vercel.app`). Vercel Auth is off on the project.
- Not confirmed: an anonymous private-window check of both URLs, and a browser run of the practice flow on the hosted URL (it was run locally in Chromium).
- Branch: `claude/serene-sagan-8za1vh` on GitHub. No pull request was opened.
