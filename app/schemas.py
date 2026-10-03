from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class DocumentIngestRequest(BaseModel):
    title: str = Field(..., description="Title of the document")
    content: str = Field(..., description="Raw text content of the document")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional custom metadata")

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query string")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    top_k: int = Field(default=5, description="Number of search results to return")
