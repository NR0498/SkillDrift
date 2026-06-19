# SkillDrift

SkillDrift tracks whether technology skills are gaining or losing demand across job
posting snapshots. It combines a real ingestion pipeline, PySpark analytics, Apache
Solr search, S3 run artifacts, FastAPI, and a dependency-free dashboard.

## Architecture

```text
RemoteOK API
    │
    ▼
job_snapshots (SQLite locally / Neon PostgreSQL in production)
    ├──► Apache Solr ──► GET /search
    │
    └──► PySpark trend engine ──► skill_trends ──► FastAPI ──► dashboard
                                 └──► S3 summary artifact
```

The deployable system is intentionally split:

- Vercel hosts the static dashboard and lightweight FastAPI read API.
- PySpark, ingestion, and Solr indexing run as scheduled jobs (GitHub Actions,
  a VM, ECS, Kubernetes, or another worker platform).
- Solr must be hosted somewhere reachable by the Vercel function. `localhost`
  only works for local development.
- SQLite is the zero-configuration local store. Neon PostgreSQL is the production
  database path because a Vercel filesystem is ephemeral.

## Stack

- Python 3.11
- Java 17 and PySpark 3.5.5
- Apache Solr 9.8
- FastAPI and SQLAlchemy 2
- SQLite or Neon PostgreSQL
- AWS S3 or LocalStack
- Static HTML/CSS/JavaScript dashboard
- Docker Compose, pytest, Ruff, and GitHub Actions

## Quick start

Prerequisites: Docker Desktop and Python 3.11. The pipeline Docker image includes
Java 17, so a host Java installation is optional.

```powershell
Copy-Item .env.example .env
docker compose up -d
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

python ingest.py
python simulate_history.py --days 6
python indexer.py
python trend_engine.py
```

Start the API and dashboard in separate terminals:

```powershell
.\.venv\Scripts\uvicorn api:app --reload --port 8000
.\.venv\Scripts\python -m http.server 3000 --directory public
```

Open:

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Solr admin: <http://localhost:8983/solr/#/jobs_core>

The full local sequence is also available as:

```powershell
.\run_pipeline.ps1
```

## Historical simulation

A new installation has one real snapshot, so every drift score starts at zero.
Create deterministic demo history with:

```powershell
python simulate_history.py --days 6 --seed 42
```

Useful options:

- `--days N`: create 1–90 historical days.
- `--seed N`: reproduce the same demo dataset.
- `--replace`: delete and regenerate the selected historical range.

The simulator uses today's real jobs and controlled per-skill sampling slopes. It
does not invent job descriptions. Simulated rows are marked with a
`source` ending in `:simulated`, so demo data remains auditable. Do not present
simulated drift as a real market conclusion.

## Pipeline commands

```powershell
# Current daily snapshot
python ingest.py

# One-time portfolio/demo backfill
python simulate_history.py --days 6

# Full-text index
python indexer.py

# Spark analytics and S3 artifact
python trend_engine.py

# Skip S3 when only testing analytics
python trend_engine.py --skip-s3
```

In normal operation, run only ingestion, indexing, and trend computation each day.
The included `Daily pipeline` GitHub Action does this on a schedule. Simulation is
deliberately excluded from scheduled production runs.

## API

| Endpoint | Behavior |
|---|---|
| `GET /health` | Database and Solr readiness |
| `GET /skills/trending?direction=rising&limit=10` | Rising, declining, or all skills |
| `GET /skills/{skill_name}` | Skill metrics and full trend series |
| `GET /search?q=python&limit=20` | Solr full-text job search |

Limits are validated and capped at 100. Search failures return `503` instead of
silently returning an empty result.

## Neon production database

1. Create a Neon project and copy its pooled connection string.
2. Set `DATABASE_URL` locally and in Vercel:

   ```text
   postgresql://USER:PASSWORD@HOST/DB?sslmode=require
   ```

3. Set the same secret in the scheduled pipeline environment.
4. Run `python ingest.py` once. SQLAlchemy creates both required tables.

When `DATABASE_URL` is present, raw snapshots and computed trends share the same
PostgreSQL database. Without it, they use the requested separate local files:
`data/jobs.db` and `data/trends.db`.

## Vercel deployment

Import this repository into Vercel or run:

```powershell
vercel
vercel --prod
```

Configure these environment variables:

```text
DATABASE_URL=<Neon pooled connection string>
SOLR_URL=https://<public-solr-host>/solr/jobs_core
CORS_ORIGINS=https://<your-domain>
AWS_ENDPOINT_URL=
AWS_REGION=<region>
S3_BUCKET=<bucket>
```

The dashboard uses same-origin API calls in production and
`http://localhost:8000` during local development.

Vercel does not host the persistent Spark, Solr, or scheduled-worker layer. A
production portfolio deployment therefore needs a public Solr service or VM and
the included scheduled workflow (or an equivalent worker).

## S3

LocalStack is configured by default:

```text
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
S3_BUCKET=skilldrift-output
```

For AWS, clear `AWS_ENDPOINT_URL` and use an IAM role or scoped credentials with
`s3:HeadBucket`, `s3:CreateBucket` (optional), and `s3:PutObject` permissions.
Each run writes to a collision-safe timestamped key under `runs/YYYY/MM/DD/`.

## Verification

```powershell
.\.venv\Scripts\ruff check .
.\.venv\Scripts\pytest
curl http://localhost:8000/health
curl "http://localhost:8000/skills/trending?direction=all&limit=5"
curl "http://localhost:8000/search?q=python"
```

## Production notes

- RemoteOK usage should respect its terms, rate limits, and identification policy.
- Drift uses percentage share rather than raw counts, reducing day-to-day volume bias.
- Skill matching uses boundary-aware regular expressions to avoid matches such as
  `java` inside `javascript`.
- Simulated history is for UI and pipeline demonstration only.
- For stronger market claims, add more data sources and replace first-vs-last drift
  with a regression slope plus confidence/error metrics.

