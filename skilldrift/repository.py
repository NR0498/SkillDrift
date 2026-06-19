from __future__ import annotations

import json

from sqlalchemy import asc, desc, func, select
from sqlalchemy.engine import Engine

from skilldrift.db import get_jobs_engine, get_trends_engine, job_snapshots, skill_trends


class TrendRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_trends_engine()

    def list_trending(self, direction: str, limit: int) -> list[dict]:
        statement = select(
            skill_trends.c.skill,
            skill_trends.c.drift,
            skill_trends.c.current_pct,
            skill_trends.c.snapshots,
            skill_trends.c.status,
        )
        if direction != "all":
            statement = statement.where(skill_trends.c.status == direction)
        if direction == "declining":
            order = asc(skill_trends.c.drift)
        elif direction == "all":
            order = desc(func.abs(skill_trends.c.drift))
        else:
            order = desc(skill_trends.c.drift)
        with self.engine.connect() as connection:
            rows = connection.execute(statement.order_by(order).limit(limit)).mappings().all()
        return [dict(row) for row in rows]

    def get_skill(self, skill_name: str) -> dict | None:
        statement = select(skill_trends).where(skill_trends.c.skill == skill_name.strip().lower())
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        if not row:
            return None
        result = dict(row)
        result["trend"] = json.loads(result.pop("trend_json"))
        result.pop("computed_at", None)
        return result

    def ping(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(select(1))
            return True
        except Exception:
            return False

    def dataset_stats(self) -> dict:
        jobs_engine = get_jobs_engine()
        with jobs_engine.connect() as connection:
            total_records = connection.execute(
                select(func.count()).select_from(job_snapshots)
            ).scalar_one()
            distinct_jobs = connection.execute(
                select(func.count(func.distinct(job_snapshots.c.id)))
            ).scalar_one()
            snapshot_count = connection.execute(
                select(func.count(func.distinct(job_snapshots.c.snapshot_date)))
            ).scalar_one()
            latest_snapshot = connection.execute(
                select(func.max(job_snapshots.c.snapshot_date))
            ).scalar_one()
            real_records = connection.execute(
                select(func.count())
                .select_from(job_snapshots)
                .where(~job_snapshots.c.source.like("%:simulated"))
            ).scalar_one()
            simulated_records = total_records - real_records

        with self.engine.connect() as connection:
            tracked_skills = connection.execute(
                select(func.count()).select_from(skill_trends)
            ).scalar_one()
            status_counts = dict(
                connection.execute(
                    select(skill_trends.c.status, func.count()).group_by(skill_trends.c.status)
                ).all()
            )

        return {
            "total_records": total_records,
            "distinct_jobs": distinct_jobs,
            "snapshot_count": snapshot_count,
            "real_records": real_records,
            "simulated_records": simulated_records,
            "tracked_skills": tracked_skills,
            "rising_skills": status_counts.get("rising", 0),
            "stable_skills": status_counts.get("stable", 0),
            "declining_skills": status_counts.get("declining", 0),
            "latest_snapshot": latest_snapshot,
        }
