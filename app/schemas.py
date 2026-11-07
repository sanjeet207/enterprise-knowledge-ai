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


class NewUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., max_length=254)
    password: Optional[str] = Field(default=None, max_length=128, description="Leave empty for a single-sign-on-only account")
    level: int = Field(default=1, ge=1, le=4)
    is_admin: bool = False


class UserChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: Optional[int] = Field(default=None, ge=1, le=4)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    password: Optional[str] = Field(default=None, max_length=128)


class NewTeam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)


class TeamMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
