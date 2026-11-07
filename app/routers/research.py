from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agents import research
from app.routers.chat import retriever
from app.security import get_current_user
from app.services import reports
from app.services.llm import LLMUnavailable
from app.services.ratelimit import SlidingWindow
from app.services.users import User

router = APIRouter(prefix="/research", tags=["Research assistant"])
limiter = SlidingWindow(5, 600)  # five reports per ten minutes per person: a report is several model calls


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str = Field(..., min_length=10, max_length=500)


@router.post("")
async def create_report(body: ResearchRequest, user: User = Depends(get_current_user)):
    """Prepare a cited report from documents you may read. Takes a minute or two; the result is a draft to review."""
    if not limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="You have requested several reports recently. Please wait a few minutes.",
                            headers={"Retry-After": "300"})
    try:
        report = await research.run_research(user, body.request, retriever)
    except research.ResearchRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LLMUnavailable:
        raise HTTPException(status_code=503, detail="The answer service is unavailable. Try again shortly.")
    report["id"] = reports.save(user, report["request"], report)
    return report


@router.get("")
def my_reports(user: User = Depends(get_current_user)):
    return {"reports": reports.list_for(user)}


@router.get("/{report_id}")
def get_report(report_id: UUID, user: User = Depends(get_current_user)):
    found = reports.get(user, str(report_id))
    if found is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return found


@router.post("/{report_id}/review")
def mark_reviewed(report_id: UUID, user: User = Depends(get_current_user)):
    """The person confirms they have read and checked the draft."""
    if not reports.mark_reviewed(user, str(report_id)):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "reviewed"}


@router.delete("/{report_id}")
def delete_report(report_id: UUID, user: User = Depends(get_current_user)):
    if not reports.delete(user, str(report_id)):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "deleted"}
