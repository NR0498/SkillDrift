from __future__ import annotations

import logging
from typing import Any

import requests
from sqlalchemy import and_, func, or_, select

from skilldrift.config import Settings, get_settings
from skilldrift.db import get_jobs_engine, job_snapshots

logger = logging.getLogger(__name__)


class SearchUnavailable(RuntimeError):
    pass


def _repair_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    current = value
    markers = ("Ã", "Â", "â")
    for _ in range(3):
        if not any(marker in current for marker in markers):
            break
        try:
            repaired = current.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if repaired == current:
            break
        current = repaired
    return current


class SolrSearch:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.session = requests.Session()

    def ping(self) -> bool:
        try:
            response = self.session.get(
                f"{self.settings.solr_url}/admin/ping",
                timeout=self.settings.solr_timeout_seconds,
            )
            if response.ok:
                return True
        except requests.RequestException:
            pass
        try:
            with get_jobs_engine(self.settings).connect() as connection:
                connection.execute(select(1))
            return True
        except Exception:
            return False

    def _database_search(self, query: str, limit: int) -> dict[str, Any]:
        terms = [term for term in query.lower().split() if term]
        searchable_columns = (
            job_snapshots.c.title,
            job_snapshots.c.company,
            job_snapshots.c.tags,
            job_snapshots.c.description,
        )
        term_filters = [
            or_(*(column.ilike(f"%{term}%") for column in searchable_columns))
            for term in terms
        ]
        latest_snapshot = select(func.max(job_snapshots.c.snapshot_date)).scalar_subquery()
        where_clause = and_(
            job_snapshots.c.snapshot_date == latest_snapshot,
            *term_filters,
        )
        fields = (
            job_snapshots.c.id,
            job_snapshots.c.title,
            job_snapshots.c.company,
            job_snapshots.c.tags,
            job_snapshots.c.description,
            job_snapshots.c.snapshot_date,
            job_snapshots.c.source,
            job_snapshots.c.source_url,
        )
        with get_jobs_engine(self.settings).connect() as connection:
            total = connection.execute(
                select(func.count()).select_from(job_snapshots).where(where_clause)
            ).scalar_one()
            rows = connection.execute(
                select(*fields)
                .where(where_clause)
                .order_by(job_snapshots.c.title)
                .limit(limit)
            ).mappings().all()
        items = []
        for row in rows:
            item = dict(row)
            for field in ("title", "company", "tags", "description"):
                item[field] = _repair_text(item.get(field))
            items.append(item)
        return {"total": total, "items": items}

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.settings.solr_url}/select",
                params={
                    "q": query,
                    "q.op": "AND",
                    "df": "_text_",
                    "rows": limit,
                    "wt": "json",
                    "fl": "id,title,company,tags,description,snapshot_date,source,source_url,score",
                },
                timeout=self.settings.solr_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()["response"]
            return {"total": payload["numFound"], "items": payload["docs"]}
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.warning("Solr search failed; using database fallback: %s", exc)
            try:
                return self._database_search(query, limit)
            except Exception as fallback_exc:
                logger.exception("Database search fallback failed")
                raise SearchUnavailable(
                    "Search service is temporarily unavailable"
                ) from fallback_exc
