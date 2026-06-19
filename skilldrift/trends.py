from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from skilldrift.db import get_jobs_engine, get_trends_engine, skill_trends
from skilldrift.skills import SKILLS, pattern_for
from skilldrift.storage import upload_run_summary

logger = logging.getLogger(__name__)


def _status(drift: float, threshold: float) -> str:
    if drift > threshold:
        return "rising"
    if drift < -threshold:
        return "declining"
    return "stable"


def _write_results(results: list[dict[str, Any]], engine: Engine) -> None:
    rows = [
        {
            "skill": result["skill"],
            "drift": result["drift"],
            "current_pct": result["current_pct"],
            "snapshots": result["snapshots"],
            "status": result["status"],
            "trend_json": json.dumps(result["trend"]),
            "computed_at": datetime.now(UTC),
        }
        for result in results
    ]
    with engine.begin() as connection:
        connection.execute(delete(skill_trends))
        if not rows:
            return
        dialect = engine.dialect.name
        if dialect == "postgresql":
            statement = pg_insert(skill_trends).values(rows)
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=["skill"],
                    set_={
                        column: getattr(statement.excluded, column)
                        for column in (
                            "drift",
                            "current_pct",
                            "snapshots",
                            "status",
                            "trend_json",
                            "computed_at",
                        )
                    },
                )
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(skill_trends).values(rows)
            connection.execute(
                statement.on_conflict_do_update(
                    index_elements=["skill"],
                    set_={
                        column: getattr(statement.excluded, column)
                        for column in (
                            "drift",
                            "current_pct",
                            "snapshots",
                            "status",
                            "trend_json",
                            "computed_at",
                        )
                    },
                )
            )
        else:
            connection.execute(skill_trends.insert(), rows)


def run_trend_engine(
    threshold: float = 0.3,
    jobs_engine: Engine | None = None,
    trends_engine: Engine | None = None,
    upload_summary: bool = True,
) -> list[dict[str, Any]]:
    # Imported lazily so the FastAPI/Vercel runtime does not need Java, pandas, or PySpark.
    import pandas as pd
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    jobs_engine = jobs_engine or get_jobs_engine()
    trends_engine = trends_engine or get_trends_engine()
    jobs = pd.read_sql(
        "SELECT id, title, company, tags, description, snapshot_date, source FROM job_snapshots",
        jobs_engine,
    )
    if jobs.empty:
        raise RuntimeError("No snapshots found. Run ingest.py first.")
    jobs["snapshot_date"] = jobs["snapshot_date"].astype(str)
    jobs = jobs.fillna("")

    spark = (
        SparkSession.builder.appName("SkillDrift")
        .master("local[*]")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        frame = spark.createDataFrame(jobs)
        searchable = F.concat_ws(
            " ",
            F.coalesce(F.col("title"), F.lit("")),
            F.coalesce(F.col("tags"), F.lit("")),
            F.coalesce(F.col("description"), F.lit("")),
        )
        totals = frame.groupBy("snapshot_date").agg(F.count("*").alias("total_jobs"))
        results: list[dict[str, Any]] = []

        for skill in SKILLS:
            counts = (
                frame.filter(searchable.rlike(pattern_for(skill)))
                .groupBy("snapshot_date")
                .agg(F.countDistinct("id").alias("skill_count"))
            )
            rows = (
                totals.join(counts, "snapshot_date", "left")
                .fillna({"skill_count": 0})
                .withColumn(
                    "demand_pct",
                    F.round(F.col("skill_count") / F.col("total_jobs") * 100, 2),
                )
                .orderBy("snapshot_date")
                .collect()
            )
            trend = [
                {"date": row["snapshot_date"], "pct": float(row["demand_pct"])} for row in rows
            ]
            drift = round(trend[-1]["pct"] - trend[0]["pct"], 2) if len(trend) > 1 else 0.0
            results.append(
                {
                    "skill": skill,
                    "drift": drift,
                    "current_pct": trend[-1]["pct"],
                    "snapshots": len(trend),
                    "status": _status(drift, threshold),
                    "trend": trend,
                }
            )
            logger.info("%-16s drift=%+.2f status=%s", skill, drift, results[-1]["status"])
    finally:
        spark.stop()

    _write_results(results, trends_engine)
    if upload_summary:
        summary = {
            "computed_at": datetime.now(UTC).isoformat(),
            "skills_tracked": len(results),
            "rising": [row["skill"] for row in results if row["status"] == "rising"],
            "declining": [row["skill"] for row in results if row["status"] == "declining"],
        }
        try:
            upload_run_summary(summary)
        except Exception:
            logger.exception("S3 summary upload failed; trend results are still available")
    return results
