from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import NewTeam, NewUser, TeamMember, UserChange
from app.security import require_admin
from app.services import admin, validation
from app.services.users import User

router = APIRouter(prefix="/admin", tags=["Admin"])


def _bad(exc: ValueError):
    raise HTTPException(status_code=422, detail=str(exc))


@router.get("/users")
def users(user: User = Depends(require_admin)):
    return {"users": admin.list_users(user.tenant_id)}


@router.post("/users", status_code=201)
def create_user(body: NewUser, user: User = Depends(require_admin)):
    try:
        email = validation.clean_email(body.email)
        validation.check_password(body.password)
    except ValueError as exc:
        _bad(exc)
    new_id = admin.create_user(user.tenant_id, email, body.password, body.level, body.is_admin)
    if new_id is None:
        raise HTTPException(status_code=409, detail="That email is already registered")
    admin.record(user, "user.create", email, {"level": body.level, "is_admin": body.is_admin})
    return {"id": new_id, "email": email}


@router.patch("/users/{user_id}")
def change_user(user_id: UUID, body: UserChange, user: User = Depends(require_admin)):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to change")
    if str(user_id) == user.id and set(changes) - {"password"}:
        raise HTTPException(status_code=409, detail="You cannot change your own level, status or administrator access")
    if "password" in changes:
        try:
            validation.check_password(changes["password"])
        except ValueError as exc:
            _bad(exc)
    if not admin.update_user(user.tenant_id, str(user_id), changes):
        raise HTTPException(status_code=404, detail="User not found")
    admin.record(user, "user.update", str(user_id), {k: ("(changed)" if k == "password" else v) for k, v in changes.items()})
    return {"status": "updated"}


@router.get("/teams")
def teams(user: User = Depends(require_admin)):
    return {"teams": admin.list_engagements(user.tenant_id)}


@router.post("/teams", status_code=201)
def create_team(body: NewTeam, user: User = Depends(require_admin)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Enter a team name")
    team_id = admin.create_engagement(user.tenant_id, name)
    admin.record(user, "team.create", name, {"team_id": team_id})
    return {"id": team_id, "name": name}


@router.post("/teams/{team_id}/members", status_code=201)
def add_member(team_id: UUID, body: TeamMember, user: User = Depends(require_admin)):
    if not admin.add_member(user.tenant_id, str(team_id), str(body.user_id)):
        raise HTTPException(status_code=404, detail="Team or person not found in your company")
    admin.record(user, "team.add_member", str(team_id), {"user_id": str(body.user_id)})
    return {"status": "added"}


@router.delete("/teams/{team_id}/members/{user_id}")
def remove_member(team_id: UUID, user_id: UUID, user: User = Depends(require_admin)):
    if not admin.remove_member(user.tenant_id, str(team_id), str(user_id)):
        raise HTTPException(status_code=404, detail="Membership not found")
    admin.record(user, "team.remove_member", str(team_id), {"user_id": str(user_id)})
    return {"status": "removed"}


@router.get("/events")
def events(user: User = Depends(require_admin)):
    return {"events": admin.recent_events(user.tenant_id)}


@router.post("/documents/{document_id}/approve")
def approve_document(document_id: UUID, user: User = Depends(require_admin)):
    info = admin.document_info(user.tenant_id, str(document_id))
    if info is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if info["uploaded_by_id"] == user.id:
        raise HTTPException(status_code=409, detail="Another administrator must approve your own upload")
    if not admin.approve_document(user.tenant_id, str(document_id)):
        raise HTTPException(status_code=409, detail="This document is not waiting for approval")
    admin.record(user, "document.approve", info["title"] or str(document_id), {"document_id": str(document_id)})
    return {"status": "published"}


@router.get("/insights")
def insights(days: int = 30, user: User = Depends(require_admin)):
    """Usage and content gaps for the company. Counts and unanswered questions only: no names, no answers."""
    return admin.insights(user.tenant_id, max(1, min(days, 365)))
