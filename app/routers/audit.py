from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.security import require_level
from app.services import admin, audit, audit_export
from app.services.users import User

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/events")
def list_events(limit: int = Query(default=50, ge=1, le=200), user: User = Depends(require_level(4))):
    """Recent questions for the caller's own tenant. Partners (level 4) only."""
    return {"events": audit.recent_events(user.tenant_id, limit)}


@router.get("/export.csv")
def export_csv(days: int = Query(default=30, ge=1, le=365), user: User = Depends(require_level(4))):
    """Questions, who asked, outcome, score and timing for the last N days. No answers and no passages."""
    body = audit_export.to_csv(audit_export.fetch(user.tenant_id, days))
    admin.record(user, "audit.export", f"last {days} days")
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="audit-last-{days}-days.csv"'})
