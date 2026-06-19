import json

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from skilldrift.db import skill_trends
from skilldrift.repository import TrendRepository


def memory_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_repository_orders_rising_and_decodes_detail():
    engine = memory_engine()
    skill_trends.create(engine)
    with engine.begin() as connection:
        connection.execute(
            skill_trends.insert(),
            [
                {
                    "skill": "python",
                    "drift": 2.5,
                    "current_pct": 14.0,
                    "snapshots": 2,
                    "status": "rising",
                    "trend_json": json.dumps(
                        [{"date": "2026-06-18", "pct": 11.5}, {"date": "2026-06-19", "pct": 14}]
                    ),
                },
                {
                    "skill": "java",
                    "drift": -1.0,
                    "current_pct": 8.0,
                    "snapshots": 2,
                    "status": "declining",
                    "trend_json": "[]",
                },
            ],
        )

    repository = TrendRepository(engine)
    assert repository.list_trending("all", 10)[0]["skill"] == "python"
    assert repository.list_trending("declining", 10)[0]["skill"] == "java"
    assert repository.get_skill("Python")["trend"][-1]["pct"] == 14
