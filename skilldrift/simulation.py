from __future__ import annotations

import hashlib
import logging
import random
import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from skilldrift.db import get_jobs_engine, job_snapshots

logger = logging.getLogger(__name__)

# A controlled demo signal. Positive values make a job more likely to appear near today;
# negative values make it more likely in older snapshots.
DEMO_SLOPES = {
    "python": 0.06,
    "typescript": 0.10,
    "react": 0.05,
    "rust": 0.12,
    "llm": 0.16,
    "rag": 0.18,
    "kubernetes": 0.07,
    "java": -0.04,
    "jquery": -0.12,
    "php": -0.06,
}


def _stable_seed(seed: int, job_id: str, snapshot_date: date) -> int:
    digest = hashlib.sha256(f"{seed}:{job_id}:{snapshot_date.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _appearance_probability(text: str, day_index: int, total_days: int) -> float:
    progress = day_index / max(total_days - 1, 1)
    probability = 0.80
    for skill, slope in DEMO_SLOPES.items():
        if re.search(rf"(?i)(?<!\w){re.escape(skill)}(?!\w)", text):
            probability += slope * (progress - 0.5)
    return min(max(probability, 0.45), 0.97)


def simulate_history(
    days: int = 6,
    seed: int = 42,
    replace: bool = False,
    engine: Engine | None = None,
) -> int:
    if days < 1 or days > 90:
        raise ValueError("days must be between 1 and 90")

    engine = engine or get_jobs_engine()
    today = datetime.now(UTC).date()

    with engine.begin() as connection:
        latest_date = connection.execute(
            select(func.max(job_snapshots.c.snapshot_date))
        ).scalar_one()
        if latest_date is None:
            raise RuntimeError("No jobs found. Run ingest.py before simulating history.")

        source_rows = (
            connection.execute(
                select(job_snapshots).where(job_snapshots.c.snapshot_date == latest_date)
            )
            .mappings()
            .all()
        )
        if not source_rows:
            raise RuntimeError("Latest snapshot contains no jobs.")

        target_dates = [today - timedelta(days=offset) for offset in range(days, 0, -1)]
        if replace:
            connection.execute(
                delete(job_snapshots).where(
                    and_(
                        job_snapshots.c.snapshot_date >= target_dates[0],
                        job_snapshots.c.snapshot_date <= target_dates[-1],
                    )
                )
            )

        generated = []
        for day_index, target_date in enumerate(target_dates):
            for row in source_rows:
                text = " ".join((row["title"] or "", row["tags"] or "", row["description"] or ""))
                rng = random.Random(_stable_seed(seed, row["id"], target_date))
                if rng.random() <= _appearance_probability(text, day_index, len(target_dates)):
                    generated.append(
                        {
                            "id": row["id"],
                            "title": row["title"],
                            "company": row["company"],
                            "tags": row["tags"],
                            "description": row["description"],
                            "snapshot_date": target_date,
                            "source": f"{row['source']}:simulated",
                            "source_url": row["source_url"],
                        }
                    )

        dialect = engine.dialect.name
        if dialect == "postgresql":
            statement = pg_insert(job_snapshots).values(generated)
            result = connection.execute(
                statement.on_conflict_do_nothing(index_elements=["id", "snapshot_date"])
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(job_snapshots).values(generated)
            result = connection.execute(
                statement.on_conflict_do_nothing(index_elements=["id", "snapshot_date"])
            )
        else:
            result = connection.execute(insert(job_snapshots), generated)

    inserted = max(result.rowcount or 0, 0)
    logger.info(
        "Simulated %s historical snapshots across %s days using seed %s",
        inserted,
        days,
        seed,
    )
    return inserted
