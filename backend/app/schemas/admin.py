from datetime import datetime
from typing import Literal

from pydantic import Field, validator

from app.schemas.common import APIBaseModel

IngestionSourceName = Literal["news", "sanctions", "ais", "prices", "refinery"]


class IngestionRunRequest(APIBaseModel):
    """Request payload used to trigger a manual ingestion run."""

    sources: list[IngestionSourceName] = Field(
        default_factory=list,
        description="Optional subset of ingestion sources to run. Empty means run all sources.",
    )
    demo_mode: bool = Field(default=True, description="Use the demo/static data generators.")

    @validator("sources", pre=True, always=True)
    def normalize_sources(cls, value: list[str] | None) -> list[str]:
        return list(value or [])


class IngestionSourceResult(APIBaseModel):
    source: str
    demo_mode: bool
    started_at: str
    finished_at: str
    fetched_count: int
    normalized_count: int
    upserted_count: int
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    status: str = "success"
    error: str | None = None


class IngestionRunResponse(APIBaseModel):
    run_started_at: str
    run_finished_at: str
    requested_sources: list[str]
    results: list[IngestionSourceResult]
    success_count: int
    failure_count: int


class SchedulerJobResponse(APIBaseModel):
    id: str
    next_run_time: str | None = None
    trigger: str


class SchedulerStatusResponse(APIBaseModel):
    enabled: bool
    running: bool
    jobs: list[SchedulerJobResponse] = Field(default_factory=list)
    last_started_at: str | None = None
    reason: str | None = None


class JobRunResponse(APIBaseModel):
    job_name: str
    started_at: str
    finished_at: str
    status: str
    result: dict = Field(default_factory=dict)
    error: str | None = None


class AuditLogItemResponse(APIBaseModel):
    id: int
    user_id: int | None = None
    user_email: str | None = None
    action: str
    entity_type: str
    entity_id: str
    metadata_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AuditLogListResponse(APIBaseModel):
    items: list[AuditLogItemResponse] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int
    page: int
    pages: int
    sort_by: str | None = None
    sort_order: str | None = None


class SystemSummaryResponse(APIBaseModel):
    generated_at: str
    counts: dict[str, int]
    latest_activity: dict[str, str | None]
    scheduler: dict[str, object]


class SeedDemoResponse(APIBaseModel):
    message: str
    seeded_at: str
    summary: SystemSummaryResponse
