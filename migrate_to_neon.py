import sqlite3

import psycopg

from skilldrift.config import get_settings

DATABASE_URL = get_settings().database_url

if not DATABASE_URL:
      raise RuntimeError(
          "DATABASE_URL is required. Add it to .env or set it in the environment."
      )


def migrate_jobs(connection: psycopg.Connection) -> int:
      source = sqlite3.connect("data/jobs.db")
      source.row_factory = sqlite3.Row

      rows = source.execute(
          """
          SELECT id, title, company, tags, description,
                 snapshot_date, source, source_url, created_at
          FROM job_snapshots
          """
      ).fetchall()

      with connection.cursor() as cursor:
          cursor.executemany(
              """
              INSERT INTO job_snapshots (
                  id, title, company, tags, description,
                  snapshot_date, source, source_url, created_at
              )
              VALUES (
                  %(id)s, %(title)s, %(company)s, %(tags)s,
                  %(description)s, %(snapshot_date)s, %(source)s,
                  %(source_url)s, %(created_at)s
              )
              ON CONFLICT (id, snapshot_date) DO NOTHING
              """,
              [dict(row) for row in rows],
          )

      source.close()
      return len(rows)


def migrate_trends(connection: psycopg.Connection) -> int:
      source = sqlite3.connect("data/trends.db")
      source.row_factory = sqlite3.Row

      rows = source.execute(
          """
          SELECT skill, drift, current_pct, snapshots,
                 status, trend_json, computed_at
          FROM skill_trends
          """
      ).fetchall()

      with connection.cursor() as cursor:
          cursor.executemany(
              """
              INSERT INTO skill_trends (
                  skill, drift, current_pct, snapshots,
                  status, trend_json, computed_at
              )
              VALUES (
                  %(skill)s, %(drift)s, %(current_pct)s,
                  %(snapshots)s, %(status)s, %(trend_json)s,
                  %(computed_at)s
              )
              ON CONFLICT (skill) DO UPDATE SET
                  drift = EXCLUDED.drift,
                  current_pct = EXCLUDED.current_pct,
                  snapshots = EXCLUDED.snapshots,
                  status = EXCLUDED.status,
                  trend_json = EXCLUDED.trend_json,
                  computed_at = EXCLUDED.computed_at
              """,
              [dict(row) for row in rows],
          )

      source.close()
      return len(rows)


with psycopg.connect(DATABASE_URL) as connection:
      jobs = migrate_jobs(connection)
      trends = migrate_trends(connection)

      with connection.cursor() as cursor:
          cursor.execute("SELECT COUNT(*) FROM job_snapshots")
          destination_jobs = cursor.fetchone()[0]

          cursor.execute("SELECT COUNT(*) FROM skill_trends")
          destination_trends = cursor.fetchone()[0]

print(f"Processed job snapshots: {jobs}")
print(f"Processed skill trends: {trends}")
print(f"Neon job snapshots: {destination_jobs}")
print(f"Neon skill trends: {destination_trends}")
