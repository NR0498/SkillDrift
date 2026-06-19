from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

from skilldrift.db import job_snapshots
from skilldrift.simulation import simulate_history


def memory_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_simulation_is_idempotent_with_fixed_seed():
    engine = memory_engine()
    job_snapshots.create(engine)
    today = datetime.now(UTC).date()
    with engine.begin() as connection:
        connection.execute(
            job_snapshots.insert(),
            {
                "id": "job-1",
                "title": "Senior Python Engineer",
                "company": "Example",
                "tags": "python, llm",
                "description": "Build production APIs",
                "snapshot_date": today,
                "source": "test",
                "source_url": "https://example.com/job",
            },
        )

    first = simulate_history(days=3, seed=7, engine=engine)
    second = simulate_history(days=3, seed=7, engine=engine)
    with engine.connect() as connection:
        total = connection.execute(select(func.count()).select_from(job_snapshots)).scalar_one()

    assert first > 0
    assert second == 0
    assert total == first + 1
