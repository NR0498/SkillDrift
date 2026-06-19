from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class TrendPoint(BaseModel):
    date: str
    pct: float


class SkillSummary(BaseModel):
    skill: str
    drift: float
    current_pct: float
    snapshots: int
    status: str


class SkillDetail(SkillSummary):
    trend: list[TrendPoint]


class JobResult(BaseModel):
    id: str
    title: str = ""
    company: str = ""
    tags: str | list[str] = ""
    description: str = ""
    snapshot_date: str | date | None = None
    source: str = ""
    source_url: str | None = None
    score: float | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    items: list[JobResult]


class HealthResponse(BaseModel):
    status: str
    database: str
    search: str
