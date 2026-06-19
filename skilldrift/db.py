from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.engine import URL, Connection, Engine

from skilldrift.config import Settings, get_settings

metadata = MetaData()

job_snapshots = Table(
    "job_snapshots",
    metadata,
    Column("id", String(64), nullable=False),
    Column("title", Text, nullable=False),
    Column("company", Text, nullable=False),
    Column("tags", Text, nullable=False, default=""),
    Column("description", Text, nullable=False, default=""),
    Column("snapshot_date", Date, nullable=False),
    Column("source", String(64), nullable=False),
    Column("source_url", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("id", "snapshot_date", name="uq_job_snapshot"),
)

skill_trends = Table(
    "skill_trends",
    metadata,
    Column("skill", String(100), primary_key=True),
    Column("drift", Float, nullable=False),
    Column("current_pct", Float, nullable=False),
    Column("snapshots", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("trend_json", Text, nullable=False),
    Column("computed_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


def _sqlite_url(path: Path) -> URL:
    return URL.create("sqlite", database=str(path.resolve()))


def create_db_engine(url: str | URL) -> Engine:
    kwargs: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    if str(url).startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    elif str(url).startswith(("postgresql://", "postgresql+psycopg://")):
        kwargs["connect_args"] = {"connect_timeout": 10}
    return create_engine(url, **kwargs)


def get_jobs_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return create_db_engine(settings.normalized_database_url or _sqlite_url(settings.jobs_db_path))


def get_trends_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return create_db_engine(
        settings.normalized_database_url or _sqlite_url(settings.trends_db_path)
    )


def initialize_databases(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    jobs_engine = get_jobs_engine(settings)
    trends_engine = get_trends_engine(settings)
    job_snapshots.create(jobs_engine, checkfirst=True)
    skill_trends.create(trends_engine, checkfirst=True)


@contextmanager
def connect(engine: Engine) -> Iterator[Connection]:
    with engine.begin() as connection:
        yield connection
