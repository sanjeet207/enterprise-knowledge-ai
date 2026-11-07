import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict

from app import config
from app.schemas import IngestRequest
from app.security import get_current_user
from app.agents import comparer
from app.services import admin, compare, extract, ingest, jobs, upload_policy, users, validation, versions
from app.services.llm import LLMUnavailable
from app.services.users import User

router = APIRouter(prefix="/documents", tags=["Documents"])


def _authorize(user: User, level: int, engagement_id: Optional[str]) -> None:
    is_member = bool(engagement_id) and users.is_engagement_member(engagement_id, user.id, user.tenant_id)
    try:
        upload_policy.check_upload(user.is_admin, user.level, level, engagement_id, is_member)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


def _add(user: User, title: str, content: str, level: int, engagement_id: Optional[str], filename: Optional[str],
         review_by: Optional[str] = None, previous: Optional[dict] = None) -> dict:
    _authorize(user, level, engagement_id)
    try:
        result = ingest.ingest_document(user, title, content, level, engagement_id, filename, review_by, previous)
    except ingest.IngestError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    return {"status": "success", **result}


def _enqueue(user: User, title: str, content: str, level: int, team: Optional[str], filename: Optional[str],
             review_by: Optional[str], previous: Optional[dict], response: Response) -> dict:
    """Quick checks now, indexing later: the person gets an answer in a moment and follows the job."""
    try:
        content_hash = ingest.precheck(user, content, team)
        document_id = str(uuid.uuid4())
        status = ingest.status_for(user)
        version = previous["version"] + 1 if previous else 1
        job_id = jobs.enqueue(user, document_id=document_id, title=title, content=content, level=level,
                              engagement_id=team, filename=filename, review_by=review_by, previous=previous,
                              status=status, content_hash=content_hash, version=version)
    except ingest.IngestError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    response.status_code = 202
    return {"status": "queued", "job_id": job_id, "document_id": document_id, "title": title,
            "version": version, "publish_status": status}


@router.get("/options")
def upload_options(user: User = Depends(get_current_user)):
    """What this person may upload, for the upload form."""
    if user.is_admin:
        teams = [{"id": t["id"], "name": t["name"]} for t in admin.list_engagements(user.tenant_id)]
        return {"can_upload": True, "company_wide": True, "max_level": 4, "teams": teams}
    if user.level >= 2:
        return {"can_upload": True, "company_wide": False, "max_level": user.level,
                "teams": admin.user_engagements(user.tenant_id, user.id)}
    return {"can_upload": False, "company_wide": False, "max_level": 0, "teams": []}


@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    classification_level: int = Form(default=1, ge=1, le=4),
    engagement_id: str = Form(default=""),
    review_by: str = Form(default=""),
    new_version_of: str = Form(default=""),
    response: Response = None,
    user: User = Depends(get_current_user),
):
    try:
        review = validation.check_review_date(review_by)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    team = None
    if engagement_id:
        try:
            team = str(UUID(engagement_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid team")
    previous = None
    level = classification_level
    if new_version_of:
        try:
            previous_id = str(UUID(new_version_of))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid document")
        found = versions.info(user.tenant_id, previous_id)
        # Same rule as managing a document: an administrator, or the person who uploaded it.
        if found is None or not upload_policy.can_delete(user.is_admin, user.id, found["uploaded_by_id"]):
            raise HTTPException(status_code=404, detail="Document not found")
        if found["status"] != "published":
            raise HTTPException(status_code=409, detail="Only a live document can get a new version")
        # A new version keeps the old version's level and team: versioning can never lower the protection.
        level, team = found["level"], found["engagement_id"]
        previous = {**found, "document_id": previous_id}
        title = title or found["title"]
    _authorize(user, level, team)
    data = file.file.read(extract.MAX_BYTES + 1)
    try:
        text = extract.extract_text(file.filename or "", data)
    except extract.ExtractError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    name = (title.strip() or (file.filename or "Untitled").rsplit(".", 1)[0])[:300]
    if config.INGEST_ASYNC:
        return _enqueue(user, name, text, level, team, file.filename, review, previous, response)
    return _add(user, name, text, level, team, file.filename, review, previous)


@router.get("/jobs")
def my_jobs(user: User = Depends(get_current_user)):
    """Recent uploads and how far they got. Administrators see the whole company's; everyone else their own."""
    return {"jobs": jobs.list_recent(user.tenant_id, None if user.is_admin else user.id)}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, user: User = Depends(get_current_user)):
    try:
        job_id = str(UUID(job_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs.get(user.tenant_id, job_id)
    if job is None or not (user.is_admin or job["uploaded_by_id"] == user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/ingest")
def ingest_document(payload: IngestRequest, user: User = Depends(get_current_user)):
    """Add pasted text. Same rules as an upload."""
    team = str(payload.engagement_id) if payload.engagement_id else None
    return _add(user, payload.title, payload.content, payload.classification_level, team, None)


@router.get("")
def list_documents(user: User = Depends(get_current_user)):
    """Administrators see every document in the company (titles and settings, not content).
    Engagement managers see only what they uploaded."""
    if user.is_admin:
        return {"documents": admin.list_documents(user.tenant_id)}
    if user.level >= 2:
        return {"documents": admin.list_documents(user.tenant_id, uploaded_by_id=user.id)}
    raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.delete("/{document_id}")
def delete_document(document_id: UUID, user: User = Depends(get_current_user)):
    info = admin.document_info(user.tenant_id, str(document_id))
    if info is None or not upload_policy.can_delete(user.is_admin, user.id, info["uploaded_by_id"]):
        raise HTTPException(status_code=404, detail="Document not found")
    removed = admin.delete_document(user.tenant_id, str(document_id))
    admin.record(user, "document.delete", info["title"] or str(document_id), {"document_id": str(document_id), "sections": removed})
    return {"status": "deleted", "sections": removed}


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_a: UUID
    document_b: UUID


@router.get("/{document_id}/versions")
def document_versions(document_id: UUID, user: User = Depends(get_current_user)):
    """Every version of this document that you may read."""
    found = versions.info(user.tenant_id, str(document_id))
    if found is None:
        raise HTTPException(status_code=404, detail="Document not found")
    history = versions.history(user, found["doc_key"])
    if not any(v["document_id"] == str(document_id) for v in history):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"versions": history}


@router.post("/compare")
async def compare_documents(body: CompareRequest, user: User = Depends(get_current_user)):
    """Compare two documents you may read. The changes are found by code; the summary is checked against them."""
    from app.routers.chat import limiter
    if not limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.", headers={"Retry-After": "60"})
    a = versions.readable_text(user, str(body.document_a))
    b = versions.readable_text(user, str(body.document_b))
    if a is None or b is None:
        raise HTTPException(status_code=404, detail="Document not found")
    result = compare.diff(a["text"], b["text"])
    summary, note = None, None
    if result["changes"]:
        try:
            summary = await comparer.run(result["changes"])
        except LLMUnavailable:
            note = "The summary is unavailable right now. The list of changes below is complete."
        if summary is None and note is None:
            note = "A reliable summary could not be produced. The list of changes below is complete."
    else:
        note = "The two documents have the same sentences."
    return {"old": {"title": a["title"], "version": a["version"]}, "new": {"title": b["title"], "version": b["version"]},
            **result, "summary": summary, "note": note}
