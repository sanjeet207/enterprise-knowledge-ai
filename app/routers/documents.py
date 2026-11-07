from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.schemas import IngestRequest
from app.security import get_current_user
from app.services import admin, extract, ingest, upload_policy, users
from app.services.users import User

router = APIRouter(prefix="/documents", tags=["Documents"])


def _authorize(user: User, level: int, engagement_id: Optional[str]) -> None:
    is_member = bool(engagement_id) and users.is_engagement_member(engagement_id, user.id, user.tenant_id)
    try:
        upload_policy.check_upload(user.is_admin, user.level, level, engagement_id, is_member)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


def _add(user: User, title: str, content: str, level: int, engagement_id: Optional[str], filename: Optional[str]) -> dict:
    _authorize(user, level, engagement_id)
    try:
        result = ingest.ingest_document(user, title, content, level, engagement_id, filename)
    except ingest.IngestError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    return {"status": "success", **result}


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
    user: User = Depends(get_current_user),
):
    team = None
    if engagement_id:
        try:
            team = str(UUID(engagement_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid team")
    _authorize(user, classification_level, team)
    data = file.file.read(extract.MAX_BYTES + 1)
    try:
        text = extract.extract_text(file.filename or "", data)
    except extract.ExtractError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    name = (title.strip() or (file.filename or "Untitled").rsplit(".", 1)[0])[:300]
    return _add(user, name, text, classification_level, team, file.filename)


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
