import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.security import get_current_user, verify_password
from app.services import admin, governance, users
from app.services.users import User

router = APIRouter(prefix="/me", tags=["My data"])


class EraseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(..., max_length=128)


@router.get("/data")
def export_my_data(user: User = Depends(get_current_user)):
    """Download everything held about you (a JSON file)."""
    admin.record(user, "privacy.export", user.email)
    body = json.dumps(governance.export_user(user), indent=2, default=str)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="my-data.json"'})


@router.post("/erase")
def erase_my_data(body: EraseRequest, user: User = Depends(get_current_user)):
    """Delete your conversations and remove your words from the audit log. Needs your password."""
    found = users.get_with_password_hash(user.email)
    if not found or not found[1] or not verify_password(body.password, found[1]):
        raise HTTPException(status_code=403, detail="Incorrect password")
    result = governance.erase_user_data(user)
    admin.record(user, "privacy.erase", user.email, result)
    return {"status": "erased", **result}
