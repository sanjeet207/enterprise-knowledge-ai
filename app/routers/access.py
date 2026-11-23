from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.security import get_current_user, require_admin
from app.services import access_requests, admin
from app.services.users import User

router = APIRouter(tags=["Access requests"])


class NewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., max_length=2000, description="What the person was trying to find out")
    reason: str = Field(..., max_length=2000, description="Why they need it")


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(..., description="approved or denied")
    note: str = Field(default="", max_length=2000)


@router.post("/access-requests", status_code=201)
def create_request(body: NewRequest, user: User = Depends(get_current_user)):
    try:
        question, reason = access_requests.clean_request(body.question, body.reason)
        request_id = access_requests.create(user, question, reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    admin.record(user, "access.request", question[:120], {"request_id": request_id})
    return {"id": request_id, "status": "pending"}


@router.get("/access-requests/mine")
def my_requests(user: User = Depends(get_current_user)):
    return {"requests": access_requests.list_mine(user)}


@router.get("/admin/access-requests")
def queue(status: str = "pending", user: User = Depends(require_admin)):
    return {"requests": access_requests.list_for_admin(user.tenant_id, only_pending=status != "all")}


@router.post("/admin/access-requests/{request_id}/decision")
def decide(request_id: UUID, body: Decision, user: User = Depends(require_admin)):
    found = access_requests.get(user.tenant_id, str(request_id))
    if found is None:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        note = access_requests.check_decision(found["status"], body.decision, body.note, user.id, found["user_id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not access_requests.decide(user.tenant_id, str(request_id), user.email, body.decision, note):
        raise HTTPException(status_code=409, detail="This request has already been decided.")
    admin.record(user, f"access.{body.decision}", found["user_email"], {"request_id": str(request_id), "note": note})
    return {"status": body.decision}
