from typing import Literal

from pydantic import BaseModel, Field, validator

IngestionSourceName = Literal["news", "sanctions", "ais", "prices", "refinery"]


class IngestionRunRequest(BaseModel):
    """Request payload used to trigger a manual ingestion run."""

    sources: list[IngestionSourceName] = Field(
        default_factory=list,
        description="Optional subset of ingestion sources to run. Empty means run all sources.",
    )
    demo_mode: bool = Field(default=True, description="Use the demo/static data generators.")

    @validator("sources", pre=True, always=True)
    def normalize_sources(cls, value: list[str] | None) -> list[str]:
        return list(value or [])


class IngestionSourceResult(BaseModel):
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


class IngestionRunResponse(BaseModel):
    run_started_at: str
    run_finished_at: str
    requested_sources: list[str]
    results: list[IngestionSourceResult]
    success_count: int
    failure_count: int


class SchedulerJobResponse(BaseModel):
    id: str
    next_run_time: str | None = None
    trigger: str


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    running: bool
    jobs: list[SchedulerJobResponse] = Field(default_factory=list)
    last_started_at: str | None = None
    reason: str | None = None


class JobRunResponse(BaseModel):
    job_name: str
    started_at: str
    finished_at: str
    status: str
    result: dict = Field(default_factory=dict)
    error: str | None = None
