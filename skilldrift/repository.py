from __future__ import annotations

import json

from sqlalchemy import asc, desc, select
from sqlalchemy.engine import Engine

from skilldrift.db import get_trends_engine, skill_trends


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
        order = (
            asc(skill_trends.c.drift) if direction == "declining" else desc(skill_trends.c.drift)
        )
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
