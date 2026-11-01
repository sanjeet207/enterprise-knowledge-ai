from fastapi import APIRouter, Depends, Query

from app.security import require_level
from app.services import audit
from app.services.users import User

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/events")
def list_events(limit: int = Query(default=50, ge=1, le=200), user: User = Depends(require_level(4))):
    """Recent questions for the caller's own tenant. Partners (level 4) only."""
    return {"events": audit.recent_events(user.tenant_id, limit)}
