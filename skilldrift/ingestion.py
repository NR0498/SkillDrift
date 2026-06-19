from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, date, datetime
from html import unescape
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from urllib3.util.retry import Retry

from skilldrift.config import Settings, get_settings
from skilldrift.db import get_jobs_engine, job_snapshots

logger = logging.getLogger(__name__)
TAG_RE = re.compile(r"<[^>]+>")


def _session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def _plain_text(value: str | None, limit: int = 10_000) -> str:
    return unescape(TAG_RE.sub(" ", value or "")).strip()[:limit]


def fetch_jobs(settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    logger.info("Fetching RemoteOK jobs")
    response = _session().get(
        settings.remoteok_url,
        headers={"User-Agent": settings.remoteok_user_agent, "Accept": "application/json"},
        timeout=(5, 30),
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("RemoteOK response was not a JSON list")

    jobs: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict) or not raw.get("position"):
            continue
        source_id = str(raw.get("id") or raw.get("url") or raw["position"])
        jobs.append(
            {
                "id": hashlib.sha256(f"remoteok:{source_id}".encode()).hexdigest(),
                "title": _plain_text(raw.get("position"), 500),
                "company": _plain_text(raw.get("company"), 500),
                "tags": ", ".join(str(tag) for tag in raw.get("tags", []) if tag),
                "description": _plain_text(raw.get("description")),
                "source": "remoteok",
                "source_url": raw.get("url"),
            }
        )
    logger.info("Fetched %s valid jobs", len(jobs))
    return jobs


def save_snapshot(
    jobs: list[dict[str, Any]],
    engine: Engine | None = None,
    snapshot_date: date | None = None,
) -> int:
    engine = engine or get_jobs_engine()
    snapshot_date = snapshot_date or datetime.now(UTC).date()
    rows = [{**job, "snapshot_date": snapshot_date} for job in jobs]
    if not rows:
        return 0

    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "postgresql":
            statement = pg_insert(job_snapshots).values(rows)
            result = connection.execute(
                statement.on_conflict_do_nothing(index_elements=["id", "snapshot_date"])
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(job_snapshots).values(rows)
            result = connection.execute(
                statement.on_conflict_do_nothing(index_elements=["id", "snapshot_date"])
            )
        else:
            result = connection.execute(job_snapshots.insert(), rows)
    saved = max(result.rowcount or 0, 0)
    logger.info("Saved %s new jobs for snapshot %s", saved, snapshot_date)
    return saved
