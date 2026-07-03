from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, conint

from app.schemas.common import ORMBaseSchema


class KnowledgeDocumentCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=240)
    source_name: str = Field(..., min_length=2, max_length=160)
    source_type: str = Field(..., min_length=2, max_length=80)
    url: str | None = Field(default=None, max_length=500)
    external_id: str | None = Field(default=None, max_length=160)
    summary: str | None = None
    content_text: str = Field(..., min_length=20)
    published_at: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunkResponse(ORMBaseSchema):
    id: int
    document_id: int
    chunk_index: int
    chunk_text: str
    token_count: int
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentResponse(ORMBaseSchema):
    id: int
    title: str
    source_name: str
    source_type: str
    url: str | None
    external_id: str | None
    summary: str | None
    content_text: str
    published_at: datetime | None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    chunk_count: int
    content_hash: str | None
    created_at: datetime
    updated_at: datetime


class ExplanationRequest(BaseModel):
    use_llm: bool = True
    top_k_notes: conint(ge=1, le=10) = 5


class SourceCitationResponse(BaseModel):
    document_id: int
    chunk_id: int
    title: str
    source_name: str
    source_type: str
    score: float
    excerpt: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ReportResponse(BaseModel):
    title: str
    summary: str
    generated_at: datetime
    model_used: str
    citations: list[SourceCitationResponse] = Field(default_factory=list)
    structured_context: dict[str, Any] = Field(default_factory=dict)


class RiskBriefResponse(ReportResponse):
    scope: str = "national"

