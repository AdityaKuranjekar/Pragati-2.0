"""P4 upload endpoints: preview (mapping + row errors) then commit. CSV and XLSX."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

from .. import deps
from ..services import ingest as svc

router = APIRouter(prefix="/api/v1/ingest")
WRITE = deps.require(*deps.MANAGERS)
KINDS = ("students", "guardians", "attendance", "fees", "results", "answer-key")


def _wrap(fn, *a, **k):
    try:
        return fn(*a, **k)
    except svc.IngestError as e:
        raise HTTPException(e.status, detail={"message": e.message, **e.extra})


@router.post("/{kind}", status_code=201)
async def upload(kind: str, file: UploadFile = File(...), mapping: str | None = Form(None), test_id: str | None = Form(None),
                 test_name: str | None = Form(None), batch_id: str | None = Form(None), test_date: str | None = Form(None),
                 max_marks: str | None = Form(None), commit: bool = Form(False),
                 p=Depends(WRITE), conn=Depends(deps.tenant)):
    """Upload a file. Returns a mapping preview and row errors; nothing is written until commit (or commit=true)."""
    if kind not in KINDS:
        raise HTTPException(404, f"unknown upload kind '{kind}'; use one of {KINDS}")
    data = await file.read()
    params = {"mapping": mapping, "test_id": test_id, "test_name": test_name, "batch_id": batch_id, "test_date": test_date, "max_marks": max_marks}
    out = _wrap(svc.preview, conn, p.institute_id, p.user_id, kind, file.filename or "upload", data, params)
    if commit and out["can_commit"] and not out["duplicate"]:
        out["commit"] = _wrap(svc.commit, conn, p.institute_id, out["job_id"])
        out["status"], out["committed"], out["stage"], out["progress"] = "done", True, "done", 1.0
    return out


@router.get("/jobs/{job_id}")
def job(job_id: str, p=Depends(WRITE), conn=Depends(deps.tenant)):
    return _wrap(svc.get_job, conn, job_id)


class MappingIn(BaseModel):
    mapping: dict[str, str | None]


@router.post("/jobs/{job_id}/mapping")
def set_mapping(job_id: str, body: MappingIn, p=Depends(WRITE), conn=Depends(deps.tenant)):
    """Re-validate the stored file with the caller's column choices (source column -> target field or null)."""
    return _wrap(svc.remap, conn, job_id, body.mapping)


@router.post("/jobs/{job_id}/commit", status_code=202)
def commit_job(job_id: str, p=Depends(WRITE), conn=Depends(deps.tenant)):
    """Writes and recomputes (a second or two), then answers 202 with status 'running'; the next GET reports 'done'."""
    out = _wrap(svc.commit, conn, p.institute_id, job_id)
    view = _wrap(svc.get_job, conn, job_id)
    view.update({"idempotent": out.get("idempotent"), "result": out.get("result"), "status": "running", "stage": "recompute", "progress": 0.9})
    return view
