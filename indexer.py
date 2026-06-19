from __future__ import annotations

import logging

import pysolr
from sqlalchemy import select

from skilldrift.config import get_settings
from skilldrift.db import get_jobs_engine, job_snapshots
from skilldrift.logging import configure_logging

logger = logging.getLogger(__name__)


def index_jobs(batch_size: int = 500) -> int:
    settings = get_settings()
    engine = get_jobs_engine(settings)
    solr = pysolr.Solr(settings.solr_url, always_commit=False, timeout=30)
    indexed = 0

    with engine.connect() as connection:
        result = connection.execution_options(stream_results=True).execute(select(job_snapshots))
        batch = []
        for row in result.mappings():
            batch.append(
                {
                    "id": f"{row['id']}_{row['snapshot_date']}",
                    "title": row["title"],
                    "company": row["company"],
                    "tags": row["tags"],
                    "description": row["description"],
                    "snapshot_date": row["snapshot_date"].isoformat(),
                    "source": row["source"],
                    "source_url": row["source_url"],
                }
            )
            if len(batch) >= batch_size:
                solr.add(batch, commit=False)
                indexed += len(batch)
                batch.clear()
        if batch:
            solr.add(batch, commit=False)
            indexed += len(batch)
    solr.commit()
    logger.info("Indexed %s documents", indexed)
    return indexed


if __name__ == "__main__":
    settings = get_settings()
    configure_logging(settings.log_level)
    print(f"[Solr] indexed={index_jobs()}")
