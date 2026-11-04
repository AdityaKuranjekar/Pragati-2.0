# What the web app sends and expects (for the backend)

The web app calls `${NEXT_PUBLIC_API_BASE}${path}`. Mock: `/api/mock` (in-process, `lib/mock/server.ts`). Real server: set `NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1` and rebuild (`NEXT_PUBLIC_*` is compiled in). Errors use FastAPI's `{"detail": "text"}` or `{"detail": [{"loc": ["body","field"], "msg": "text"}]}`; the screen shows `msg` as is (for example "Attendance must be between 0 and 100 (got 140)").
Every call except `POST /auth/login` sends `Authorization: Bearer <token>`. 401: the app gets a new demo token and retries once; 403 shows "not available". CORS must allow the web origin and the `Authorization` header.

Each response below is validated with zod in `lib/*.ts`; extra fields are fine, missing required ones show an error.

| Method and path | Request | Response (fields the UI reads) |
|---|---|---|
| `POST /auth/login` | `{role: "owner", institute_id}` (the app always signs in as owner, silently, and again after any 401) | `{access_token, me: {name, role, institute_slug, ...}}`; the client also accepts `user` |
| `GET /{institute}/{file}` and `/global/{file}` | | Artifact-shaped JSON, the same bodies as `ml/artifacts/<institute>/<file>.json`. Files: `mastery risk student percentile parent reports owner datacard` and global `moat scaling models metrics`. Student and parent roles must only receive their own `student_id` rows. `risk.list[].attendance_pct` is new and optional. |
| `POST /ingest/{students,attendance,fees,results,answer-key}` | multipart `file` (CSV or XLSX) | job preview (below), HTTP 201 |
| `POST /ingest/jobs/{id}/mapping` | `{mapping: {source_column: target_field|null}}` | job preview (re-validated) |
| `POST /ingest/jobs/{id}/commit` | `{}` | job, `status: "running"`, HTTP 202; 422 with a text `detail` if required columns are missing |
| `GET /ingest/jobs/{id}` | | job; polled every 400 ms; `status` is `preview|running|done|failed`, `stage` is `reading|cleaning|scoring|recompute|done`, `progress` 0..1 |
| `POST /ingest/omr` | multipart `file` (photo) | `{job_id, status: "review"|"retake", filename, result: OmrResult.to_dict()}` (shape of `backend/app/omr/reader.py`; the UI reads `roll_no`, `quality`, `questions`, `uncertain[].{question_no,label,reason,fill}`) |
| `POST /ingest/omr/{job}/confirm` | `{corrections: {"<question_no>": "A".."D"}}` for every uncertain question | `{status: "done", roll_no, scored: {correct, wrong, blank, marks, max_marks}, redirect}`; 422 text if some uncertain cells are not covered |
| `GET /ingest/omr/{job}` | | same shape as the upload response (used for the banner after the redirect) |
| `GET /batches/{id}/tests` | | `{batch_id, tests: [{test_id, name, date, question_count}]}` (**not in the plan's endpoint table; please add**) |
| `GET /tests/{id}/flagged-questions` | | `{test_id, flagged: [{question_no, subject, current_key, suggested_key, reason_code, share_top_group_chose_suggested, share_chose_current_key, n_students, status: "open"|"fixed", fixed_at}]}` |
| `POST /answer-keys/{test}/{q}` | `{key: "A".."D"}` (or `A|C`) | `{test_id, question_no, key, rescored_students, recompute_ms, flagged: [...]}` |
| `PATCH /students/{id}/attendance` | `{attendance_pct: number}` | `{student_id, attendance_pct, track, effect: "model"|"rule_only"|"none", on_support_list, recompute_ms, message_en, message_hi, support_list: <risk body>}`; 422 for out of range; 404 for an unknown student. Students under 18: `effect: "rule_only"` and the model must not use attendance. |
| `GET /batches/{id}/support-list` | | risk body (the UI currently reloads `/{institute}/risk` instead) |
| `GET /settings/privacy-tier` | | `{tier: "full"|"academic_only", options: [{tier, label_en, label_hi, metrics: {auc, precision, recall, lead_time_days}}], minors_always_academic, list_size, capacity_per_week, origin}` |
| `PUT /settings/privacy-tier` | `{tier}` | same as GET (owner only; recompute so `list_size` is the new size) |
| `GET /consents?q=` | | `{items: [{consent_id, student_id, roll_no, guardian_display, kind: "parental"|"self", method, date, status: "active"|"withdrawn"}], summary: {total, active, withdrawn}}` |
| `POST /consents` | `{roll_no, guardian_name, method: "in_person_id_check"|"digilocker"}` | the new consent row, 201; 409 if already active |
| `DELETE /consents/{id}` | | `{...row, effect: "text"}`; processing for that student must stop at once |
| `POST /students/{id}/reports` | `{language: "hi"|"en", use_llm: bool}` | `{student_id, language, month, body, verified, checks: [{id, label, passed}], source: "template"|"llm", llm_requested, llm_available, fallback_used, fallback_reason, hi_reviewed, latency_ms}` |

Job preview fields: `job_id, kind, filename, status, stage, progress, row_count, accepted_count, error_count, warning_count, rejected_rows, columns: [{source, target|null, confidence 0..1, alternatives}], targets: [{id, required, label_en, label_hi}], missing_required: [target ids], one_of: [target ids]|null, one_of_missing, can_commit, errors: [{row, column, code, severity: "error"|"warning", value, message_en, message_hi}], errors_truncated, sample_rows: [{source_column: value}], redirect`. Target ids follow `contracts/csv_templates/*.csv` (for attendance, `attendance_pct` is an addition so a percent-per-student sheet also works).

Roles enforced by the mock (the real server should do the same): staff = owner, teacher, mentor. Ingest and answer keys: owner, teacher. Attendance edit: staff. Consent write and privacy-tier PUT: owner only. Student and parent: only their own artifact rows and report. Other institute: 403.


The screens read batch and student data from `GET /batches`, `/batches/{id}/students|heatmap|support-list`, `/students/{id}/profile|parent-view`, `/owner/dashboard`, `/datacard`, `/scaling`, `/models`, and `/global/moat` (all served by the real backend and by the mock).
