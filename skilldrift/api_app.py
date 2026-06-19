from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from skilldrift.config import get_settings
from skilldrift.db import initialize_databases
from skilldrift.logging import configure_logging
from skilldrift.repository import TrendRepository
from skilldrift.schemas import HealthResponse, SearchResponse, SkillDetail, SkillSummary
from skilldrift.search import SearchUnavailable, SolrSearch

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_databases(settings)
    yield


app = FastAPI(
    title="SkillDrift API",
    version="1.0.0",
    description="Skill demand trend analytics and full-text job search.",
    lifespan=lifespan,
)
allow_credentials = "*" not in settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


def get_repository() -> TrendRepository:
    return TrendRepository()


def get_search() -> SolrSearch:
    return SolrSearch()


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": "SkillDrift API", "docs": "/docs", "health": "/health"}


@app.get("/health", response_model=HealthResponse)
def health(
    repository: Annotated[TrendRepository, Depends(get_repository)],
    search: Annotated[SolrSearch, Depends(get_search)],
) -> HealthResponse:
    database_ok = repository.ping()
    search_ok = search.ping()
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        database="ok" if database_ok else "unavailable",
        search="ok" if search_ok else "unavailable",
    )


@app.get("/skills/trending", response_model=list[SkillSummary])
def trending_skills(
    repository: Annotated[TrendRepository, Depends(get_repository)],
    direction: Literal["rising", "declining", "all"] = "all",
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict]:
    try:
        return repository.list_trending(direction, limit)
    except SQLAlchemyError as exc:
        logger.exception("Could not load trend data")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trend data is unavailable. Run the pipeline or configure DATABASE_URL.",
        ) from exc


@app.get("/skills/{skill_name}", response_model=SkillDetail)
def skill_detail(
    skill_name: str,
    repository: Annotated[TrendRepository, Depends(get_repository)],
) -> dict:
    try:
        result = repository.get_skill(skill_name)
    except (SQLAlchemyError, json.JSONDecodeError) as exc:
        logger.exception("Could not load skill detail")
        raise HTTPException(status_code=503, detail="Trend data is unavailable.") from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' was not found")
    return result


@app.get("/search", response_model=SearchResponse)
def search_jobs(
    search: Annotated[SolrSearch, Depends(get_search)],
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> SearchResponse:
    try:
        result = search.search(q.strip(), limit)
    except SearchUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SearchResponse(query=q.strip(), **result)
