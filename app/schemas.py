from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=500_000)
    classification_level: int = Field(default=1, ge=1, le=4)
    engagement_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
